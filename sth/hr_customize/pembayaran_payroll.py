"""Tagihan Payroll Entry dipecah per tipe pembayaran.

Accrual Payroll Entry mengkredit Payroll Payable sebesar net pay dan tiap akun
potongan sebesar potongannya. Yang dibayar Payment Entry adalah kredit-kredit
itu, tapi penerimanya berbeda-beda, jadi dipecah per tipe:

- Gaji: net pay tiap slip, ke Payroll Payable.
- PPh 21: komponen potongan PPH21 TER.
- Potongan: potongan dari Employee Potongan, sub tipenya Jenis Potongan.
  Potongan lain yang tidak lewat Employee Potongan, Daftar BPJS, atau PPh 21
  ikut di sini dengan sub tipe nama Salary Component-nya.
- BPJS: porsi karyawan dari Daftar BPJS, sub tipenya BPJS TK atau BPJS KES.
  Porsi perusahaan tidak ikut karena memang tidak diaccrual (komponennya
  dicentang Not Include Net Pay).

Potongan dibaca lewat rincian_komponen, penyaring yang sama dengan accrual,
jadi jumlah tiap akun di sini persis yang dikredit accrual. Baris yang akunnya
tidak dikredit GL Payroll Entry - accrual cara lama yang menumpuk semuanya di
satu akun - ditandai belum diaccrual dan tidak bisa dibayar.

Satu Payment Entry boleh membayar beberapa tipe sekaligus lewat tabel
rincian_payroll; tiap baris mendebit akunnya sendiri.
"""

import frappe
from frappe import _
from frappe.utils import flt

from sth.accounting_sth.komponen_gaji import rincian_komponen
from sth.hr_customize.pph21 import get_komponen_pph21_ter

TIPE_GAJI = "Gaji"
TIPE_PPH21 = "PPh 21"
TIPE_POTONGAN = "Potongan"
TIPE_BPJS = "BPJS"
URUTAN_TIPE = (TIPE_GAJI, TIPE_PPH21, TIPE_POTONGAN, TIPE_BPJS)

TABEL_RINCIAN = "rincian_payroll"
DOCTYPE_RINCIAN = "Payment Entry Payroll"

TOLERANSI = 0.005


def kunci(row):
	return (row.get("tipe"), row.get("sub_tipe") or "", row.get("account"))


def rincian_baris(payroll_entry):
	"""Satu baris per slip per komponen, lengkap dengan tipe, sub tipe, dan dokumen asalnya."""
	slips = frappe.db.sql("""
		SELECT name, employee, employee_name, net_pay
		FROM `tabSalary Slip`
		WHERE payroll_entry = %s AND docstatus = 1
	""", payroll_entry.name, as_dict=True)

	if not slips:
		return []

	hasil = [
		frappe._dict({
			"tipe": TIPE_GAJI,
			"sub_tipe": "",
			"account": payroll_entry.payroll_payable_account,
			"salary_slip": d.name,
			"employee": d.employee,
			"employee_name": d.employee_name,
			"salary_component": "",
			"amount": flt(d.net_pay),
			"sumber_doctype": "Salary Slip",
			"sumber": d.name,
		})
		for d in slips
		if flt(d.net_pay)
	]

	nama_slip = [d.name for d in slips]
	potongan = employee_potongan_per_additional_salary(nama_slip)
	bpjs = daftar_bpjs_per_slip_komponen(nama_slip)
	pph21 = set(get_komponen_pph21_ter("Deduction"))

	for r in rincian_komponen(payroll_entry.company, nama_slip, "deductions"):
		baris = frappe._dict({
			"account": r.account,
			"salary_slip": r.salary_slip,
			"employee": r.employee,
			"employee_name": r.employee_name,
			"salary_component": r.salary_component,
			"amount": flt(r.amount),
		})

		if sumber := potongan.get(r.additional_salary):
			baris.update(tipe=TIPE_POTONGAN, sub_tipe=sumber.jenis_potongan,
				sumber_doctype="Employee Potongan", sumber=sumber.name)
		elif sumber := bpjs.get((r.salary_slip, r.salary_component)):
			baris.update(tipe=TIPE_BPJS, sub_tipe=sumber.jenis_bpjs,
				sumber_doctype="Daftar BPJS", sumber=sumber.name)
		elif r.salary_component in pph21:
			baris.update(tipe=TIPE_PPH21, sub_tipe="",
				sumber_doctype="Salary Slip", sumber=r.salary_slip)
		elif r.additional_salary:
			baris.update(tipe=TIPE_POTONGAN, sub_tipe=r.salary_component,
				sumber_doctype="Additional Salary", sumber=r.additional_salary)
		else:
			baris.update(tipe=TIPE_POTONGAN, sub_tipe=r.salary_component,
				sumber_doctype="Salary Slip", sumber=r.salary_slip)

		hasil.append(baris)

	return hasil


