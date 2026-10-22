import frappe

PARTY_TYPE = "Daftar Masyarakat"
REFERENCE_DOCTYPE = "Ganti Rugi Lahan"


def execute():
	"""Daftar Masyarakat jadi party Payment Entry pembayaran Ganti Rugi Lahan.

	Sebelumnya PE GRL dibayarkan atas nama Employee internal, padahal uangnya
	diterima pemilik lahan. Party Type dibuat supaya pemilik lahan bisa dipilih
	di field party, dan baris Payment Settings supaya Ganti Rugi Lahan sah
	sebagai referensi untuk party itu (lihat get_valid_reference_doctypes di
	sth/overrides/payment_entry.py).

	Account type Payable cuma syarat Party Type: PE GRL mendebit akun aset GRL
	milik Company, bukan akun hutang, jadi party-nya tidak ikut ke jurnal.
	"""
	if not frappe.db.exists("Party Type", PARTY_TYPE):
		frappe.get_doc({
			"doctype": "Party Type",
			"party_type": PARTY_TYPE,
			"account_type": "Payable",
		}).insert(ignore_permissions=True)

	settings = frappe.get_single("Payment Settings")
	row = next((d for d in settings.get("reference") if d.party_type == PARTY_TYPE), None)
	if row:
		if REFERENCE_DOCTYPE in (row.doctype_ref or "").split("\n"):
			return

		row.doctype_ref = "\n".join(filter(None, [row.doctype_ref, REFERENCE_DOCTYPE]))
	else:
		settings.append("reference", {"party_type": PARTY_TYPE, "doctype_ref": REFERENCE_DOCTYPE})

	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)
