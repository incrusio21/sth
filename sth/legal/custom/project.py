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
                self.validate_spk_type()
                self.validate_order_adendum()
                self.set_note()
            case "on_update":
                self.validate_and_update_project()
                self.move_task_to_new_project()
                self.validate_proposal()
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

    def validate_spk_type(self):
        # jika document baru tidak perlu ada pengecekan
        before_doc = self.doc.get_latest()
        if not before_doc:
            return
        
        if before_doc.spk_type != self.doc.spk_type:
            frappe.throw("Proposal Type cannot be change")

    def validate_order_adendum(self):
        if self.doc.project_type != "Adendum" or self.doc.spk_type != "Transaction":
            return
        
        # get proposal dari adendum
        new_po = frappe.get_value("Proposal", {"from_proposal": self.doc.last_proposal, "docstatus": 1}, "name")
        if not new_po:
            frappe.throw(f"Please create new Proposal for Project {self.doc.project_type} first")

        self.doc.proposal = new_po

    def set_note(self):
        if not self.doc.is_new() and self.doc.for_proposal and not self.doc.proposal:
            return
        
        from frappe.utils.formatters import format_value
        
        po_i = frappe.qb.DocType("Proposal Item")
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
            ).where(po_i.parent == self.doc.proposal)
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
        
    def validate_proposal(self):
        # jika bukan untuk proposal. hapus purchase order
        if not self.doc.for_proposal:
            self.doc.proposal = None
        
        before_save = self.doc.get_latest()
        # pastikan purchase order pada project tidak boleh berubah
        if (
            before_save and 
            before_save.proposal and 
            before_save.proposal != self.doc.proposal
        ):
            frappe.throw(_("No changes allowed to Proposal"))

    def create_task_by_order(self):
        # skip create task jika tidak terdapat data po atau task sudah ada
        if not self.doc.proposal or frappe.db.exists("Task", {"proposal": self.doc.proposal}):
            return
        
        po = frappe.get_doc("Proposal", self.doc.proposal)

        # jika po bukan submit atau bukan merupakan check progress
        if po.docstatus != 1:
            frappe.throw(f"Unable to create project from Proposal {self.doc.proposal}")

        for item in po.items:
            task = frappe.new_doc("Task")

            task.update({
                "subject": frappe.get_cached_value("Kegiatan", item.kegiatan, "nm_kgt"),
                "project": self.doc.name,
                "proposal": self.doc.proposal,
                "proposal_item": item.name,
                "progress": flt(item.progress_received/item.qty*100)
            })

            task.save()


@frappe.whitelist()
def get_proposal_data(proposal):
    detail_proposal = frappe.get_value("Proposal", proposal, ["spesifikasi_kerja", "keperluan", "jangka_waktu", "denda"], as_dict=1)

    detail_proposal["identifications"] = frappe.get_all("Proposal Identification Detail", 
        filters={"parent": proposal, "parenttype": "Proposal"}, 
        fields=["identification", "available", "not_available"],
        order_by="idx"
    ) or {}

    return detail_proposal


@frappe.whitelist()
def make_project_adendum(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.project_type = "Adendum"
        target.last_proposal = source.proposal or source.last_proposal

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