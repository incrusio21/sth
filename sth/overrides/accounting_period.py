import frappe
from frappe.utils import cint, flt
from frappe import _, bold
from erpnext.accounts.doctype.accounting_period.accounting_period import (
	AccountingPeriod,
	OverlapError,
	ClosedAccountingPeriod
)

class SthAccountingPeriod(AccountingPeriod):

	def autoname(self):
		company_abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = " - ".join([self.period_name, company_abbr])

	def validate(self):
		self.validate_overlap()

	def validate_overlap(self):
		existing_accounting_period = frappe.db.sql(
			"""select name, unit from `tabAccounting Period`
			where (
				(%(start_date)s between start_date and end_date)
				or (%(end_date)s between start_date and end_date)
				or (start_date between %(start_date)s and %(end_date)s)
				or (end_date between %(start_date)s and %(end_date)s)
			) and name!=%(name)s and company=%(company)s
			and unit = %(unit)s
			""",
			{
				"start_date": self.start_date,
				"end_date": self.end_date,
				"name": self.name,
				"company": self.company,
				"unit": self.unit
			},
			as_dict=True,
		)

		if len(existing_accounting_period) > 0:
			frappe.throw(
				_("Accounting Period overlaps with {0} - {1}").format(existing_accounting_period[0].get("name"), existing_accounting_period[0].get("unit")),
				OverlapError,
			)
	def on_submit(self):
		create_costing_bengkel_on_submit(self)

	def on_cancel(self):
		cancel_costing_bengkel_on_cancel(self)

	def on_trash(self):
		delete_costing_bengkel_on_trash(self)

def create_costing_bengkel_on_submit(doc, method=None):
	"""
	Saat Accounting Period disubmit (workflow_state = "Submitted"), buat & submit
	Costing Bengkel otomatis dengan periode/company/unit yang sama.
	Dicek dulu supaya tidak dobel kalau doc disimpan ulang saat sudah Submitted.
	"""
	if doc.get("workflow_state") != "Submitted":
		return

	existing = frappe.db.exists("Costing Bengkel", {
		"company": doc.company,
		"unit": doc.unit,
		"periode_dari": doc.start_date,
		"periode_sampai": doc.end_date,
		"docstatus": ["!=", 2],
	})
	if existing:
		return

	from sth.accounting_sth.doctype.costing_bengkel.costing_bengkel import build_and_submit_costing_bengkel

	build_and_submit_costing_bengkel(
		company=doc.company,
		unit=doc.unit,
		periode_dari=doc.start_date,
		periode_sampai=doc.end_date,
	)


def cancel_costing_bengkel_on_cancel(doc, method=None):
	"""
	Saat Accounting Period dibatalkan (workflow_state = "Cancelled"), cancel juga
	Costing Bengkel yang otomatis dibuat untuk company/unit/periode yang sama.
	"""
	if doc.get("workflow_state") != "Cancelled":
		return

	costing_bengkel_list = frappe.get_all("Costing Bengkel", filters={
		"company": doc.company,
		"unit": doc.unit,
		"periode_dari": doc.start_date,
		"periode_sampai": doc.end_date,
		"docstatus": 1,
	}, pluck="name")

	for name in costing_bengkel_list:
		cb = frappe.get_doc("Costing Bengkel", name)
		cb.flags.ignore_links = True
		cb.flags.ignore_permissions = True
		cb.cancel()


def delete_costing_bengkel_on_trash(doc, method=None):
	"""
	Saat Accounting Period dihapus, ikut hapus Costing Bengkel yang otomatis
	dibuat untuk company/unit/periode yang sama. Yang masih submitted
	dibatalkan dulu sebelum dihapus.
	"""
	costing_bengkel_list = frappe.get_all("Costing Bengkel", filters={
		"company": doc.company,
		"unit": doc.unit,
		"periode_dari": doc.start_date,
		"periode_sampai": doc.end_date,
	}, pluck="name")

	for name in costing_bengkel_list:
		cb = frappe.get_doc("Costing Bengkel", name)
		if cb.docstatus == 1:
			cb.flags.ignore_links = True
			cb.flags.ignore_permissions = True
			cb.cancel()

		frappe.delete_doc("Costing Bengkel", name, force=True, ignore_permissions=True)


def validate_accounting_period_on_doc_save(doc, method=None):
	if doc.doctype == "Bank Clearance":
		return
	elif doc.doctype == "Asset":
		if doc.is_existing_asset:
			return
		else:
			date = doc.available_for_use_date
	elif doc.doctype == "Asset Repair":
		date = doc.completion_date
	elif doc.doctype == "Period Closing Voucher":
		date = doc.period_end_date
	else:
		date = doc.posting_date

	ap = frappe.qb.DocType("Accounting Period")
	cd = frappe.qb.DocType("Closed Document")

	accounting_period = (
		frappe.qb.from_(ap)
		.from_(cd)
		.select(ap.name)
		.where(
			(ap.name == cd.parent)
			& (ap.company == doc.company)
			& (cd.closed == 1)
			& (cd.document_type == doc.doctype)
			& (date >= ap.start_date)
			& (date <= ap.end_date)
			& (ap.unit == doc.unit)
			& (ap.workflow_state == "Submitted")
		)
	).run(as_dict=1)

	if accounting_period:
		frappe.throw(
			_("You cannot create a {0} within the closed Accounting Period {1} Unit {2}").format(
				doc.doctype, frappe.bold(accounting_period[0]["name"]), frappe.bold(doc.unit)
			),
			ClosedAccountingPeriod,
		)