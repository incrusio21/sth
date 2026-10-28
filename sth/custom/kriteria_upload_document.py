import frappe

def update_status_surat_menyurat(doc, method=None):
	if doc.voucher_type != "Surat Menyurat" or not doc.voucher_no:
		return

	sudah_upload = any(row.upload_file for row in doc.get("file_upload") or [])
	frappe.db.set_value(
		"Surat Menyurat",
		doc.voucher_no,
		"status",
		"Sudah Upload" if sudah_upload else "Belum Upload",
	)