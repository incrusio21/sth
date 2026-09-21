import frappe
from frappe.utils import flt

from erpnext.accounts.general_ledger import make_reverse_gl_entries

# Selisih di bawah ini dianggap sama, supaya pembulatan float tidak dilaporkan
# sebagai perbedaan.
TOLERANSI = 0.005

# Costing yang mengkredit balik beban gaji. Dokumen yang sudah disubmit untuk
# periode yang diposting ulang ikut dilaporkan: kreditnya masih menunjuk akun
# alokasi yang lama, jadi harus diambil datanya ulang dan disubmit lagi.
DOCTYPE_COSTING = (
	"Costing Mill",
	"Costing Panen",
	"Costing Perawatan",
	"Costing Bengkel",
)


def execute(terapkan=0, company=None, dari=None, sampai=None, nama=None):
	"""Posting ulang accrual Payroll Entry lama memakai akun tiap komponen.

	Accrual yang lama menumpuk seluruh net pay di satu akun dari STH Accounting
	Settings Payroll. Yang sekarang mendebit tiap earning ke akun komponennya dan
	mengkredit tiap deduction ke akunnya, dan Costing Mill, Kebun, serta Bengkel
	mengkredit balik ke akun-akun itu pula. Selama accrual lamanya belum
	diposting ulang, costing periode itu akan mengkredit akun yang tidak pernah
	didebit - itulah yang dibereskan di sini.

	Bawaannya cuma melaporkan, tidak menyentuh buku besar sama sekali. Yang
	mau diposting ulang dijalankan dengan terapkan=1:

	    bench --site <site> execute sth.patches.repost_accrual_payroll_per_komponen.execute
	    bench --site <site> execute sth.patches.repost_accrual_payroll_per_komponen.execute \\
	        --kwargs "{'terapkan': 1, 'dari': '2026-09-01', 'sampai': '2026-09-30'}"

	Penyaringnya: company, dari, sampai (tanggal posting Payroll Entry), atau
	nama satu dokumen. Payroll Entry yang GL-nya sudah sama dengan hitungan
	sekarang dilewati, jadi patch ini aman diulang.

	Waktu diterapkan, GL lamanya dibalik lebih dulu dengan tanggal posting yang
	sama, baru barisnya yang baru diposting. Periode yang sudah ditutup akan
	menolak - dokumennya dilaporkan gagal dan sisanya tetap jalan, karena kapan
	periode dibuka itu keputusan yang menutup buku.

	Sengaja tidak didaftarkan di patches.txt: memposting ulang jurnal gaji bukan
	sesuatu yang boleh jalan sendiri tiap migrate.
	"""
	terapkan = frappe.utils.cint(terapkan)
	dokumen = cari_payroll_entry(company=company, dari=dari, sampai=sampai, nama=nama)

	if not dokumen:
		print("Tidak ada Payroll Entry ber-GL hidup yang cocok dengan penyaringnya.")
		return

	print("{0} Payroll Entry diperiksa, mode {1}\n".format(
		len(dokumen), "TERAPKAN" if terapkan else "LAPORAN SAJA"
	))

	sama = []
	beda = []
	gagal = []

	for nama_pe in dokumen:
		try:
			lama, baru = bandingkan(nama_pe)
		except Exception as e:
			pesan = sebab(e)
			gagal.append((nama_pe, pesan))
			print("{0}: GAGAL DIHITUNG — {1}".format(nama_pe, pesan))
			continue

		if not selisih_akun(lama, baru):
			sama.append(nama_pe)
			continue

		beda.append(nama_pe)
		cetak_perbandingan(nama_pe, lama, baru)

		if not terapkan:
			continue

		# satu dokumen yang tertolak tidak menghentikan sisanya. yang paling
		# sering menolak adalah periode yang sudah ditutup, dan itu perlu
		# diputuskan sendiri-sendiri
		titik = "repost_accrual_payroll"
		try:
			frappe.db.savepoint(titik)
			posting_ulang(nama_pe)
			print("    diposting ulang\n")
		except Exception as e:
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=titik)
			pesan = sebab(e)
			gagal.append((nama_pe, pesan))
			print("    GAGAL — {0}\n".format(pesan))

	print("\nsama dengan hitungan sekarang : {0}".format(len(sama)))
	print("berbeda                       : {0}".format(len(beda)))
	print("gagal                         : {0}".format(len(gagal)))

	for nama_pe, pesan in gagal:
		print("  {0}: {1}".format(nama_pe, pesan[:200]))

	if not terapkan and beda:
		print(
			"\nBelum ada yang disentuh. Ulangi dengan terapkan=1 untuk memposting "
			"ulang dokumen yang berbeda di atas."
		)

	# Costing periode yang sama memegang kredit lama; tanpa diambil ulang, akun
	# komponennya tetap tidak nol walau accrual-nya sudah dibetulkan.
	if beda:
		lapor_costing_terdampak(beda)


