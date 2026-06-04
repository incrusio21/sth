import frappe

def on_payment_entry_submit(doc, method=None):
	"""
	Setelah Payment Entry di-submit:
	  - Jika tipe_transfer == 'LEASING' dan transaksi_berulang & leasing_row_idx terisi
	  - Update baris leasing yang dipilih:
			no_transaksi_kas_bank = doc.name
			status_bayar          = 'Sudah Dibayar'
	"""
	if (doc.get("tipe_transfer") or "").upper() != "LEASING":
		return

	transaksi_berulang = doc.get("transaksi_berulang")
	leasing_row_idx    = doc.get("leasing_row_idx")

	if not transaksi_berulang or not leasing_row_idx:
		frappe.log_error(
			f"Payment Entry {doc.name} bertipe LEASING tetapi "
			f"transaksi_berulang={transaksi_berulang!r} / "
			f"leasing_row_idx={leasing_row_idx!r} kosong — baris leasing tidak diupdate.",
			"PE LEASING – field tidak lengkap",
		)
		return

	leasing_row_idx = int(leasing_row_idx)

	tb_doc = frappe.get_doc("Transaksi Berulang", transaksi_berulang)

	updated = False
	for row in tb_doc.transaksi_berulang_leasing_table:
		if row.idx == leasing_row_idx:
			row.no_transaksi_kas_bank = doc.name
			row.status_bayar          = "Sudah Dibayar"
			updated = True
			break

	if not updated:
		frappe.log_error(
			f"idx={leasing_row_idx} tidak ditemukan di leasing table "
			f"dokumen {transaksi_berulang} (PE: {doc.name})",
			"PE LEASING – baris tidak ditemukan",
		)
		return

	tb_doc.save(ignore_permissions=True)

	frappe.logger().info(
		f"[PE LEASING] {doc.name} → {transaksi_berulang} "
		f"(idx={leasing_row_idx}) status_bayar=Sudah Dibayar, "
		f"no_transaksi_kas_bank={doc.name}"
	)


def on_payment_entry_cancel(doc, method=None):
	"""
	Jika Payment Entry dibatalkan:
	  - Kembalikan status_bayar → 'Belum Dibayar'
	  - Kosongkan no_transaksi_kas_bank
	"""
	if (doc.get("tipe_transfer") or "").upper() != "LEASING":
		return

	transaksi_berulang = doc.get("transaksi_berulang")
	leasing_row_idx    = doc.get("leasing_row_idx")

	if not transaksi_berulang or not leasing_row_idx:
		return

	leasing_row_idx = int(leasing_row_idx)

	tb_doc = frappe.get_doc("Transaksi Berulang", transaksi_berulang)

	for row in tb_doc.transaksi_berulang_leasing_table:
		if row.idx == leasing_row_idx:
			row.no_transaksi_kas_bank = None
			row.status_bayar          = "Belum Dibayar"
			break

	tb_doc.save(ignore_permissions=True)

	frappe.logger().info(
		f"[PE LEASING] Cancel {doc.name} → {transaksi_berulang} "
		f"(idx={leasing_row_idx}) dikembalikan ke Belum Dibayar"
	)