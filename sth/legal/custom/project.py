# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, today

class Project:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        match self.method:
            case "validate":
                self.validate_status_project()
                self.validate_proposal_type()
                self.validate_order_adendum()
                self.set_note()
            case "on_update":
                self.validate_and_update_project()
                self.move_task_to_new_project()
                self.validate_purchase_order()
                self.create_task_by_order()
            case "on_trash":
                self.validate_and_update_project(delete=1)
                self.move_task_to_new_project(delete=1)
    
    def validate_status_project(self):
        # jika document baru tidak perlu ada pengecekan
        before_doc = self.doc.get_latest()
        if not before_doc:
            return
        
        if before_doc.status == "Cancelled":
            frappe.throw("Cant update status Project")

        if self.doc.status == "Completed" and before_doc.status != self.doc.status:
            self.doc.complete_date = today()

    def validate_proposal_type(self):
        # jika document baru tidak perlu ada pengecekan
        before_doc = self.doc.get_latest()
        if not before_doc:
            return
        
        if before_doc.proposal_type != self.doc.proposal_type:
            frappe.throw("Proposal Type cannot be change")

    def validate_order_adendum(self):
        if self.doc.project_type != "Adendum" or self.doc.proposal_type != "Transaction":
            return
        
        # get purchase order dari adendum
        new_po = frappe.get_value("Purchase Order", {"from_order": self.doc.last_purchase_order, "docstatus": 1}, "name")
        if not new_po:
            frappe.throw(f"Please create new Purchase Order for Project {self.doc.project_type} first")

        self.doc.purchase_order = new_po

    def set_note(self):
        if not self.doc.is_new() and self.doc.for_proposal and not self.doc.purchase_order:
            return
        
        from frappe.utils.formatters import format_value
        
        po_i = frappe.qb.DocType("Purchase Order Item")
        kegiatan = frappe.qb.DocType("Kegiatan")

        query = (
            frappe.qb.from_(po_i)
            .inner_join(kegiatan)
            .on(kegiatan.name == po_i.kegiatan)
            .select(
                kegiatan.nm_kgt.as_("kegiatan"),
                po_i.qty,
                po_i.uom,
                po_i.rate,
            ).where(po_i.parent == self.doc.purchase_order)
        ).run(as_dict=1)

        data = "<div class='ql-editor' contenteditable='true'><ol>"
        for d in query:
            data += '<li data-list="ordered">'
            data += f'<span class="ql-ui" contenteditable="false"></span>{d.kegiatan} {format_value(d.qty)} {d.uom} {format_value(d.rate)}'
            data += '</li>'

        data += "</ol></div>"

        self.doc.notes = data

    def validate_and_update_project(self, delete=0):
        # paksa status selalu menjadi cancelled ketika sudah ada yang adendum
        if not delete and frappe.db.exists("Project", {"from_project": self.doc.name}):
            self.db_set("status", "Cancelled") 
        
        # jika tidak ada project awal. skip
        if not self.doc.from_project:
           return
        
        status = "Cancelled" if not delete else "Open"
        frappe.db.set_value("Project", self.doc.from_project, "status", status)

    def move_task_to_new_project(self, delete=0):
        if self.doc.project_type != "Adendum" or self.doc.proposal_type == "Transaction":
            return
        
        if not self.doc.from_project:
            frappe.throw("Can't make Adendum without SPK")

        new_project, last_project = self.doc.name, self.doc.from_project
        if delete:
            new_project, last_project = last_project, new_project

        frappe.db.sql(""" update `tabTask` set project = %s where project = %s """, (new_project, last_project))
        
    def validate_purchase_order(self):
        # jika bukan untuk proposal. hapus purchase order
        if not self.doc.for_proposal:
            self.doc.purchase_order = None
        
        before_save = self.doc.get_latest()
        # pastikan purchase order pada project tidak boleh berubah
        if (
            before_save and 
            before_save.purchase_order and 
            before_save.purchase_order != self.doc.purchase_order
        ):
            frappe.throw(_("No changes allowed to Purchase Order"))

    def create_task_by_order(self):
        # skip create task jika tidak terdapat data po atau task sudah ada
        if not self.doc.purchase_order or frappe.db.exists("Task", {"purchase_order": self.doc.purchase_order}):
            return
        
        po = frappe.get_doc("Purchase Order", self.doc.purchase_order)
        # run hanya untuk ambil key onload
        po.run_method("onload")

        # jika po bukan submit atau bukan merupakan check progress
        if po.docstatus != 1 or not po.get_onload("check_progress"):
            frappe.throw(f"Unable to create project from Purchase Order {self.doc.purchase_order}")

        subject = po.get_onload("progress_benchmark")
        for item in po.items:
            task = frappe.new_doc("Task")

            task.update({
                "subject": item.get(subject),
                "project": self.doc.name,
                "purchase_order": self.doc.purchase_order,
                "purchase_order_item": item.name,
                "progress": flt(item.progress_received/item.qty*100)
            })

            task.save()

@frappe.whitelist()
def make_project_adendum(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.project_type = "Adendum"
        target.last_purchase_order = source.purchase_order or source.last_purchase_order

    doc = get_mapped_doc(
        "Project",
        source_name,
        {
            "Project": {
                "doctype": "Project",
                "field_map": {
                    "name": "from_project"
                },
            },
        },
        target_doc,
        set_missing_values,
    )

    return doc