def employee_potongan_per_additional_salary(nama_slip):
	rows = frappe.db.sql("""
		SELECT DISTINCT sd.additional_salary, ep.name, ep.jenis_potongan
		FROM `tabSalary Detail` sd
		JOIN `tabEmployee Potongan Details` epd ON epd.additional_salary = sd.additional_salary
		JOIN `tabEmployee Potongan` ep ON ep.name = epd.parent
		WHERE sd.parent IN %(slips)s
		  AND sd.parenttype = 'Salary Slip'
		  AND IFNULL(sd.additional_salary, '') != ''
	""", {"slips": tuple(nama_slip)}, as_dict=True)

	return {r.additional_salary: r for r in rows}


def daftar_bpjs_per_slip_komponen(nama_slip):
	"""Daftar BPJS asal potongan BPJS tiap slip.

	Employee Payment Log menaut slipnya lewat salary_slip begitu slip
	disubmit, dan tagihan cuma membaca slip tersubmit.
	"""
	rows = frappe.db.sql("""
		SELECT epl.salary_slip, epl.salary_component, db.name, db.jenis_bpjs
		FROM `tabEmployee Payment Log` epl
		JOIN `tabDaftar BPJS` db ON db.name = epl.voucher_no
		WHERE epl.salary_slip IN %(slips)s
		  AND epl.voucher_type = 'Daftar BPJS'
		  AND epl.type = 'Deduction'
	""", {"slips": tuple(nama_slip)}, as_dict=True)

	return {(r.salary_slip, r.salary_component): r for r in rows}


def get_tagihan(payroll_entry, kecuali=None):
	"""Tagihan tiap tipe, sub tipe, dan akun beserta yang sudah dibayar.

	kecuali: Payment Entry yang pembayarannya tidak dihitung, yaitu dokumen
	yang sedang divalidasi.
	"""
	if isinstance(payroll_entry, str):
		payroll_entry = frappe.get_doc("Payroll Entry", payroll_entry)

	tagihan = {}
	for r in rincian_baris(payroll_entry):
		row = tagihan.setdefault(kunci(r), frappe._dict({
			"tipe": r.tipe,
			"sub_tipe": r.sub_tipe or "",
			"account": r.account,
			"tagihan": 0,
			"karyawan": set(),
		}))
		row.tagihan += r.amount
		row.karyawan.add(r.employee)

	party = party_per_akun(payroll_entry, {k[2] for k in tagihan})
	kredit = kredit_accrual(payroll_entry.name)
	total_per_akun = {}
	for row in tagihan.values():
		total_per_akun[row.account] = total_per_akun.get(row.account, 0) + row.tagihan

	dibayar = get_dibayar(payroll_entry, kecuali=kecuali)

	hasil = []
	for k, row in tagihan.items():
		row.tagihan = flt(row.tagihan, 2)
		row.karyawan = len(row.karyawan)
		row.party_type, row.party = party.get(row.account, (None, None))
		row.belum_diakrual = int(kredit.get(row.account, 0) < total_per_akun[row.account] - TOLERANSI)
		row.dibayar = flt(dibayar.pop(k, 0), 2)
		row.sisa = 0 if row.belum_diakrual else flt(row.tagihan - row.dibayar, 2)
		hasil.append(row)

	# Pembayaran yang kuncinya tidak lagi ada di tagihan tetap ditampilkan,
	# supaya kelebihan bayar tidak hilang dari pandangan.
	for (tipe, sub_tipe, account), amount in dibayar.items():
		hasil.append(frappe._dict({
			"tipe": tipe, "sub_tipe": sub_tipe, "account": account,
			"tagihan": 0, "karyawan": 0, "party_type": None, "party": None,
			"belum_diakrual": 0, "dibayar": flt(amount, 2), "sisa": flt(-amount, 2),
		}))

	hasil.sort(key=lambda d: (
		URUTAN_TIPE.index(d.tipe) if d.tipe in URUTAN_TIPE else len(URUTAN_TIPE),
		d.sub_tipe, d.account or "",
	))
	return hasil


def party_per_akun(payroll_entry, accounts):
	"""Party yang dipakai accrual untuk akun bertipe Payable, lihat party_akun_potongan."""
	from sth.overrides.payroll_entry import tipe_akun_party

	return {
		account: ("Supplier", payroll_entry.get("supplier_potongan"))
		for account, tipe in tipe_akun_party(accounts).items()
		if tipe == "Payable" and payroll_entry.get("supplier_potongan")
	}


