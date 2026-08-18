import frappe

DOCTYPE = "Asset Scrap Request"
STATE_DRAFT = "Draft"


def execute():
	"""Isi state awal pengajuan scrap yang terlanjur dibuat tanpa state.

	Pengajuan yang dibuat langsung dari doctype-nya — bukan lewat tombol di form
	Asset — berangkat tanpa workflow_state selama state awalnya belum dipasang.
	Dokumen seperti itu tidak bisa dibuka sama sekali: formnya meminta daftar
	transisi, dan frappe menolaknya dengan "Workflow State not set".

	Yang diisi cuma yang masih draft. Dokumen ber-docstatus lain tidak mungkin
	kosong statenya, karena satu-satunya jalan ke sana lewat transisi workflow.
	"""
	if not frappe.get_meta(DOCTYPE).has_field("workflow_state"):
		return

	frappe.db.sql("""
		UPDATE `tabAsset Scrap Request`
		SET workflow_state = %(draft)s
		WHERE docstatus = 0
			AND (workflow_state IS NULL OR workflow_state = '')
	""", {"draft": STATE_DRAFT})
