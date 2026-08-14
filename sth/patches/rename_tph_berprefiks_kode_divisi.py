import frappe

# Diambil dari modulnya langsung, bukan lewat frappe.rename_doc: pintasan di
# frappe/__init__.py tidak meneruskan ignore_permissions ke fungsi aslinya.
from frappe.model.rename_doc import rename_doc

DOCTYPE = "TPH"

# TPH-nya ribuan, dan tiap rename menyentuh beberapa tabel sekaligus. Kabar
# kemajuan dicetak sesekali supaya migrate yang berjalan lama tidak kelihatan
# seperti menggantung.
SETIAP = 500


def execute():
	"""Ganti nama TPH mengikuti Blok yang sudah berprefiks kode divisi.

	Nama TPH disusun dari nama Bloknya ditambah nomor urut — "A06a-001" untuk
	Blok "A06a". Sesudah Blok diawali kode divisi (lihat
	rename_blok_berprefiks_kode_divisi), nama TPH jadi satu-satunya yang masih
	memakai penyebutan lama, dan sama tidak uniknya seperti Blok dulu: nomor
	"A06a-001" bisa muncul di dua kebun sekaligus.

	Nama barunya diturunkan dari data, bukan dari daftar tersendiri: kode divisi
	diambil dari Blok yang ditunjuk TPH, lalu ditempelkan di depan kode lama.
	Hasilnya sama saja dengan menempelkan sisa kode di belakang nama Blok yang
	baru — "A06a-001" pada Blok "ASRE01A06a" jadi "ASRE01A06a-001". TPH yang
	kodenya tidak mengikuti pola itu tidak ditebak-tebak: dilewati dan
	dilaporkan di akhir.

	Karena TPH dinamai `field:kode`, nama dokumen dan isi field `kode` bergerak
	bersama lewat frappe.rename_doc, berikut field Link yang menunjuk TPH.
	Field `nama` yang selama ini isinya sama persis dengan kode ikut disamakan
	lagi sesudahnya.

	Patch ini aman diulang, dan aman dijalankan sebelum Bloknya sempat diganti
	nama: TPH milik Blok yang belum berprefiks dilewati, bukan dinamai asal.
	"""
	rencana = _susun_rencana()

	for nomor, (lama, baru) in enumerate(rencana["ganti"], start=1):
		rename_doc(
			DOCTYPE,
			lama,
			baru,
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)

		if nomor % SETIAP == 0:
			print(f"  ... {nomor} dari {len(rencana['ganti'])} TPH")
			frappe.db.commit()

	frappe.db.commit()

	# Dijalankan atas yang baru diganti sekaligus yang sudah bernama baru sejak
	# sebelumnya, supaya baris yang tertinggal dari percobaan yang putus di
	# tengah jalan ikut dirapikan.
	nama = _samakan_nama([baru for _, baru in rencana["ganti"] + rencana["sudah"]])

	frappe.db.commit()

	_cetak_laporan(rencana, nama)


def _susun_rencana():
	"""Pilah tiap TPH menurut keadaannya, tanpa mengubah apa pun.

	Semua diperiksa dulu sebelum satu pun diganti, supaya patch tidak berhenti
	di tengah dengan sebagian TPH bernama baru dan sebagian belum.
	"""
	rencana = {
		"ganti": [],
		"sudah": [],
		"tanpa_blok": [],
		"blok_belum_pindah": [],
		"pola_lain": [],
		"bentrok": [],
	}

	divisi_blok = {
		b.name: b.divisi
		for b in frappe.get_all("Blok", fields=["name", "divisi"], limit_page_length=0)
	}

	tph = frappe.get_all(DOCTYPE, fields=["name", "blok"], limit_page_length=0)
	nama_terpakai = {t.name for t in tph}

	for t in tph:
		blok = t.blok
		divisi = divisi_blok.get(blok) if blok else None

		if not blok or not divisi:
			# tanpa Blok — atau Bloknya tanpa Divisi — tidak ada asal-usul kode
			# divisi yang bisa dipercaya
			rencana["tanpa_blok"].append(t.name)
			continue

		if not blok.startswith(divisi):
			# Bloknya belum diawali kode divisi: entah patch Blok belum jalan,
			# entah blok itu memang di luar pemetaan. Dua-duanya bukan urusan
			# patch ini untuk ditebak.
			rencana["blok_belum_pindah"].append((t.name, blok))
			continue

		if t.name.startswith(blok):
			rencana["sudah"].append((t.name, t.name))
			continue

		blok_lama = blok[len(divisi):]

		if not t.name.startswith(blok_lama):
			rencana["pola_lain"].append((t.name, blok))
			continue

		baru = blok + t.name[len(blok_lama):]

		if baru in nama_terpakai:
			rencana["bentrok"].append((t.name, baru))
			continue

		# didaftarkan sekarang juga supaya dua TPH tidak bisa dijadwalkan ke
		# nama yang sama dalam satu putaran
		nama_terpakai.add(baru)
		rencana["ganti"].append((t.name, baru))

	return rencana


def _samakan_nama(nama_baru):
	"""Isi field `nama` dengan nama dokumennya sendiri.

	Ditulis lewat SQL, bukan lewat dokumen: yang disalin cuma satu kolom, dan
	memuat ribuan dokumen satu per satu untuk itu tidak sebanding. `modified`
	sengaja dibiarkan supaya jejak perubahan dokumennya tidak bergeser gara-gara
	patch.
	"""
	if not nama_baru:
		return 0

	belum_sama = "name IN %s AND (nama IS NULL OR nama != name)"
	nama_baru = tuple(nama_baru)

	# dihitung lebih dulu: UPDATE tidak mengembalikan jumlah baris lewat frappe.db.sql
	jumlah = frappe.db.sql(f"SELECT COUNT(*) FROM `tabTPH` WHERE {belum_sama}", (nama_baru,))[0][0]

	if jumlah:
		frappe.db.sql(f"UPDATE `tabTPH` SET nama = name WHERE {belum_sama}", (nama_baru,))

	return jumlah


def _cetak_laporan(rencana, nama):
	print(f"Rename TPH: {len(rencana['ganti'])} TPH diganti namanya")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} TPH sudah bernama baru sejak sebelumnya, dilewati")

	if nama:
		print(f"  {nama} TPH field Nama-nya disamakan dengan nama dokumen")

	for kunci, keterangan in (
		("tanpa_blok", "TPH tidak punya Blok, atau Bloknya tanpa Divisi"),
		("blok_belum_pindah", "TPH Bloknya belum diawali kode divisi"),
		("pola_lain", "TPH kodenya tidak diawali nama Blok, jadi tidak bisa diturunkan"),
		("bentrok", "TPH TIDAK diganti karena nama barunya sudah dipakai dokumen lain"),
	):
		daftar = rencana[kunci]
		if daftar:
			print(f"  {len(daftar)} {keterangan}: {_ringkas(daftar)}")


def _ringkas(daftar, batas=20):
	"""Sebutkan sebagian saja kalau daftarnya panjang — ini keluaran migrate,
	bukan laporan."""
	isi = [nilai if isinstance(nilai, str) else " -> ".join(nilai) for nilai in daftar[:batas]]
	sisa = len(daftar) - len(isi)

	return ", ".join(isi) + (f", dan {sisa} lainnya" if sisa > 0 else "")
