# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import parse_json

from frappe.model.document import Document

class KriteriaDokumenFinance(Document):
	def autoname(self):
		self.name = self.dokumen_finance
		if self.criteria_type:
			self.name += "-" + self.criteria_type

def create_kriteria_upload_document(self, method):
	if self.doctype == "DocType" or frappe.db.exists("Kriteria Upload Document", {"voucher_type": self.doctype, "voucher_no": self.name}):
		return

	# skip kalau Delivery Note punya timbangan_ref
	if self.doctype == "Delivery Note" and self.timbangan_ref:
		return

	kriteria_type = self.run_method("document_kriteria")
	if not isinstance(kriteria_type, str):
		kriteria_type = None

	entries = get_criteria(self.doctype, self.name, kriteria_type, True)
	if entries:
		create_kriteria_document(entries, self)

def delete_kriteria_upload_document(self, method):
	kud_list = frappe.get_all(
		"Kriteria Upload Document",
		filters={"voucher_type": self.doctype, "voucher_no": self.name},
	)
	
	for kud in kud_list:
		frappe.delete_doc("Kriteria Upload Document", kud.name)

def validate_mandatory_document(self, method):
	# skip jika doctype tidak memiliki document kriteria
	if not frappe.db.exists("Kriteria Dokumen Finance", {"dokumen_finance": self.doctype}) or frappe.flags.skip_validate_file:
		return
	
	parent = frappe.qb.DocType("Kriteria Upload Document")
	child = frappe.qb.DocType("Kriteria Upload Dokumen Finance")

	missing_documents = (
		frappe.qb.from_(parent)
		.inner_join(child)
		.on(parent.name == child.parent)
		.select(
			child.rincian_dokumen_finance,
			child.upload_file,
		)
		.where(
			(parent.voucher_type == self.doctype) &
			(parent.voucher_no == self.name) &
			(child.mandatory == 1) &
			(IfNull(child.upload_file, "") == "")
		)
		.for_update()
	).run()		

	if missing_documents:
		frappe.throw(
			_("List of mandatory documents to be filled out prior to submission: <br> {0}").format(
				"<br>".join([d[0] for d in missing_documents])
			),
			title=_("Mandatory Document")
		)
	
@frappe.whitelist()
def add_criteria(entries, document_no, doc, do_not_save=False):
	if isinstance(entries, str):
		entries = parse_json(entries)

	if isinstance(doc, str):
		doc = parse_json(doc)

	if frappe.db.exists("Kriteria Upload Document", document_no):
		sb_doc = update_kriteria_document(document_no, entries, doc)
	else:
		sb_doc = create_kriteria_document(
			entries, doc, do_not_save=do_not_save
		)

	return sb_doc

def update_kriteria_document(document_no, entries, doc):
	doc = frappe.get_doc("Kriteria Upload Document", document_no)
	doc.set("file_upload", [])

	for row in entries:
		row = frappe._dict(row)
		doc.append(
			"file_upload",
			{
				"rincian_dokumen_finance": row.rincian_dokumen_finance,
				"upload_file": row.upload_file,
				"mandatory": row.mandatory
			},
		)

	doc.save(ignore_permissions=True)

	frappe.msgprint(_("Kriteria Document updated"), alert=True)

	return doc

def create_kriteria_document(entries, doc, do_not_save=False):

	if not doc.doctype:
		return

	doc = frappe.get_doc(
		{
			"doctype": "Kriteria Upload Document",
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
		}
	)

	for row in entries:
		row = frappe._dict(row)
		
		doc.append(
			"file_upload",
			{
				"rincian_dokumen_finance": row.rincian_dokumen_finance,
				"upload_file": row.upload_file,
				"mandatory": row.mandatory
			},
		)

	doc.save()

	# if do_not_save:
	# 	frappe.db.set_value(child_row.doctype, child_row.name, "serial_and_batch_bundle", doc.name)

	frappe.msgprint(_("Kriteria Document created"), alert=True)

	return doc

@frappe.whitelist()
def get_criteria(voucher_type, voucher_no, doucment_type=None, only_kriteria=False):
	kriteria_doc = frappe.db.get_value("Kriteria Upload Document", {"voucher_type": voucher_type, "voucher_no": voucher_no}, "name")
	if not kriteria_doc:
		parent = frappe.qb.DocType("Kriteria Dokumen Finance")
		child = frappe.qb.DocType("Kriteria Satuan Dokumen Finance")

		kriteria = (
			frappe.qb.from_(parent)
			.inner_join(child)
			.on(parent.name == child.parent)
			.select(
				child.rincian_dokumen_finance,
				child.mandatory,
			)
			.where(
				(parent.dokumen_finance == voucher_type)
			)
			.orderby(child.idx)
		)

		if doucment_type:
			kriteria = kriteria.where(parent.criteria_type == doucment_type)

		kriteria = kriteria.run(as_dict=True)
	else:
		kriteria = frappe.get_all("Kriteria Upload Dokumen Finance", 
			filters={"parent": kriteria_doc}, 
			fields=["name", "rincian_dokumen_finance", "upload_file", "mandatory"],
			order_by="idx"
		)

	if only_kriteria:
		return kriteria

	return {"document_no": kriteria_doc, "kriteria": kriteria}

@frappe.whitelist()
def update_criteria_type(voucher_type, voucher_no, document_type):
	# Find existing Kriteria Upload Document
	existing = frappe.db.get_value(
		"Kriteria Upload Document",
		{"voucher_type": voucher_type, "voucher_no": voucher_no},
		"name"
	)

	if not existing:
		return {"status": "no_document"}

	parent_name = frappe.db.get_value(
		"Kriteria Dokumen Finance",
		{"criteria_type": document_type},
		"name"
	)

	if not parent_name:
		frappe.throw(f"No Kriteria Dokumen Finance found for criteria_type: {document_type}")

	# Then fetch child rows from that parent
	new_criteria = frappe.db.get_all(
		"Kriteria Satuan Dokumen Finance",
		filters={"parent": parent_name},
		fields=["rincian_dokumen_finance", "mandatory"],
		order_by="idx"
	)
	
	if not new_criteria:
		frappe.throw(f"No criteria template found for type: {document_type}")

	doc = frappe.get_doc("Kriteria Upload Document", existing)

	# Preserve existing uploaded files by matching rincian_dokumen_finance
	existing_files = {
		row.rincian_dokumen_finance: row.upload_file
		for row in doc.file_upload
		if row.upload_file
	}

	# Rebuild file_upload child table with new criteria
	doc.file_upload = []
	doc.document_type = document_type

	for criteria_row in new_criteria:
		doc.append("file_upload", {
			"rincian_dokumen_finance": criteria_row.rincian_dokumen_finance,
			"mandatory": criteria_row.mandatory,
			# Re-attach file if same criteria name existed before
			"upload_file": existing_files.get(criteria_row.rincian_dokumen_finance, None)
		})

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"status": "updated", "document_type": document_type}