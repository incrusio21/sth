# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PaymentNotificationSettings(Document):
    
    def validate(self):

        if not self.document_name:
            return

        meta = frappe.get_meta(self.document_name)

        if not meta.has_field("outstanding_amount"):
            frappe.throw(
                f"DocType <b>{self.document_name}</b> tidak memiliki field <b>outstanding_amount</b>"
            )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_outstanding_doctypes(doctype, txt, searchfield, start, page_len, filters):

    settings = frappe.get_single("Payment Settings")

    allowed = []

    if settings.outstanding_doctype:
        allowed += [d.strip() for d in settings.outstanding_doctype.split("\n") if d.strip()]

    for row in settings.reference:
        if row.doctype_ref:
            allowed += [d.strip() for d in row.doctype_ref.split("\n") if d.strip()]

    allowed = list(set(allowed))

    if not allowed:
        return []

    valid_doctypes = []

    for dt in allowed:
        exists = frappe.db.exists(
            "DocField",
            {
                "parent": dt,
                "fieldname": "outstanding_amount"
            }
        )

        if exists:
            valid_doctypes.append(dt)

    if not valid_doctypes:
        return []

    return frappe.db.sql("""
        SELECT name
        FROM `tabDocType`
        WHERE name IN %(allowed)s
        AND name LIKE %(txt)s
        LIMIT %(start)s, %(page_len)s
    """, {
        "allowed": tuple(valid_doctypes),
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })


def check_outstanding_field():

    settings = frappe.get_single("Payment Settings")

    doctypes = []

    if settings.outstanding_doctype:
        doctypes += [d.strip() for d in settings.outstanding_doctype.split("\n") if d.strip()]

    for row in settings.reference:
        if row.doctype_ref:
            doctypes += [d.strip() for d in row.doctype_ref.split("\n") if d.strip()]

    doctypes = list(set(doctypes))

    result = []

    for dt in doctypes:

        exists = frappe.db.exists(
            "DocField",
            {
                "parent": dt,
                "fieldname": "outstanding_amount"
            }
        )

        result.append({
            "doctype": dt,
            "has_outstanding_amount": bool(exists)
        })

    return result