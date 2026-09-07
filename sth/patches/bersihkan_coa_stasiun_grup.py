import frappe

from sth.custom.employee import akun_stasiun


def execute():
	"""Kosongkan COA Stasiun karyawan yang isinya bukan pilihan yang sah lagi.

	Sebelum ini, stasiun yang namanya mengandung UMUM memakai akun Station
	Procurement Settings itu sendiri sebagai COA Stasiun. Akun itu ternyata akun
	grup — 72110 BIAYA PEGAWAI STAF DAN NON-STAFF, yang punya lima belas anak —
	dan akun grup ditolak GL Entry, jadi Costing Mill di unit yang memuat
	karyawan tersebut tidak bisa disubmit sama sekali.

	Sekarang yang menentukan punya-tidaknya anak, bukan nama stasiunnya, jadi
	nilai lama itu tidak ada lagi di daftar pilihan. set_coa_stasiun sebenarnya
	membuangnya sendiri, tapi baru waktu dokumen karyawannya disimpan; sampai
	itu terjadi kolomnya masih memegang akun grup dan Costing Mill tetap gagal.

	Dikosongkan, bukan ditebak isinya. Karyawan yang COA Stasiunnya kosong jatuh
	ke get_coa_operasional_stasiun, yaitu akun bernomor grup + '01' — untuk UMUM
	berarti 7211001 GAJI (STAF), TUNJANGAN DAN MANFAAT. Kalau yang dikehendaki
	akun lain di antara kelima belas anak itu, pilih sendiri di form karyawan.

	Aman dijalankan ulang: karyawan yang COA Stasiunnya sudah sah dilewati.
	"""
	karyawan = frappe.get_all(
		"Employee",
		filters={"coa_stasiun": ("is", "set")},
		fields=["name", "employee_name", "company", "stasiun", "coa_stasiun"],
		order_by="name",
		limit_page_length=0,
	)

	pilihan = {}
	dikosongkan = []

	for row in karyawan:
		kunci = (row.stasiun, row.company)
		if kunci not in pilihan:
			pilihan[kunci] = akun_stasiun(row.stasiun, row.company)

		if row.coa_stasiun in pilihan[kunci]:
			continue

		# Langsung ke kolomnya: yang diubah cuma satu field dan dokumennya tidak
		# perlu divalidasi ulang — validate akan mengosongkannya juga.
		frappe.db.set_value("Employee", row.name, "coa_stasiun", None, update_modified=False)
		dikosongkan.append(row)

	frappe.db.commit()

	if not dikosongkan:
		print("COA Stasiun semua karyawan sudah sah, tidak ada yang dikosongkan.")
		return

	print("{0} karyawan dikosongkan COA Stasiunnya:".format(len(dikosongkan)))
	for row in dikosongkan:
		print("  {0}  {1}  {2}".format(row.name, row.employee_name, row.coa_stasiun))
	print("Selanjutnya mereka memakai akun OPERASIONAL stasiunnya lewat Costing Mill.")
