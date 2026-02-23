import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "jenis_transaksi",
			"label": _("JENIS TRANSAKSI"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "pt",
			"label": _("PT"),
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"fieldname": "uraian",
			"label": _("URAIAN - VENDOR - PT UNIT"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "no_payment_voucher",
			"label": _("NO. PAYMENT VOUCHER"),
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 180,
		},
		{
			"fieldname": "no_reff_mcm",
			"label": _("NO REFF MCM"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "nilai_tagihan",
			"label": _("NILAI TAGIHAN"),
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"fieldname": "payment_schedule",
			"label": _("PAYMENT SCHEDULE"),
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "payment_status",
			"label": _("PAYMENT STATUS"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "submit_button",
			"label": _("ACTION"),
			"fieldtype": "Data",
			"width": 120,
		},
	]


def get_data(filters=None):
	# Fetch all Draft Payment Entries with their references
	payment_entries = frappe.db.sql(
		"""
		SELECT
			pe.name,
			pe.company,
			pe.party,
			pe.reference_no,
			per.reference_doctype,
			per.outstanding_amount
		FROM
			`tabPayment Entry` pe
		INNER JOIN
			`tabPayment Entry Reference` per ON per.parent = pe.name
		WHERE
			pe.docstatus = 0
		ORDER BY
			FIELD(per.reference_doctype, 'BPJS KES', 'Employee Advance', 'Purchase Invoice'),
			pe.company,
			pe.name
		""",
		as_dict=True,
	)

	# Group rows by section
	bpjs_rows = []
	hrd_rows = []
	supplier_rows = []

	for pe in payment_entries:
		ref_type = pe.reference_doctype or ""

		row = {
			"pt": pe.company,
			"uraian": pe.party,
			"no_payment_voucher": pe.name,
			"no_reff_mcm": pe.reference_no,
			"nilai_tagihan": flt(pe.outstanding_amount),
			"payment_schedule": "",
			"submit_button": pe.name,  # JS will render a button using this
		}

		if ref_type == "BPJS KES":
			row["jenis_transaksi"] = "BPJS KESEHATAN"
			row["payment_status"] = "PRIORITY"
			bpjs_rows.append(row)
		elif ref_type == "Employee Advance":
			row["jenis_transaksi"] = "TAGIHAN HRD"
			row["payment_status"] = ""
			hrd_rows.append(row)
		elif ref_type == "Purchase Invoice":
			row["jenis_transaksi"] = "TAGIHAN SUPPLIER"
			row["payment_status"] = ""
			supplier_rows.append(row)

	data = []
	grand_total = 0

	# --- BPJS KESEHATAN ---
	if bpjs_rows:
		bpjs_total = sum(r["nilai_tagihan"] for r in bpjs_rows)
		grand_total += bpjs_total
		data.extend(bpjs_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL BPJS KESEHATAN",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": bpjs_total,
				"payment_schedule": "",
				"payment_status": "",
				"submit_button": "",
				"is_total": 1,
			}
		)

	# --- TAGIHAN HRD ---
	if hrd_rows:
		hrd_total = sum(r["nilai_tagihan"] for r in hrd_rows)
		grand_total += hrd_total
		data.extend(hrd_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL TAGIHAN HRD",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": hrd_total,
				"payment_schedule": "",
				"payment_status": "",
				"submit_button": "",
				"is_total": 1,
			}
		)

	# --- TAGIHAN SUPPLIER ---
	if supplier_rows:
		supplier_total = sum(r["nilai_tagihan"] for r in supplier_rows)
		grand_total += supplier_total
		data.extend(supplier_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL TAGIHAN SUPPLIER",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": supplier_total,
				"payment_schedule": "",
				"payment_status": "",
				"submit_button": "",
				"is_total": 1,
			}
		)

	# --- GRAND TOTAL ---
	data.append(
		{
			"jenis_transaksi": "",
			"pt": "",
			"uraian": "GRAND TOTAL PEMBAYARAN TAGIHAN",
			"no_payment_voucher": "",
			"no_reff_mcm": "",
			"nilai_tagihan": grand_total,
			"payment_schedule": "",
			"payment_status": "",
			"submit_button": "",
			"is_total": 1,
			"is_grand_total": 1,
		}
	)

	return data