def cari_payroll_entry(company=None, dari=None, sampai=None, nama=None):
	"""Payroll Entry submitted yang GL accrual-nya masih hidup."""
	syarat = ["pe.docstatus = 1"]
	params = {}

	if nama:
		syarat.append("pe.name = %(nama)s")
		params["nama"] = nama
	if company:
		syarat.append("pe.company = %(company)s")
		params["company"] = company
	if dari:
		syarat.append("pe.posting_date >= %(dari)s")
		params["dari"] = dari
	if sampai:
		syarat.append("pe.posting_date <= %(sampai)s")
		params["sampai"] = sampai

	return frappe.db.sql_list("""
		SELECT DISTINCT pe.name
		FROM `tabPayroll Entry` pe
		JOIN `tabGL Entry` gle
		  ON gle.voucher_type = 'Payroll Entry'
		 AND gle.voucher_no = pe.name
		 AND gle.is_cancelled = 0
		WHERE {syarat}
		ORDER BY pe.posting_date, pe.name
	""".format(syarat=" AND ".join(syarat)), params)


def bandingkan(nama_pe):
	"""Ringkasan GL yang ada sekarang dan yang dihitung aturan baru."""
	lama = gl_sekarang(nama_pe)

	doc = frappe.get_doc("Payroll Entry", nama_pe)
	gl_entries, _payable = doc.susun_gl_accrual()

	baru = {}
	for d in gl_entries:
		kunci = (d.account, d.cost_center)
		nilai = baru.setdefault(kunci, {"debit": 0, "credit": 0})
		nilai["debit"] += flt(d.debit)
		nilai["credit"] += flt(d.credit)

	return lama, baru


def gl_sekarang(nama_pe):
	rows = frappe.db.sql("""
		SELECT account, cost_center, SUM(debit) AS debit, SUM(credit) AS credit
		FROM `tabGL Entry`
		WHERE voucher_type = 'Payroll Entry'
		  AND voucher_no = %s
		  AND is_cancelled = 0
		GROUP BY account, cost_center
	""", nama_pe, as_dict=True)

	return {
		(r.account, r.cost_center): {"debit": flt(r.debit), "credit": flt(r.credit)}
		for r in rows
	}


def selisih_akun(lama, baru):
	"""Kunci yang nilainya tidak sama antara GL lama dan hitungan baru."""
	hasil = []

	for kunci in sorted(set(lama) | set(baru), key=lambda k: (str(k[0]), str(k[1]))):
		a = lama.get(kunci) or {"debit": 0, "credit": 0}
		b = baru.get(kunci) or {"debit": 0, "credit": 0}

		if (
			abs(flt(a["debit"]) - flt(b["debit"])) > TOLERANSI
			or abs(flt(a["credit"]) - flt(b["credit"])) > TOLERANSI
		):
			hasil.append((kunci, a, b))

	return hasil


def cetak_perbandingan(nama_pe, lama, baru):
	print("{0}".format(nama_pe))
	print("    {0:<58} {1:>16} {2:>16}".format("akun / cost center", "sekarang", "jadi"))

	for kunci, a, b in selisih_akun(lama, baru):
		akun, cost_center = kunci
		print("    {0:<58} {1:>16} {2:>16}".format(
			"{0} | {1}".format(str(akun)[:44], cost_center or "-")[:58],
			nilai_singkat(a),
			nilai_singkat(b),
		))


def sebab(e):
	"""Pesan penolakan yang terbaca, tanpa markup frappe.throw."""
	return frappe.utils.strip_html(str(e)).strip() or e.__class__.__name__


def nilai_singkat(nilai):
	debit = flt(nilai["debit"], 2)
	credit = flt(nilai["credit"], 2)

	if debit and credit:
		return "D {0} K {1}".format(debit, credit)
	if debit:
		return "D {0}".format(debit)
	if credit:
		return "K {0}".format(credit)

	return "-"


def posting_ulang(nama_pe):
	"""Balik GL lamanya, lalu posting barisnya yang baru.

	Dibalik, bukan dihapus, supaya jejaknya tetap ada dan penjaga periode
	tertutup serta tanggal beku tetap berlaku - keduanya ikut diperiksa
	make_reverse_gl_entries dan make_gl_entries.
	"""
	make_reverse_gl_entries(voucher_type="Payroll Entry", voucher_no=nama_pe)

	doc = frappe.get_doc("Payroll Entry", nama_pe)
	doc.make_payroll_gl_entries()


def lapor_costing_terdampak(nama_payroll_entry):
	"""Costing submitted yang periodenya memuat Payroll Entry yang berubah."""
	periode = frappe.db.sql("""
		SELECT name, company, posting_date
		FROM `tabPayroll Entry`
		WHERE name IN %(nama)s
	""", {"nama": tuple(nama_payroll_entry)}, as_dict=True)

	terdampak = []
	for doctype in DOCTYPE_COSTING:
		if not frappe.db.table_exists(doctype):
			continue

		for pe in periode:
			terdampak.extend(frappe.get_all(
				doctype,
				filters={
					"docstatus": 1,
					"company": pe.company,
					"periode_dari": ("<=", pe.posting_date),
					"periode_sampai": (">=", pe.posting_date),
				},
				fields=["name", "company", "unit", "periode_dari", "periode_sampai"],
				limit_page_length=0,
			))

	if not terdampak:
		print("\nTidak ada dokumen costing submitted di periode yang berubah.")
		return

	print(
		"\nCosting submitted di periode yang berubah - kreditnya masih memakai akun "
		"alokasi lama, perlu Ambil Data ulang lalu disubmit lagi:"
	)

	sudah = set()
	for d in terdampak:
		if d.name in sudah:
			continue
		sudah.add(d.name)
		print("  {0:<28} {1} {2} {3} s/d {4}".format(
			d.name, d.company, d.unit or "-", d.periode_dari, d.periode_sampai
		))