def kredit_accrual(payroll_entry):
	return dict(frappe.db.sql("""
		SELECT account, SUM(credit)
		FROM `tabGL Entry`
		WHERE voucher_type = 'Payroll Entry' AND voucher_no = %s AND is_cancelled = 0
		GROUP BY account
	""", payroll_entry))


def get_dibayar(payroll_entry, kecuali=None):
	"""Jumlah yang sudah dibayar Payment Entry tersubmit, per tipe, sub tipe, dan akun.

	Payment Entry sebelum ada tabel rincian cuma membayar net pay ke Payroll
	Payable, jadi dihitung sebagai Gaji.
	"""
	hasil = {}
	for r in frappe.db.sql("""
		SELECT r.tipe, IFNULL(r.sub_tipe, '') AS sub_tipe, r.account, SUM(r.amount) AS amount
		FROM `tab{0}` r
		JOIN `tabPayment Entry` pe ON pe.name = r.parent
		WHERE pe.no_payroll_entry = %(pe)s
		  AND pe.docstatus = 1
		  AND pe.name != %(kecuali)s
		  AND r.parenttype = 'Payment Entry'
		GROUP BY r.tipe, IFNULL(r.sub_tipe, ''), r.account
	""".format(DOCTYPE_RINCIAN), {"pe": payroll_entry.name, "kecuali": kecuali or ""}, as_dict=True):
		hasil[kunci(r)] = flt(r.amount)

	lama = frappe.db.sql("""
		SELECT IFNULL(SUM(pe.paid_amount), 0)
		FROM `tabPayment Entry` pe
		WHERE pe.no_payroll_entry = %(pe)s
		  AND pe.docstatus = 1
		  AND pe.name != %(kecuali)s
		  AND NOT EXISTS (
			SELECT 1 FROM `tab{0}` r
			WHERE r.parent = pe.name AND r.parenttype = 'Payment Entry'
		  )
	""".format(DOCTYPE_RINCIAN), {"pe": payroll_entry.name, "kecuali": kecuali or ""})[0][0]

	if flt(lama):
		k = (TIPE_GAJI, "", payroll_entry.payroll_payable_account)
		hasil[k] = hasil.get(k, 0) + flt(lama)

	return hasil


def get_pembayaran(payroll_entry):
	"""Payment Entry yang menaut Payroll Entry ini, yang batal tidak ikut."""
	return frappe.get_all(
		"Payment Entry",
		filters={"no_payroll_entry": payroll_entry, "docstatus": ("<", 2)},
		fields=["name", "docstatus", "posting_date", "paid_amount", "paid_from"],
		order_by="posting_date, name",
	)


@frappe.whitelist()
def get_tagihan_payroll(payroll_entry):
	frappe.has_permission("Payroll Entry", "read", payroll_entry, throw=True)

	doc = frappe.get_doc("Payroll Entry", payroll_entry)
	if doc.docstatus != 1:
		frappe.throw(_("Payroll Entry {0} belum di-submit").format(payroll_entry))

	return {
		"company": doc.company,
		"unit": doc.get("unit"),
		"cost_center": doc.cost_center,
		"tagihan": get_tagihan(doc),
		"pembayaran": get_pembayaran(payroll_entry),
	}


@frappe.whitelist()
def get_dokumen_terkait(payroll_entry, kunci_tagihan=None):
	"""Dokumen asal tagihan, dikelompokkan per tipe, sub tipe, dan akun.

	kunci_tagihan: daftar [tipe, sub_tipe, account] yang mau dilihat, dalam
	JSON kalau dari form. Kosong berarti semuanya.
	"""
	frappe.has_permission("Payroll Entry", "read", payroll_entry, throw=True)

	if isinstance(kunci_tagihan, str):
		kunci_tagihan = frappe.parse_json(kunci_tagihan)
	dicari = {(k[0], k[1] or "", k[2]) for k in kunci_tagihan or []}

	doc = frappe.get_doc("Payroll Entry", payroll_entry)
	kelompok = {}
	for r in rincian_baris(doc):
		k = kunci(r)
		if dicari and k not in dicari:
			continue

		g = kelompok.setdefault(k, frappe._dict({
			"tipe": r.tipe,
			"sub_tipe": r.sub_tipe or "",
			"account": r.account,
			"jumlah": 0,
			"dokumen": {},
			"karyawan": [],
		}))
		g.jumlah += r.amount
		g.karyawan.append(r)

		# Gaji dan PPh 21 bersumber dari tiap slip, dan slipnya sudah ada di
		# daftar karyawan; tabel dokumen cukup memuat dokumen di luar slip.
		if r.sumber_doctype == "Salary Slip":
			continue

		d = g.dokumen.setdefault((r.sumber_doctype, r.sumber), frappe._dict({
			"doctype": r.sumber_doctype,
			"name": r.sumber,
			"karyawan": set(),
			"jumlah": 0,
		}))
		d.karyawan.add(r.employee)
		d.jumlah += r.amount

	for g in kelompok.values():
		g.jumlah = flt(g.jumlah, 2)
		g.karyawan.sort(key=lambda r: (r.employee_name or "", r.salary_component or ""))
		dokumen = []
		for d in g.dokumen.values():
			d.karyawan = len(d.karyawan)
			d.jumlah = flt(d.jumlah, 2)
			if d.doctype == "Daftar BPJS" and g.sub_tipe in ("BPJS TK", "BPJS KES"):
				d.dokumen_bpjs = frappe.db.get_value(
					g.sub_tipe, {"no_daftar_bpjs": d.name, "docstatus": 1}, "name"
				)
			dokumen.append(d)
		g.dokumen = sorted(dokumen, key=lambda d: (d.doctype, d.name))

	return sorted(kelompok.values(), key=lambda g: (
		URUTAN_TIPE.index(g.tipe) if g.tipe in URUTAN_TIPE else len(URUTAN_TIPE),
		g.sub_tipe, g.account or "",
	))


