# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
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
                self.set_missing_value()
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
        # proposal jika spk_type po/so dan sebalikny
        if self.doc.spk_type in ["PO/SO"]:
            self.purchase_order = ""
        else:
            self.proposal_type = self.proposal = ""

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

    def set_missing_value(self):
        if self.doc.supplier:
            # get data alamat dari table alamat pic
            self.doc.supplier_address, self.doc.telepon = frappe.db.get_value("Alamat dan PIC", {
                "parent": self.doc.supplier, "status_pic": "Aktif"}, ["alamat_pic", "telepon"]) or ["", ""]

             # get data user email dari table structur supplier
            self.doc.user_email = frappe.db.get_value("Struktur Supplier", {
                "parent": self.doc.supplier, "status_supplier": "Aktif"}, "user_email") or""

    def set_note(self):
        if not self.doc.is_new():
            return
        
        from frappe.utils.formatters import format_value

        doctype_name, document_name = "Proposal", self.doc.proposal
        if self.doc.spk_type == "PO/SO":
            doctype_name, document_name = "Purchase Order", self.doc.purchase_order

        po_i = frappe.qb.DocType(f"{doctype_name} Item")
        
        fields = [
            po_i.kegiatan_name if doctype_name == "Proposal" else po_i.item_name,
            po_i.qty,
            po_i.uom,
            po_i.rate,
        ]

        query = (
            frappe.qb.from_(po_i)
            .select(
                *fields
            ).where(po_i.parent == document_name)
        ).run()

        data = "<div class='ql-editor' contenteditable='true'><ol>"
        for d in query:
            data += '<li data-list="ordered">'
            data += f'<span class="ql-ui" contenteditable="false"></span>{d[0]} {format_value(d[1])} {d[2]} {format_value(d[3])}'
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
                "subject": item.kegiatan_name,
                "project": self.doc.name,
                "proposal": self.doc.proposal,
                "proposal_item": item.name,
                "progress": flt(item.progress_received/item.qty*100)
            })

            task.save()

@frappe.whitelist()
def get_proposal_data(doctype, docname=None):
    detail_proposal = {
        "company": "",
        "spesifikasi_kerja": "",
        "keperluan": "", 
        "jangka_waktu": "", 
        "denda": "",
        "identifications": {}
    }

    if docname:
        fieldname = ["company", "supplier"]
        if doctype == "Proposal":
            fieldname.append(["spesifikasi_kerja", "keperluan", "jangka_waktu", "denda"])

        detail_proposal.update(
            frappe.get_value(doctype, docname, fieldname, as_dict=1)
        )

        if doctype == "Proposal":
            detail_proposal["identifications"] = frappe.get_all(f"{doctype} Identification Detail", 
                filters={"parent": docname, "parenttype": "Proposal"}, 
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

@frappe.whitelist()
def get_contract_template(template_name, doc):
    if isinstance(doc, str):
        doc = json.loads(doc)

    contract_template = frappe.get_doc("Contract Template", template_name)
    contract_terms = contract_cover = None

    from sth.legal.utils import (
        file_image,
        get_date_number, 
        get_days_name, get_date_text, 
        get_month_number, get_month_name, 
        get_year_number, get_year_text, 
        money_to_text
    )

    context = {
        "project": doc,
        "proposal": frappe.get_doc("Proposal", doc["proposal"]) if doc.get("proposal") else {},
        "unit": frappe.get_doc("Unit", doc["unit"]) if doc.get("unit") else {},
        "day_name": get_days_name,
        "date_number": get_date_number,
        "date_text": get_date_text,
        "month_number": get_month_number,
        "month_name": get_month_name,
        "year_number": get_year_number,
        "year_text": get_year_text,
        "money_to_text": money_to_text,
        "file_image": file_image
    }

    if contract_template.contract_terms:
        contract_cover = frappe.render_template(contract_template.contract_cover, context)

    if contract_template.contract_terms:
        contract_terms = frappe.render_template(contract_template.contract_terms, context)

    return {
        "contract_template": contract_template, 
        "contract_cover": contract_cover,
        "contract_terms": contract_terms,
        "contract_footer": contract_template.contract_footer
    }

@frappe.whitelist()
def download_contract_pdf(docname):
	doc = frappe.get_doc('Project', docname)
	pdf = doc.generate_pdf()
	
	frappe.local.response.filename = f"{docname}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"