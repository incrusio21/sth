# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from erpnext.controllers.status_updater import OverAllowanceError
import frappe
from frappe import _

from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form, now

class StatusUpdater(Document):
    """
    Updates the status of the calling records
    Delivery Note: Update Delivered Qty, Update Percent and Validate over delivery
    Sales Invoice: Update Billed Amt, Update Percent and Validate over billing
    Installation Note: Update Installed Qty, Update Percent Qty and Validate over installation
    """

    def update_prevdoc_status(self):
        self.update_qty()
        self.validate_qty()
	
    def validate_qty(self):
        """Validates qty at row level"""
        self.item_allowance = {}
        self.global_qty_allowance = None
        self.global_amount_allowance = None

        for args in self.status_updater:
            if "target_ref_field" not in args:
                # if target_ref_field is not specified, the programmer does not want to validate qty / amount
                continue
            
            is_child = args.get("is_child")
            if is_child:
                self._validate_children(args)
            else:
                self._validate_doctype(args)

    def _validate_children(self, args):
        # get unique transactions to update
        for d in self.get_all_children():
            if hasattr(d, "qty") and d.qty < 0 and not self.get("is_return"):
                frappe.throw(_("For an item {0}, quantity must be positive number").format(d.item_code))

            if hasattr(d, "qty") and d.qty > 0 and self.get("is_return"):
                frappe.throw(_("For an item {0}, quantity must be negative number").format(d.item_code))

            if not frappe.db.get_single_value("Selling Settings", "allow_negative_rates_for_items"):
                if hasattr(d, "item_code") and hasattr(d, "rate") and flt(d.rate) < 0:
                    frappe.throw(
                        _(
                            "For item {0}, rate must be a positive number. To Allow negative rates, enable {1} in {2}"
                        ).format(
                            frappe.bold(d.item_code),
                            frappe.bold(_("`Allow Negative rates for Items`")),
                            get_link_to_form("Selling Settings", "Selling Settings"),
                        ),
                    )

            if d.doctype == args["source_dt"] and d.get(args["join_field"]):
                args["name"] = d.get(args["join_field"])

                # get all qty where qty > target_field
                item = frappe.db.sql(
                    """select item_code, `{target_ref_field}`,
                    `{target_field}`, parenttype, parent from `tab{target_dt}`
                    where `{target_ref_field}` < `{target_field}`
                    and name=%s and docstatus=1""".format(**args),
                    args["name"],
                    as_dict=1,
                )
                if item:
                    item = item[0]
                    item["idx"] = d.idx
                    item["target_ref_field"] = args["target_ref_field"].replace("_", " ")

                    # if not item[args['target_ref_field']]:
                    # 	msgprint(_("Note: System will not check over-delivery and over-booking for Item {0} as quantity or amount is 0").format(item.item_code))
                    if args.get("no_allowance"):
                        item["reduce_by"] = item[args["target_field"]] - item[args["target_ref_field"]]
                        if item["reduce_by"] > 0.01:
                            self.limits_crossed_error(args, item, "qty")

                    elif item[args["target_ref_field"]]:
                        self.check_overflow_with_allowance(item, args)

    def _validate_doctype(self, args):
        if self.get(args["join_field"]):
            args["name"] = self.get(args["join_field"])

            # get all qty where qty > target_field
            item = frappe.db.sql(
                """select item_code, `{target_ref_field}`,
                `{target_field}`, parenttype, parent from `tab{target_dt}`
                where `{target_ref_field}` < `{target_field}`
                and name=%s and docstatus=1""".format(**args),
                args["name"],
                as_dict=1,
            )

            if item:
                item = item[0]
                item["target_ref_field"] = args["target_ref_field"].replace("_", " ")

                # if not item[args['target_ref_field']]:
                # 	msgprint(_("Note: System will not check over-delivery and over-booking for Item {0} as quantity or amount is 0").format(item.item_code))
                if args.get("no_allowance"):
                    item["reduce_by"] = item[args["target_field"]] - item[args["target_ref_field"]]
                    if item["reduce_by"] > 0.01:
                        self.limits_crossed_error(args, item)

                elif item[args["target_ref_field"]]:
                    self.check_overflow_with_allowance(item, args)
    
                frappe.throw(str(item))
    
    def limits_crossed_error(self, args, item, qty_or_amount=""):
        """Raise exception for limits crossed"""
        if (
            self.doctype in ["Sales Invoice", "Delivery Note"]
            and qty_or_amount == "amount"
            and self.is_internal_customer
        ):
            return

        elif (
            self.doctype in ["Purchase Invoice", "Purchase Receipt"]
            and qty_or_amount == "amount"
            and self.is_internal_supplier
        ):
            return

        action_msg = ""
        if qty_or_amount == "qty":
            action_msg = _(
                'To allow over receipt / delivery, update "Over Receipt/Delivery Allowance" in Stock Settings or the Item.'
            )
        elif qty_or_amount == "amount":
            action_msg = _(
                'To allow over billing, update "Over Billing Allowance" in Accounts Settings or the Item.'
            )

        frappe.throw(
            _(
                "This document is over limit by {0} {1} for item {4}. Are you making another {3} against the same {2}?"
            ).format(
                frappe.bold(_(item["target_ref_field"].title())),
                frappe.bold(item["reduce_by"]),
                frappe.bold(_(args.get("target_parent_dt"))),
                frappe.bold(_(self.doctype)),
                frappe.bold(item.get("item_code")),
            )
            + "<br><br>"
            + action_msg,
            OverAllowanceError,
            title=_("Limit Crossed"),
        )

    def update_qty(self, update_modified=True):
        """Updates qty or amount at row level

        :param update_modified: If true, updates `modified` and `modified_by` for target parent doc
        """
        for args in self.status_updater:
            # condition to include current record (if submit or no if cancel)
            is_submit = self.docstatus == 1
            is_child = args.get("is_child")

            if self.docstatus == 1:
                args["cond"] = " or %s='%s'" % ('parent' if is_child else 'name',self.name.replace('"', '"'))
            else:
                args["cond"] = " and %s!='%s'" % ('parent' if is_child else 'name',self.name.replace('"', '"'))

            if is_child:
                self._update_children(args, update_modified)
            else:
                self._update_doctype(args, update_modified)
                
            if "percent_join_field" in args or "percent_join_field_parent" in args:
                self._update_percent_field_in_targets(args, update_modified)

    def _update_doctype(self, args, update_modified):
        """Update quantities or amount in table"""
        args["source_dt"] = self.doctype

        self._update_modified(args, update_modified)

        # updates qty in the child table
        args["detail_id"] = self.get(args["join_field"])

        args["second_source_condition"] = ""

        if args["detail_id"]:
            if not args.get("extra_cond"):
                args["extra_cond"] = ""

            args["source_dt_value"] = (
                frappe.db.sql(
                    """
                    (select ifnull(sum({source_field}), 0)
                        from `tab{source_dt}` where `{join_field}`='{detail_id}'
                        and (docstatus=1 {cond}) {extra_cond})
            """.format(**args)
                )[0][0]
                or 0.0
            )

            if args["second_source_condition"]:
                args["source_dt_value"] += flt(args["second_source_condition"])

            frappe.db.sql(
                """update `tab{target_dt}`
                set {target_field} = {source_dt_value} {update_modified}
                where name='{detail_id}'""".format(**args)
            )
    
    def _update_percent_field_in_targets(self, args, update_modified=True):
        """Update percent field in parent transaction"""
        if args.get("percent_join_field_parent"):
            # if reference to target doc where % is to be updated, is
            # in source doc's parent form, consider percent_join_field_parent
            args["name"] = self.get(args["percent_join_field_parent"])
            self._update_percent_field(args, update_modified)
        else:
            distinct_transactions = set(
                d.get(args["percent_join_field"]) for d in self.get_all_children(args["source_dt"])
            )

            for name in distinct_transactions:
                if name:
                    args["name"] = name
                    self._update_percent_field(args, update_modified)

    def _update_percent_field(self, args, update_modified=True):
        """Update percent field in parent transaction"""

        self._update_modified(args, update_modified)

        if args.get("target_parent_field"):
            frappe.db.sql(
                """update `tab{target_parent_dt}`
                set {target_parent_field} = round(
                    ifnull((select
                        ifnull(sum(case when abs({target_ref_field}) > abs({target_field}) then abs({target_field}) else abs({target_ref_field}) end), 0)
                        / sum(abs({target_ref_field})) * 100
                    from `tab{target_dt}` where parent='{name}' and parenttype='{target_parent_dt}' having sum(abs({target_ref_field})) > 0), 0), 6)
                    {update_modified}
                where name='{name}'""".format(**args)
            )

            # update field
            if args.get("status_field"):
                frappe.db.sql(
                    """update `tab{target_parent_dt}`
                    set {status_field} = (case when {target_parent_field}<0.001 then 'Not {keyword}'
                    else case when {target_parent_field}>=99.999999 then 'Fully {keyword}'
                    else 'Partly {keyword}' end end)
                    where name='{name}'""".format(**args)
                )

            if update_modified:
                target = frappe.get_doc(args["target_parent_dt"], args["name"])
                target.set_status(update=True)
                target.notify_update()
                               
    def _update_modified(self, args, update_modified):
        if not update_modified:
            args["update_modified"] = ""
            return

        args["update_modified"] = ", modified = {}, modified_by = {}".format(
            frappe.db.escape(now()), frappe.db.escape(frappe.session.user)
        )