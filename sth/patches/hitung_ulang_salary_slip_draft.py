import frappe
from frappe.utils import cint, flt

# Commit tiap sekian slip: ratusan slip dalam satu transaksi memegang kunci
# baris terlalu lama, dan jalan yang terputus di tengah tidak perlu
# mengulang dari nol.
COMMIT_TIAP = 50


def execute(dry_run=0):
	"""Simpan ulang semua Salary Slip draft supaya ikut formula Salary Structure baru.

	Slip tidak membaca formula dari Salary Component: tiap kali disimpan, slip
	menghitung ulang komponennya dari baris earnings/deductions Salary Structure
	(calculate_net_pay di sth.overrides.salary_slip, yang sekalian membangun
	ulang payment log dan pinjamannya). Slip draft yang dibuat sebelum formula
	di Salary Structure diganti masih memegang angka lama sampai disimpan ulang.

	Slip yang sudah submit tidak disentuh: angkanya sudah masuk accrual Payroll
	Entry, dan mengubahnya berarti cancel dan amend, bukan simpan ulang.

	Slip yang menolak disimpan (karyawan sudah nonaktif, slip ganda di periode
	yang sama, dan sejenisnya) dilewati dan dilaporkan, bukan menghentikan
	sisanya. Tidak didaftarkan di patches.txt: dijalankan sendiri tiap kali
	formulanya diganti, dan aman diulang:

	    bench --site <site> execute sth.patches.hitung_ulang_salary_slip_draft.execute
	    bench --site <site> execute sth.patches.hitung_ulang_salary_slip_draft.execute \\
	        --kwargs "{'dry_run': 1}"

	dry_run menghitung ulang dan melaporkan selisihnya tanpa menyimpan apa pun.
	"""
	dry_run = cint(dry_run)

	slips = frappe.get_all(
		"Salary Slip",
		filters={"docstatus": 0},
		fields=["name", "salary_structure", "net_pay"],
		order_by="start_date, name",
	)

	if not slips:
		print("Tidak ada Salary Slip draft, dilewati.")
		return

	# Formula dibaca lewat get_cached_doc; buang salinan lama di cache supaya
	# yang dipakai pasti versi Salary Structure yang sekarang.
	for structure in {d.salary_structure for d in slips if d.salary_structure}:
		frappe.clear_document_cache("Salary Structure", structure)

	print("{0} Salary Slip draft akan dihitung ulang{1}.".format(
		len(slips), " (dry run, tidak disimpan)" if dry_run else ""
	))

	berubah = []
	gagal = []
	titik = "hitung_ulang_salary_slip"

	for i, d in enumerate(slips, 1):
		try:
			frappe.db.savepoint(titik)
			doc = frappe.get_doc("Salary Slip", d.name)

			if dry_run:
				doc.run_method("validate")
			else:
				doc.save()

			if flt(doc.net_pay, 2) != flt(d.net_pay, 2):
				berubah.append((d.name, flt(d.net_pay), flt(doc.net_pay)))

			if dry_run:
				frappe.db.rollback(save_point=titik)
		except Exception as e:
			frappe.db.rollback(save_point=titik)
			if frappe.message_log:
				frappe.message_log.pop()
			gagal.append((d.name, frappe.utils.strip_html(str(e)).strip()))

		if not dry_run and i % COMMIT_TIAP == 0:
			frappe.db.commit()
			print("  {0}/{1}".format(i, len(slips)))

	if not dry_run:
		frappe.db.commit()

	print("")
	print("Selesai: {0} slip, {1} net pay-nya berubah, {2} gagal.".format(
		len(slips), len(berubah), len(gagal)
	))

	for nama, lama, baru in berubah[:50]:
		print("  {0:45} {1:>16,.2f} -> {2:>16,.2f}".format(nama, lama, baru))
	if len(berubah) > 50:
		print("  ... dan {0} slip lain".format(len(berubah) - 50))

	if gagal:
		print("")
		print("Tidak bisa disimpan ulang, perlu dilihat sendiri:")
		for nama, sebab in gagal:
			print("  {0:45} {1}".format(nama, sebab[:150]))
