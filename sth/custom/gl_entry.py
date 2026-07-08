import frappe
from frappe.model.naming import make_autoname
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

def autoname_gl_entry(doc, method=None):
    # Ensure the series row exists
    frappe.db.sql(
        "INSERT IGNORE INTO `tabSeries` (name, current) VALUES ('GL-.', 0)"
    )

    # Lock the series row so concurrent inserts queue up here
    frappe.db.sql(
        "SELECT current FROM `tabSeries` WHERE name = 'GL-.' FOR UPDATE"
    )

    # Read the real max from the table — fills gaps left by deletions
    last = frappe.db.sql(
        """SELECT COALESCE(MAX(CAST(SUBSTRING(name, 4) AS UNSIGNED)), 0)
           FROM `tabGL Entry`
           WHERE name REGEXP '^GL-[0-9]{8}$'"""
    )[0][0]

    next_num = int(last) + 1

    # Keep tabSeries in sync (useful for monitoring / manual checks)
    frappe.db.sql(
        "UPDATE `tabSeries` SET current = %s WHERE name = 'GL-.'",
        (next_num,),
    )

    doc.name = "GL-{:08d}".format(next_num)



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