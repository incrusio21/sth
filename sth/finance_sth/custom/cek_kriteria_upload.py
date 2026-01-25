import frappe
from frappe import _

def cek_dokumen_before_submit(doc, method=None):
	validate_mandatory_documents(doc)

def cek_dokumen_setelah_insert(doc, method=None):
	populate_kriteria_upload(doc)

def populate_kriteria_upload(doc):
	if not hasattr(doc, 'kriteria_upload_dokumen_finance'):
		return

	criteria = frappe.db.get_value(
		"Kriteria Dokumen Finance",
		{"dokumen_finance": doc.doctype},
		"name"
	)
	
	if not criteria:
		doc.kriteria_upload_dokumen_finance = []
		return
	
	kriteria_items = frappe.get_all(
		"Kriteria Satuan Dokumen Finance",
		filters={
			"parent": criteria,
			"aktif": 1
		},
		fields=["rincian_dokumen_finance", "mandatory"],
		order_by="idx"
	)
	
	if not kriteria_items:
		return

	existing_uploads = {}
	if hasattr(doc, 'kriteria_upload_dokumen_finance'):
		for row in doc.kriteria_upload_dokumen_finance:
			existing_uploads[row.rincian_dokumen_finance] = row.upload_file

	doc.kriteria_upload_dokumen_finance = []
	
	for idx, item in enumerate(kriteria_items, start=1):
		upload_file = existing_uploads.get(item.rincian_dokumen_finance, None)
		
		if doc.doctype != "Supplier":
			doc.append("kriteria_upload_dokumen_finance", {
				"rincian_dokumen_finance": item.rincian_dokumen_finance,
				"upload_file": upload_file,
				"mandatory": item.mandatory, 
				"idx": idx
			})
		else:
			if doc.badan_usaha == "Perorangan":
				if item.rincian_dokumen_finance in ["Cover Rekening", "NPWP","KTP Pemilik", "Form Supplier"]:
					doc.append("kriteria_upload_dokumen_finance", {
						"rincian_dokumen_finance": item.rincian_dokumen_finance,
						"upload_file": upload_file,
						"mandatory": item.mandatory, 
					})
			elif doc.badan_usaha == "Koperasi":
				if item.rincian_dokumen_finance in ["Akta", "Cover Rekening", "NPWP","KTP Pemilik", "Form Supplier"]:
					doc.append("kriteria_upload_dokumen_finance", {
						"rincian_dokumen_finance": item.rincian_dokumen_finance,
						"upload_file": upload_file,
						"mandatory": item.mandatory, 
					})
			else:
				cek_sppkp = 0

				if doc.npwp_dan_sppkp_supplier:
					for row in doc.npwp_dan_sppkp_supplier:
						if row.status_pkp == 1:
							cek_sppkp = 1

				if cek_sppkp == 1 and item.rincian_dokumen_finance == "SPPKP":
					doc.append("kriteria_upload_dokumen_finance", {
						"rincian_dokumen_finance": item.rincian_dokumen_finance,
						"upload_file": upload_file,
						"mandatory": item.mandatory, 
						"idx": idx
					})
				elif cek_sppkp == 0 and item.rincian_dokumen_finance != "SPPKP":
					doc.append("kriteria_upload_dokumen_finance", {
						"rincian_dokumen_finance": item.rincian_dokumen_finance,
						"upload_file": upload_file,
						"mandatory": item.mandatory, 
						"idx": idx
					})
				elif cek_sppkp == 1 and item.rincian_dokumen_finance != "SPPKP":
					doc.append("kriteria_upload_dokumen_finance", {
						"rincian_dokumen_finance": item.rincian_dokumen_finance,
						"upload_file": upload_file,
						"mandatory": item.mandatory, 
						"idx": idx
					})


def validate_mandatory_documents(doc):

	if not hasattr(doc, 'kriteria_upload_dokumen_finance'):
		return
	
	missing_documents = []
	
	for row in doc.kriteria_upload_dokumen_finance:
		if row.get("mandatory") and not row.get("upload_file"):
			missing_documents.append(row.rincian_dokumen_finance)
	
	if missing_documents:
		frappe.throw(
			_("Dokumen wajib berikut harus dilampirkan sebelum submit: {0}").format(
				", ".join(missing_documents)
			),
			title=_("Dokumen Wajib Tidak Lengkap")
		)

# DAFTAR KRITERIA FINANCE YANG BUTUH UPLOAD
# QUOTATION - SALES ORDER - DELIVERY NOTE - SALES INVOICE
# REQUEST FOR QUOTATION - SUPPLIER QUOTATION - PURCHASE ORDER - PURCHASE RECEIPT - PURCHASE INVOICE
# DUNNING - DEPOSITO INTEREST
# Pengajuan Panen Kontanan
# Transaksi Bonus
# Transaksi THR
# Perhitungan Kompensasi PHK
# Ganti Rugi Lahan
# Pengajuan Pembayaran
# PDO Bahan Bakar Vtwo
# PDO Perjalanan Dinas Vtwo
# PDO Kas Vtwo
# PDO Dana Cadangan Vtwo
# PDO NON PDO Vtwo
# Deposito Interest
# BPJS TK
# BPJS KES
# Deposito
# Expense Claim
# Employee Advance
# Leave Encashment
# Journal Entry
# Pengajuan Panen Kontanan
# Transaksi Bonus
# Transaksi THR
# Perhitungan Kompensasi PHK
# Ganti Rugi Lahan
# Pengajuan Pembayaran
# PDO Bahan Bakar Vtwo
# PDO Perjalanan Dinas Vtwo
# PDO Kas Vtwo
# PDO Dana Cadangan Vtwo
# PDO NON PDO Vtwo
# BPJS TK
# BPJS KES