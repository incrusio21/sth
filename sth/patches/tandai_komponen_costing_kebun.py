import frappe

from sth.accounting_sth.costing_kebun import FIELD_KOMPONEN_KEBUN

# Daftar yang dulu ditulis tetap di sth.accounting_sth.costing_kebun. Disimpan di
# sini, bukan di modul itu, supaya yang jadi acuan sehari-hari cuma centangan di
# masternya - daftar ini hanya dipakai sekali untuk mengisinya.
KOMPONEN = (
	"HKnE",
	"Lembur",
	"Natura",
	"Premi Kehadiran",
	"Premi Tutup Buku",
	"Gaji Pokok",
)

# BPJS beban perusahaan namanya bervariasi (JKK punya beberapa varian RS/RT/RSD),
# jadi dicari dengan pola, sama seperti penyaring lamanya.
POLA = (
	"BPJS% (Perusahaan)",
	"BPJS TK - JK%",
)


def execute():
	"""Centang "Dibagi ke Kegiatan Kebun" pada komponen yang dulu terdaftar di kode.

	Penyaring komponen Costing Panen dan Costing Perawatan pindah dari daftar tetap
	di kode ke centangan di master Salary Component. Tanpa patch ini tidak ada
	komponen yang tercentang, dan costing kebun jadi kosong tanpa pesan error apa
	pun - karena itu patch ini harus dijalankan sekali setelah bench migrate.

	Yang sudah tercentang dilewati, jadi aman dijalankan ulang, dan centangan yang
	ditambahkan orang tidak ikut dimatikan: patch ini cuma menyalakan.

	Komponen di daftar yang ternyata tidak ada di master didaftar di akhir untuk
	diperiksa - namanya mungkin sudah berubah, dan yang begitu harus dicentang
	sendiri.

	Dijalankan dengan:
		bench --site <site> execute sth.patches.tandai_komponen_costing_kebun.execute
	"""
	if not frappe.db.has_column("Salary Component", FIELD_KOMPONEN_KEBUN):
		print("Field {0} belum ada di Salary Component, jalankan bench migrate dulu.".format(
			FIELD_KOMPONEN_KEBUN
		))
		return

	nama = set(cocok_persis()) | set(cocok_pola())

	tidak_ada = [k for k in KOMPONEN if not frappe.db.exists("Salary Component", k)]

	baru = [n for n in sorted(nama) if not frappe.db.get_value("Salary Component", n, FIELD_KOMPONEN_KEBUN)]

	for n in baru:
		frappe.db.set_value("Salary Component", n, FIELD_KOMPONEN_KEBUN, 1)
		print("  dicentang: {0}".format(n))

	frappe.db.commit()

	print("{0} dari {1} komponen dicentang, sisanya sudah tercentang sebelumnya.".format(
		len(baru), len(nama)
	))

	laporkan_tidak_ada(tidak_ada)


def cocok_persis():
	"""Komponen yang namanya persis ada di daftar."""
	return frappe.get_all(
		"Salary Component",
		filters={"name": ("in", KOMPONEN)},
		pluck="name",
	)


def cocok_pola():
	"""Komponen BPJS beban perusahaan, dicari lewat pola namanya."""
	hasil = []

	for pola in POLA:
		hasil.extend(frappe.get_all(
			"Salary Component",
			filters={"name": ("like", pola)},
			pluck="name",
		))

	return hasil


def laporkan_tidak_ada(tidak_ada):
	"""Komponen di daftar yang tidak ketemu di master Salary Component."""
	if not tidak_ada:
		return

	print("{0} komponen di daftar tidak ada di master, centang sendiri penggantinya:".format(
		len(tidak_ada)
	))
	for nama in tidak_ada:
		print("  {0}".format(nama))
