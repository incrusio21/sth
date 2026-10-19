import frappe

from sth.overrides.salary_slip import BPJS_PERUSAHAAN

# Hutang BPJS, satu nomor akun di semua company (dari sheet Salary Component ERPNext)
NOMOR_AKUN_HUTANG_BPJS = "2161003"


def execute(terapkan=0):
	"""Isi Akun Potongan komponen BPJS beban perusahaan dengan hutang BPJS.

	Sejak beban perusahaan dipotong balik di deductions slip, accrual Payroll
	Entry mengkredit Akun Potongan komponennya. Yang kosong ditolak accrual
	dengan pesan "Akun Komponen Belum Diisi".

	Komponennya dikenali dari Set Up BPJS PT (kolom perusahaan), Employee
	Payment Log beban perusahaan, dan Salary Component earning bernama
	"BPJS..." (komponen Mill yang belum dipakai master mana pun), lalu tiap
	baris tabel Accounts-nya diisi
	2161003 HUTANG BPJS milik company baris itu. Yang sudah terisi dibiarkan.

	Tanpa terapkan=1 cuma melaporkan. Tidak didaftarkan di patches.txt: field
	Akun Potongan baru terpasang sesudah semua patch, jadi dijalankan manual
	sesudah migrate:

	    bench --site <site> execute sth.patches.isi_akun_potongan_bpjs_perusahaan.execute --kwargs "{'terapkan': 1}"
	"""
	komponen = set(frappe.get_all(
		"Set Up BPJS PT Table",
		filters={"salary_component_perusahaan": ["is", "set"]},
		pluck="salary_component_perusahaan",
		distinct=True,
	)) | set(frappe.get_all(
		"Employee Payment Log",
		filters={"component_type": BPJS_PERUSAHAAN, "salary_component": ["is", "set"]},
		pluck="salary_component",
		distinct=True,
	)) | set(frappe.get_all(
		"Salary Component",
		filters={"type": "Earning", "name": ["like", "BPJS%"]},
		pluck="name",
	))

	akun_hutang = dict(frappe.get_all(
		"Account",
		filters={"account_number": NOMOR_AKUN_HUTANG_BPJS, "is_group": 0},
		fields=["company", "name"],
		as_list=True,
	))

	diisi, tanpa_hutang, tanpa_baris = [], [], []
	for nama in sorted(komponen):
		baris = frappe.get_all(
			"Salary Component Account",
			filters={"parent": nama, "parenttype": "Salary Component"},
			fields=["name", "company", "akun_potongan"],
		)
		if not baris:
			tanpa_baris.append(nama)

		for b in baris:
			if b.akun_potongan:
				continue

			akun = akun_hutang.get(b.company)
			if not akun:
				tanpa_hutang.append(f"{nama} / {b.company}")
				continue

			diisi.append(f"{nama} / {b.company} -> {akun}")
			if frappe.utils.cint(terapkan):
				frappe.db.set_value("Salary Component Account", b.name, "akun_potongan", akun,
					update_modified=False)

	print(f"Komponen BPJS perusahaan: {len(komponen)}")
	cetak("Diisi" if frappe.utils.cint(terapkan) else "Akan diisi", diisi)
	cetak(f"Company tanpa akun {NOMOR_AKUN_HUTANG_BPJS}, dilewati", tanpa_hutang)
	cetak("Komponen tanpa baris Accounts sama sekali", tanpa_baris)

	if frappe.utils.cint(terapkan):
		frappe.db.commit()
	else:
		print("\nBelum ada yang diubah. Jalankan dengan terapkan=1 untuk mengisi.")


def cetak(judul, daftar):
	print(f"\n{judul}: {len(daftar)}")
	for d in daftar:
		print(f"  {d}")
