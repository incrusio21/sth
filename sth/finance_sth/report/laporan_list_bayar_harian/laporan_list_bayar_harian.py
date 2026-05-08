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
			"width": 250,
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
			pe.payment_type,
			pe.tipe_transfer,
			uf.name as unit_from,
			ut.name as unit_to,
			cf.abbr as company_from,
			ct.abbr as company_to,
			pe.company,
			pe.party,
			pe.reference_no,
			pi.invoice_type,
			per.reference_doctype,
			per.outstanding_amount,
			pe.paid_amount,
			pe.request_release_date
		FROM
			`tabPayment Entry` pe
		LEFT JOIN
			`tabPayment Entry Reference` per ON per.parent = pe.name
		LEFT JOIN
			`tabPurchase Invoice` pi ON pi.name = per.reference_name
		LEFT JOIN
			`tabUnit` uf ON uf.bank_account = pe.paid_from
		LEFT JOIN
			`tabUnit` ut ON ut.bank_account = pe.paid_to
		LEFT JOIN
			`tabAccount` af ON af.name = pe.paid_from
		LEFT JOIN
			`tabAccount` at ON at.name = pe.paid_to
		LEFT JOIN
			`tabCompany` cf ON cf.name = af.company
		LEFT JOIN
			`tabCompany` ct ON ct.name = at.company
		WHERE
			pe.docstatus = 0 AND pe.tipe_transfer = '' AND pe.permintaan_dana_operasional IS NULL
		ORDER BY
			FIELD(per.reference_doctype, 'BPJS KES', 'Employee Advance', 'Purchase Invoice'),
			pe.company,
			pe.name
		""",
		as_dict=True,
	)

	# Group rows by section
	pindah_dana_rows = []
	tbs_luar_rows = []
	bpjs_rows = []
	bpjs_tk_rows = []
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
			"payment_schedule": pe.request_release_date,
			"submit_button": pe.name,  # JS will render a button using this
		}

		if pe.get("payment_type") == "Internal Transfer":
			row["jenis_transaksi"] = "PINDAH DANA"
			row["payment_status"] = ""
			row["pt"] = f"{pe.get('company_from')} -> {pe.get('company_to')}"
			row["uraian"] = f"{pe.get('unit_from')} -> {pe.get('unit_to')}"
			row["nilai_tagihan"] = pe.get("paid_amount")
			pindah_dana_rows.append(row)	
		elif ref_type == "Purchase Invoice" and pe.get("invoice_type") == "Pengakuan Pembelian TBS":
			row["jenis_transaksi"] = "PEMBELIAN TBS LUAR"
			row["payment_status"] = "TOP PRIORITY"
			tbs_luar_rows.append(row)	
		elif ref_type == "BPJS KES":
			row["jenis_transaksi"] = "BPJS KESEHATAN"
			row["payment_status"] = "PRIORITY"
			bpjs_rows.append(row)
		elif ref_type == "BPJS TK":
			row["jenis_transaksi"] = "BPJS TK"
			row["payment_status"] = "PRIORITY"
			bpjs_tk_rows.append(row)
		elif ref_type == "Employee Advance":
			row["jenis_transaksi"] = "PENGAJUAN PERJALANAN DINAS"
			row["payment_status"] = ""
			hrd_rows.append(row)
		elif ref_type in ["Pertanggungjawaban Perjalanan Dinas", "Employee Potongan"]:
			row["jenis_transaksi"] = "TAGIHAN HRD"
			row["payment_status"] = ""
			hrd_rows.append(row)
		elif pe.get("invoice_type") == "Jasa Pelatihan":
			row["jenis_transaksi"] = "TAGIHAN HRD"
			row["payment_status"] = ""
			hrd_rows.append(row)
		elif ref_type == "Purchase Invoice" and pe.get("invoice_type") not in ["Jasa Pelatihan", "Pengakuan Pembelian TBS"]:
			row["jenis_transaksi"] = "TAGIHAN SUPPLIER"
			row["payment_status"] = ""
			supplier_rows.append(row)

	data = []
	grand_total = 0

	# --- PINDAH DANA ---
	if pindah_dana_rows:
		pindah_dana_total = sum(r["nilai_tagihan"] for r in pindah_dana_rows)
		grand_total += pindah_dana_total
		data.extend(pindah_dana_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL PINDAH DANA",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": pindah_dana_total,
				"payment_schedule": "",
				"payment_status": "",
				"submit_button": "",
				"is_total": 1,
			}
		)

	# --- PEMBELIAN TBS LUAR ---
	if tbs_luar_rows:
		tbs_luar_total = sum(r["nilai_tagihan"] for r in tbs_luar_rows)
		grand_total += tbs_luar_total
		data.extend(tbs_luar_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL PEMBELIAN TBS LUAR",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": tbs_luar_total,
				"payment_schedule": "",
				"payment_status": "",
				"submit_button": "",
				"is_total": 1,
			}
		)

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

	# --- BPJS TK ---
	if bpjs_tk_rows:
		bpjs_tk_total = sum(r["nilai_tagihan"] for r in bpjs_tk_rows)
		grand_total += bpjs_tk_total
		data.extend(bpjs_tk_rows)
		data.append(
			{
				"jenis_transaksi": "",
				"pt": "",
				"uraian": "TOTAL BPJS TK",
				"no_payment_voucher": "",
				"no_reff_mcm": "",
				"nilai_tagihan": bpjs_tk_total,
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