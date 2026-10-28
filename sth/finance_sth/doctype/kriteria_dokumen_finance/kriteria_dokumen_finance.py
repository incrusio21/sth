# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import parse_json
from frappe.model.workflow import get_workflow_name

from frappe.model.document import Document

CACHE_DOCTYPE_BERKRITERIA = "sth:doctype_berkriteria"

class KriteriaDokumenFinance(Document):
	def autoname(self):
		self.name = self.dokumen_finance
		if self.criteria_type:
			self.name += "-" + self.criteria_type

	def on_update(self):
		frappe.cache.delete_value(CACHE_DOCTYPE_BERKRITERIA)

	def on_trash(self):
		frappe.cache.delete_value(CACHE_DOCTYPE_BERKRITERIA)

	def after_rename(self, old, new, merge=False):
		frappe.cache.delete_value(CACHE_DOCTYPE_BERKRITERIA)

def doctype_berkriteria():
	"""Doctype yang punya Kriteria Dokumen Finance, disimpan di cache.

	create_kriteria_upload_document dipasang di on_update semua doctype, jadi
	ikut jalan untuk tiap GL Entry, Stock Ledger Entry dan sejenisnya. Doctype
	tanpa kriteria tidak pernah mendapat Kriteria Upload Document — get_criteria
	menyaring lewat dokumen_finance — jadi cukup ditolak di depan tanpa query.
	Dulu tiap GL Entry menjalankan dua scan penuh tabKriteria Upload Document,
	dan posting BKM saat Accounting Period disubmit habis di sana.
	"""
	return frappe.cache.get_value(
		CACHE_DOCTYPE_BERKRITERIA,
		lambda: set(frappe.get_all("Kriteria Dokumen Finance", pluck="dokumen_finance", distinct=True)),
	)

def create_kriteria_upload_document(self, method):
	if self.doctype not in doctype_berkriteria():
		return

	if self.doctype == "DocType" or frappe.db.exists("Kriteria Upload Document", {"voucher_type": self.doctype, "voucher_no": self.name}):
		return

	# skip kalau Delivery Note atau Sales Invoice punya timbangan_ref: berkasnya
	# disalin dari Timbangan (create_kriteria_upload_document di custom/delivery_note)
	if self.doctype in ("Delivery Note", "Sales Invoice") and self.get("timbangan_ref"):
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

def validate_mandatory_document_workflow(self, method):
	"""Dokumen ber-workflow dicek saat meninggalkan state awal workflow-nya (Draft
	ke Butuh Persetujuan 1, atau aksi pertama approver kalau workflow-nya langsung
	mulai di Butuh Persetujuan 1), bukan saat submit. Submit dijalankan approval
	terakhir, yaitu direksi, yang tidak semestinya mengurus berkas. Menolak ke
	Rejected tidak dicek.
	"""
	if self.doctype not in doctype_berkriteria() or frappe.flags.skip_validate_file:
		return

	workflow_name = get_workflow_name(self.doctype)
	before = self.get_doc_before_save()
	if not workflow_name or not before:
		return

	workflow = frappe.get_cached_doc("Workflow", workflow_name)
	lama = before.get(workflow.workflow_state_field)
	baru = self.get(workflow.workflow_state_field)
	if lama == baru or (lama and lama != workflow.states[0].state):
		return
	if (baru or "").startswith("Reject"):
		return

	cek_mandatory_document(self)

def validate_mandatory_document(self, method):
	# skip jika doctype tidak memiliki document kriteria
	if not frappe.db.exists("Kriteria Dokumen Finance", {"dokumen_finance": self.doctype}) or frappe.flags.skip_validate_file:
		return

	# Dokumen ber-workflow sudah dicek di validate_mandatory_document_workflow.
	if get_workflow_name(self.doctype):
		return

	cek_mandatory_document(self)

def cek_mandatory_document(self):
	
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

	# Baris mandatory tidak boleh dihapus dari popup
	sisa_kriteria = {frappe._dict(row).rincian_dokumen_finance for row in entries}
	mandatory_hilang = [
		row.rincian_dokumen_finance
		for row in doc.get("file_upload")
		if row.mandatory and row.rincian_dokumen_finance not in sisa_kriteria
	]
	if mandatory_hilang:
		frappe.throw(
			_("Mandatory document cannot be removed: <br> {0}").format("<br>".join(mandatory_hilang)),
			title=_("Mandatory Document")
		)

	# Ambil mapping file lama: rincian_dokumen_finance -> upload_file
	old_files = {
		row.rincian_dokumen_finance: row.upload_file
		for row in doc.get("file_upload")
		if row.upload_file
	}
	
	# Bandingkan dengan entries baru, hapus file yang diganti
	for row in entries:
		row = frappe._dict(row)
		old_file = old_files.get(row.rincian_dokumen_finance)
		new_file = row.upload_file
		
		if old_file and new_file and old_file != new_file:
			# File diganti, hapus yang lama
			try:
				file_doc = frappe.get_doc("File", {"file_url": old_file})
				file_doc.delete(ignore_permissions=True)
			except frappe.DoesNotExistError:
				pass  # File sudah tidak ada, skip
	
	# Lanjut proses seperti biasa
	doc.set("file_upload", [])
	for row in entries:
		row = frappe._dict(row)
		doc.append(
			"file_upload",
			{
				"rincian_dokumen_finance": row.rincian_dokumen_finance,
				"upload_file": row.upload_file,
				"mandatory": row.mandatory,
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

	if doc.doctype == "Surat Menyurat":
		frappe.set_value("Surat Menyurat", doc.name, "status", "Sudah Upload" if any(row.upload_file for row in doc.get("file_upload") or []) else "Belum Upload")

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