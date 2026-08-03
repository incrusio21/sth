# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import clear_last_message

def get_attendance_settings(key: str):
	"""Return the value associated with the given `key` from Attendance Settings DocType."""
	if not (attendance_setings := getattr(frappe.local, "attendance_setings", None)):
		try:
			frappe.local.attendance_setings = attendance_setings = frappe.get_cached_doc("Attendance Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return attendance_setings.get(key)

def get_premi_attendance_settings(key: str):
	"""Return the value associated with the given `key` from Overtime Settings DocType."""
	if not (premi_attendance_setings := getattr(frappe.local, "premi_attendance_setings", None)):
		premi_type = {}
		for p in get_attendance_settings("premi"):
			premi_type.setdefault(p.premi_type, p.salary_component)

		frappe.local.premi_attendance_setings = premi_attendance_setings = premi_type

	return premi_attendance_setings.get(key)

def get_overtime_settings(key: str):
	"""Return the value associated with the given `key` from Overtime Settings DocType."""
	if not (overtime_settings := getattr(frappe.local, "overtime_settings", None)):
		try:
			frappe.local.overtime_settings = overtime_settings = frappe.get_cached_doc("Overtime Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	return overtime_settings.get(key)

def get_payment_settings(key=None):
	"""Return the value associated with the given `key` from Payment Settings DocType."""
	if not (payment_settings := getattr(frappe.local, "payment_settings", None)):
		try:
			frappe.local.payment_settings = payment_settings = frappe.get_cached_doc("Payment Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	if key:
		return payment_settings.get(key)
	
	return payment_settings


def get_allowance_settings(key=None):
	"""Return the value associated with the given `key` from Bonus and Allowance Settings DocType."""
	if not (allowance_settings := getattr(frappe.local, "allowance_settings", None)):
		try:
			frappe.local.allowance_settings = allowance_settings = frappe.get_cached_doc("Bonus and Allowance Settings")
		except frappe.DoesNotExistError:  # possible during new install
			clear_last_message()
			return

	if key:
		return allowance_settings.get(key)
	
	return allowance_settings

@frappe.whitelist()
def update_payment_log(voucher_type, voucher_no=None, filters=None):
	filters = json.loads(filters or "{}")

	if voucher_no:
		filters["name"] = voucher_no

	# doctype yang aman menghitung ulang draft menyatakannya lewat atribut
	# repair_include_draft pada controller-nya. sisanya tetap submitted saja.
	from frappe.model.base_document import get_controller

	# include_draft = getattr(get_controller(voucher_type), "repair_include_draft", False)
	# filters.setdefault("docstatus", ["in", [0, 1]] if include_draft else 1)
	filters.setdefault("docstatus", ["in", [0, 1]])

	# field yang dibandingkan sebelum vs sesudah, sebatas yang dimiliki doctype
	meta = frappe.get_meta(voucher_type)
	tracked = [f for f in ("rupiah_basis", "hasil_kerja_amount", "hasil_kerja_premi_amount", "grand_total") if meta.has_field(f)]

	state_field = None
	if workflow := meta.get_workflow():
		state_field = frappe.get_cached_value("Workflow", workflow, "workflow_state_field") or "workflow_state"

	docs = frappe.get_all(voucher_type, filters=filters, pluck="name")
	changed = []
	posted = []

	for d in docs:
		doc = frappe.get_doc(voucher_type, d)

		# dokumen Posted sudah masuk buku besar, nilainya tidak boleh berubah lagi.
		# dilewati, bukan di-throw, supaya satu dokumen tidak menggagalkan seluruh batch
		if state_field and doc.get(state_field) == "Posted":
			posted.append(d)
			continue

		before = {f: doc.get(f) for f in tracked}

		doc.run_method("repair_employee_payment_log")

		diff = [(f, before[f], doc.get(f)) for f in tracked if before[f] != doc.get(f)]
		if diff:
			changed.append((d, doc.docstatus, diff))

	frappe.msgprint(
		get_update_payment_log_summary(voucher_type, filters, len(docs) - len(posted), changed, posted),
		title=f"Re-calculate {voucher_type}",
		wide=True
	)

	return [c[0] for c in changed]

def get_update_payment_log_summary(voucher_type, filters, total, changed, posted=None):
	status_label = {0: "Draft", 1: "Submitted"}

	html = [
		f"<p>{len(changed)} dari {total} dokumen berubah.</p>",
		f"<p style='color: var(--text-muted)'>Filter: <code>{frappe.utils.escape_html(str(filters))}</code></p>"
	]

	if posted:
		html.append(
			f"<p style='color: var(--text-muted)'>{len(posted)} dokumen dilewati karena sudah <b>Posted</b>.</p>"
		)

	if not total:
		html.append("<p>Tidak ada dokumen yang cocok dengan filter di atas. Periksa rentang tanggal, dan pastikan <code>docstatus</code> mencakup draft bila yang dicari draft.</p>")

	if not changed:
		return "".join(html)

	html.append("<table class='table table-bordered'><thead><tr><th>Document</th><th>Status</th><th>Perubahan</th></tr></thead><tbody>")

	for name, docstatus, diff in changed:
		detail = "<br>".join(f"{f}: {old} &rarr; {new}" for f, old, new in diff)
		link = f"<a href='/app/{frappe.scrub(voucher_type).replace('_', '-')}/{name}'>{name}</a>"

		html.append(f"<tr><td>{link}</td><td>{status_label.get(docstatus, docstatus)}</td><td>{detail}</td></tr>")

	html.append("</tbody></table>")

	return "".join(html)