def validate_pembayaran_payroll(pe):
	"""Isi dan periksa tabel rincian_payroll Payment Entry.

	Akun dan party tiap baris diambil ulang dari tagihan, bukan dari isian
	form, dan jumlahnya tidak boleh melewati sisa tagihan yang belum dibayar
	Payment Entry tersubmit lain.
	"""
	rows = pe.get(TABEL_RINCIAN) or []
	if pe.tipe_transfer != "Payroll Entry" or not rows:
		return

	if not pe.no_payroll_entry:
		frappe.throw(_("No Payroll Entry belum diisi"))

	payroll_entry = frappe.get_doc("Payroll Entry", pe.no_payroll_entry)
	if payroll_entry.docstatus != 1:
		frappe.throw(_("Payroll Entry {0} belum di-submit").format(payroll_entry.name))

	if payroll_entry.company != pe.company:
		frappe.throw(_("Payroll Entry {0} milik company {1}, bukan {2}").format(
			payroll_entry.name, payroll_entry.company, pe.company
		))

	tagihan = {kunci(d): d for d in get_tagihan(payroll_entry, kecuali=pe.name)}

	terpakai = {}
	for row in rows:
		label = _("Baris {0} ({1}{2})").format(
			row.idx, row.tipe, " - " + row.sub_tipe if row.sub_tipe else ""
		)
		t = tagihan.get(kunci(row))
		if not t or not t.tagihan:
			frappe.throw(_("{0}: tidak ada di tagihan Payroll Entry {1}").format(label, payroll_entry.name))

		if t.belum_diakrual:
			frappe.throw(_(
				"{0}: akun {1} tidak dikredit GL Payroll Entry {2}, jadi belum ada "
				"hutang yang bisa dibayar. Accrual-nya masih cara lama; posting ulang dulu."
			).format(label, t.account, payroll_entry.name))

		if flt(row.amount) <= 0:
			frappe.throw(_("{0}: jumlah bayar harus lebih dari 0").format(label))

		row.sub_tipe = t.sub_tipe
		row.party_type = t.party_type
		row.party = t.party
		row.tagihan = t.tagihan
		row.sisa = t.sisa

		terpakai[kunci(row)] = terpakai.get(kunci(row), 0) + flt(row.amount)
		if terpakai[kunci(row)] > t.sisa + TOLERANSI:
			frappe.throw(_("{0}: dibayar {1}, padahal sisa tagihannya {2}").format(
				label,
				frappe.format(terpakai[kunci(row)], {"fieldtype": "Currency"}),
				frappe.format(t.sisa, {"fieldtype": "Currency"}),
			))

	total = flt(sum(flt(d.amount) for d in rows), pe.precision("paid_amount"))
	pe.paid_to = rows[0].account
	pe.paid_amount = pe.received_amount = total
	pe.base_paid_amount = flt(total * flt(pe.source_exchange_rate or 1), pe.precision("base_paid_amount"))
	pe.base_received_amount = flt(total * flt(pe.target_exchange_rate or 1), pe.precision("base_received_amount"))


def gl_pembayaran_payroll(pe):
	"""Debit tiap baris rincian ke akun yang dikredit accrual."""
	return [
		{
			"account": row.account,
			"party_type": row.party_type,
			"party": row.party,
			"against": pe.paid_from,
			"debit": flt(row.amount),
			"debit_in_account_currency": flt(row.amount),
			"debit_in_transaction_currency": flt(row.amount),
			"cost_center": pe.cost_center,
		}
		for row in pe.get(TABEL_RINCIAN) or []
		if flt(row.amount)
	]
