import frappe
from frappe.utils import cint, flt

from sth.overrides.salary_slip import BPJS_PERUSAHAAN

# Kolom baris earning yang tidak ikut disalin ke baris potongannya
KOLOM_BARU = ("name", "idx", "parentfield", "creation", "modified", "modified_by", "owner")


def execute(terapkan=0, company=None, dari=None, sampai=None, payroll_entry=None):
	"""Pasang baris potongan BPJS beban perusahaan di Salary Slip yang sudah ada.

	Slip yang dibuat sebelum potong_balik_bpjs_perusahaan ada cuma memuat
	beban perusahaan di earnings. Slip draft cukup disimpan ulang - hitungan
	slip yang memasang pasangannya. Slip submit tidak boleh dihitung ulang,
	jadi baris earning-nya disalin langsung ke deductions, bercentang Do Not
	Include In Total. Net pay dan total potongannya tidak berubah.

	Dua yang dilewati dan cuma dilaporkan:

	- Komponen yang tidak dicentang Not Include Net Pay, seperti JKK. Di slip
	  submit ia sudah menambah net pay, dan net pay itu bisa jadi sudah
	  ditransfer; pasangannya akan menurunkan net pay.
	- Beban perusahaan yang dokumen BPJS TK/KES-nya masih punya GL hidup
	  (dibuat sebelum 30 Sep 2026 dan belum dibalik). GL itu sudah mendebit
	  bebannya dan mengkredit hutang BPJS; pasangannya akan mendobelkannya.

	Sesudahnya accrual Payroll Entry slip submit belum ikut. Posting ulang
	dengan sth.patches.repost_accrual_payroll_per_komponen - daftar Payroll
	Entry-nya dicetak di akhir.

	Penyaring: company, dari/sampai (start_date slip), payroll_entry. Aman
	diulang: komponen yang sudah berpasangan dilewati. Tanpa terapkan=1 cuma
	melaporkan. Tidak didaftarkan di patches.txt:

	    bench --site <site> execute sth.patches.sisip_potongan_bpjs_perusahaan.execute --kwargs "{'terapkan': 1, 'dari': '2026-10-01'}"
	"""
	terapkan = cint(terapkan)
	slips = cari_slip(company, dari, sampai, payroll_entry)
	if not slips:
		print("Tidak ada Salary Slip ber-BPJS perusahaan tanpa pasangan yang cocok dengan penyaringnya.")
		return

	draft = [s for s in slips if s.docstatus == 0]
	submit = [s for s in slips if s.docstatus == 1]
	print(f"{len(draft)} slip draft, {len(submit)} slip submit, mode {'TERAPKAN' if terapkan else 'LAPORAN SAJA'}")

	hasil = {"disimpan": [], "gagal": [], "disisip": [], "net_pay": [], "gl_bpjs": []}
	for s in draft:
		simpan_ulang_draft(s, terapkan, hasil)

	gl_hidup = dokumen_bpjs_ber_gl()
	payroll_entry_terdampak = set()
	for s in submit:
		if sisip_di_slip_submit(s, gl_hidup, terapkan, hasil):
			payroll_entry_terdampak.add(s.payroll_entry)

	cetak("Slip draft " + ("disimpan ulang" if terapkan else "akan disimpan ulang"), hasil["disimpan"])
	cetak("Slip draft gagal disimpan", hasil["gagal"])
	cetak("Baris potongan " + ("disisipkan" if terapkan else "akan disisipkan"), hasil["disisip"])
	cetak("Dilewati: komponen ikut net pay (tidak dicentang Not Include Net Pay)", hasil["net_pay"])
	cetak("Dilewati: dokumen BPJS masih punya GL hidup", hasil["gl_bpjs"])

	payroll_entry_terdampak.discard(None)
	ber_gl = sorted(pe for pe in payroll_entry_terdampak if frappe.db.exists(
		"GL Entry", {"voucher_type": "Payroll Entry", "voucher_no": pe, "is_cancelled": 0}
	))
	cetak("Payroll Entry yang accrual-nya perlu diposting ulang "
		"(sth.patches.repost_accrual_payroll_per_komponen, kwargs nama)", ber_gl)

	if terapkan:
		frappe.db.commit()
	else:
		print("\nBelum ada yang diubah. Jalankan dengan terapkan=1 untuk memasang.")


