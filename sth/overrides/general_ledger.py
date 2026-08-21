import frappe
from erpnext.accounts.doctype.accounting_period.accounting_period import ClosedAccountingPeriod
from erpnext.accounts.general_ledger import validate_accounting_period as _validate_accounting_period
from frappe import _

def validate_accounting_period(gl_map):
	cek_doc = frappe.get_doc(gl_map[0].voucher_type, gl_map[0].voucher_no)
	if cek_doc:
		accounting_periods = frappe.db.sql(
			""" SELECT
				ap.name as name
			FROM
				`tabAccounting Period` ap, `tabClosed Document` cd
			WHERE
				ap.name = cd.parent
				AND ap.company = %(company)s
				AND cd.closed = 1
				AND cd.document_type = %(voucher_type)s
				AND %(date)s between ap.start_date and ap.end_date
				AND ap.unit = %(unit)s
				AND ap.workflow_state = "Submitted"
				""",
			{
				"date": gl_map[0].posting_date,
				"company": gl_map[0].company,
				"voucher_type": gl_map[0].voucher_type,
				"unit": cek_doc.get("unit")
			},
			as_dict=1,
		)

		if accounting_periods:
			# unit di GL Entry tidak selalu terisi — voucher yang menjurnal langsung
			# lewat make_gl_entries kerap melewatkannya. yang dipakai unit dokumennya
			# supaya pesannya menyebut unit yang benar, bukan kosong
			unit = gl_map[0].get("unit") or cek_doc.get("unit") or "-"

			frappe.throw(
				_(
					"You cannot create or cancel any accounting entries with in the closed Accounting Period {0} for unit {1}"
				).format(frappe.bold(accounting_periods[0].name), frappe.bold(unit)),
				ClosedAccountingPeriod,
			)

