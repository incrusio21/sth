import frappe
from frappe.model.naming import getseries
from frappe import _

def set_unit_from_parent(doc, method):

	if not doc.voucher_type or not doc.voucher_no:
		return

	try:
		parent = frappe.get_doc(doc.voucher_type, doc.voucher_no)
	except:
		return

	if hasattr(parent, "unit"):
		doc.unit = parent.unit

GL_SERIES_KEY = "GL-."


def autoname_gl_entry(doc, method=None):
    # Nomor diambil dari counter di `tabSeries`, bukan dari MAX(`tabGL Entry`).
    # getseries() melakukan SELECT ... FOR UPDATE lalu UPDATE current = current + 1,
    # jadi nilainya selalu versi terbaru yang ter-commit dan row lock-nya ditahan
    # sampai transaksi selesai -- request paralel antre di sini, tidak bisa dobel.
    doc.name = "GL-" + getseries(GL_SERIES_KEY, 8)



def patch_unit_gl_entry():

	start = 0
	batch_size = 1000

	while True:

		entries = frappe.get_all(
			"GL Entry",
			filters={"unit": ["is", "not set"]},
			fields=["name", "voucher_type", "voucher_no"],
			start=start,
			limit_page_length=batch_size
		)

		if not entries:
			break

		for e in entries:

			if not e.voucher_type or not e.voucher_no:
				continue

			try:
				parent = frappe.get_doc(e.voucher_type, e.voucher_no)
			except frappe.DoesNotExistError:
				continue

			if hasattr(parent, "unit") and parent.unit:

				frappe.db.set_value(
					"GL Entry",
					e.name,
					"unit",
					parent.unit
				)
				print(parent.name)

		frappe.db.commit()

		start += batch_size