def cari_slip(company, dari, sampai, payroll_entry):
	"""Slip draft/submit yang punya earning BPJS perusahaan tanpa baris potongan sekomponen."""
	syarat, params = ["ss.docstatus < 2"], {"bpjs": BPJS_PERUSAHAAN}
	for kolom, nilai, op in (
		("ss.company", company, "="),
		("ss.start_date", dari, ">="),
		("ss.start_date", sampai, "<="),
		("ss.payroll_entry", payroll_entry, "="),
	):
		if nilai:
			kunci = "p{0}".format(len(params))
			syarat.append(f"{kolom} {op} %({kunci})s")
			params[kunci] = nilai

	return frappe.db.sql("""
		SELECT DISTINCT ss.name, ss.docstatus, ss.payroll_entry, ss.employee
		FROM `tabSalary Slip` ss
		JOIN `tabSalary Detail` er
		  ON er.parent = ss.name AND er.parenttype = 'Salary Slip' AND er.parentfield = 'earnings'
		WHERE {syarat}
		  AND IFNULL(er.amount, 0) != 0
		  AND er.salary_component IN (
			SELECT DISTINCT salary_component FROM `tabEmployee Payment Log`
			WHERE component_type = %(bpjs)s
		  )
		  AND NOT EXISTS (
			SELECT 1 FROM `tabSalary Detail` pot
			WHERE pot.parent = ss.name AND pot.parenttype = 'Salary Slip'
			  AND pot.parentfield = 'deductions' AND pot.salary_component = er.salary_component
		  )
		ORDER BY ss.start_date, ss.name
	""".format(syarat=" AND ".join(syarat)), params, as_dict=True)


def simpan_ulang_draft(s, terapkan, hasil):
	if not terapkan:
		hasil["disimpan"].append(s.name)
		return

	frappe.db.savepoint("sisip_bpjs")
	try:
		doc = frappe.get_doc("Salary Slip", s.name)
		doc.flags.ignore_permissions = True
		doc.save()
		hasil["disimpan"].append(s.name)
	except Exception as e:
		frappe.db.rollback(save_point="sisip_bpjs")
		hasil["gagal"].append(f"{s.name}: {e}")


def dokumen_bpjs_ber_gl():
	"""Daftar BPJS yang dokumen BPJS TK/KES-nya masih punya GL hidup."""
	hasil = set()
	for jenis in frappe.get_all("Daftar BPJS", filters={"docstatus": 1}, pluck="jenis_bpjs", distinct=True):
		if not jenis:
			continue
		hasil.update(frappe.db.sql_list("""
			SELECT DISTINCT b.no_daftar_bpjs
			FROM `tab{0}` b
			JOIN `tabGL Entry` gle
			  ON gle.voucher_type = %(jenis)s AND gle.voucher_no = b.name AND gle.is_cancelled = 0
			WHERE b.docstatus = 1
		""".format(jenis), {"jenis": jenis}))
	return hasil


def sisip_di_slip_submit(s, gl_hidup, terapkan, hasil):
	"""Salin baris earning BPJS perusahaan slip submit ke deductions. True kalau ada yang disisip."""
	asal = dict(frappe.db.sql("""
		SELECT salary_component, MAX(voucher_no)
		FROM `tabEmployee Payment Log`
		WHERE salary_slip = %s AND component_type = %s AND voucher_type = 'Daftar BPJS'
		GROUP BY salary_component
	""", (s.name, BPJS_PERUSAHAAN)))

	doc = frappe.get_doc("Salary Slip", s.name)
	sudah = {d.salary_component for d in doc.deductions}
	idx = max([d.idx for d in doc.deductions] or [0])

	ada = False
	for er in doc.earnings:
		if er.salary_component not in asal or er.salary_component in sudah or not flt(er.amount):
			continue

		label = f"{s.name} / {er.salary_component} {flt(er.amount):,.2f}"
		if not cint(frappe.get_cached_value("Salary Component", er.salary_component, "not_include_net_pay")):
			hasil["net_pay"].append(label)
			continue
		if asal[er.salary_component] in gl_hidup:
			hasil["gl_bpjs"].append(f"{label} ({asal[er.salary_component]})")
			continue

		hasil["disisip"].append(label)
		ada = True
		if not terapkan:
			continue

		idx += 1
		baris = frappe.get_doc({
			**{k: v for k, v in er.as_dict().items() if k not in KOLOM_BARU},
			"doctype": "Salary Detail",
			"parent": doc.name,
			"parenttype": "Salary Slip",
			"parentfield": "deductions",
			"idx": idx,
			"do_not_include_in_total": 1,
			"exempted_from_income_tax": 0,
			"additional_salary": None,
		})
		baris.db_insert()

	return ada


def cetak(judul, daftar):
	print(f"\n{judul}: {len(daftar)}")
	for d in daftar:
		print(f"  {d}")
