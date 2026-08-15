import frappe

# Diambil dari modulnya langsung, bukan lewat frappe.rename_doc: pintasan di
# frappe/__init__.py tidak meneruskan ignore_permissions ke fungsi aslinya.
from frappe.model.rename_doc import rename_doc

DOCTYPE = "TPH"

# Cuma kebun ini yang dikembalikan; divisi lain tetap berprefiks.
UNIT = "TPRE"

# TPH-nya ribuan, dan tiap rename menyentuh beberapa tabel sekaligus. Kabar
# kemajuan dicetak sesekali supaya migrate yang berjalan lama tidak kelihatan
# seperti menggantung.
SETIAP = 500


def execute():
	"""Kembalikan nama TPH milik Unit TPRE mengikuti Bloknya yang sudah bernama lama.

	Nama TPH disusun dari nama Bloknya ditambah nomor urut. Sesudah Blok TPRE
	dikembalikan (lihat kembalikan_nama_blok_tpre), TPH-nya jadi satu-satunya yang
	masih berprefiks kode divisi.

	Sama seperti waktu berangkat, nama barunya diturunkan dari data: kode divisi
	diambil dari Blok yang ditunjuk TPH, lalu dilepas dari depan nama TPH. Yang
	tersisa harus diawali nama Bloknya sendiri — kalau tidak, TPH itu dilewati dan
	dilaporkan, bukan ditebak.

	Field `nama` yang isinya sama persis dengan kode ikut disamakan lagi sesudahnya.

	Patch ini aman diulang, dan aman dijalankan sebelum Bloknya sempat
	dikembalikan: TPH milik Blok yang masih berprefiks dilewati.
	"""
	rencana = _susun_rencana()

	for nomor, (lama, baru) in enumerate(rencana["kembali"], start=1):
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
			print(f"  ... {nomor} dari {len(rencana['kembali'])} TPH")
			frappe.db.commit()

	frappe.db.commit()

	# Dijalankan atas yang baru dikembalikan sekaligus yang sudah bernama lama
	# sejak sebelumnya, supaya baris yang tertinggal dari percobaan yang putus di
	# tengah jalan ikut dirapikan.
	nama = _samakan_nama([baru for _, baru in rencana["kembali"] + rencana["sudah"]])

	frappe.db.commit()

	_cetak_laporan(rencana, nama)


def _susun_rencana():
	"""Pilah tiap TPH TPRE menurut keadaannya, tanpa mengubah apa pun.

	Semua diperiksa dulu sebelum satu pun diganti, supaya patch tidak berhenti di
	tengah dengan sebagian TPH bernama lama dan sebagian masih berprefiks.
	"""
	rencana = {
		"kembali": [],
		"sudah": [],
		"tanpa_divisi": [],
		"blok_belum_kembali": [],
		"pola_lain": [],
		"bentrok": [],
	}

	blok_tpre = {
		b.name: b.divisi
		for b in frappe.get_all(
			"Blok", filters={"unit": UNIT}, fields=["name", "divisi"], limit_page_length=0
		)
	}

	tph = frappe.get_all(DOCTYPE, fields=["name", "blok"], limit_page_length=0)
	nama_terpakai = {t.name for t in tph}

	for t in tph:
		# TPH di luar TPRE bukan urusan patch ini, termasuk yang tidak punya Blok:
		# penamaannya sudah selesai sejak patch berprefiks
		if not t.blok or t.blok not in blok_tpre:
			continue

		divisi = blok_tpre[t.blok]

		if not divisi:
			# tanpa Divisi tidak ada kode yang bisa dilepas
			rencana["tanpa_divisi"].append(t.name)
			continue

		if t.blok.startswith(divisi):
			# Bloknya masih berprefiks: entah patch Bloknya belum jalan, entah blok
			# itu termasuk yang dilewati di sana. Dua-duanya bukan urusan patch ini
			# untuk ditebak.
			rencana["blok_belum_kembali"].append((t.name, t.blok))
			continue

		if t.name.startswith(t.blok):
			rencana["sudah"].append((t.name, t.name))
			continue

		sisa = t.name[len(divisi):] if t.name.startswith(divisi) else ""

		if not sisa.startswith(t.blok):
			rencana["pola_lain"].append((t.name, t.blok))
			continue

		if sisa in nama_terpakai:
			rencana["bentrok"].append((t.name, sisa))
			continue

		# didaftarkan sekarang juga supaya dua TPH tidak bisa dijadwalkan ke nama
		# yang sama dalam satu putaran
		nama_terpakai.add(sisa)
		rencana["kembali"].append((t.name, sisa))

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
	print(f"Kembalikan nama TPH {UNIT}: {len(rencana['kembali'])} TPH dikembalikan ke nama lama")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} TPH sudah bernama lama sejak sebelumnya, dilewati")

	if nama:
		print(f"  {nama} TPH field Nama-nya disamakan dengan nama dokumen")

	for kunci, keterangan in (
		("tanpa_divisi", "TPH Bloknya tanpa Divisi, jadi kode yang dilepas tidak bisa dipastikan"),
		("blok_belum_kembali", "TPH Bloknya masih diawali kode divisi"),
		("pola_lain", "TPH kodenya tidak diawali kode divisi + nama Blok, jadi tidak bisa diturunkan"),
		("bentrok", "TPH TIDAK dikembalikan karena nama lamanya sudah dipakai dokumen lain"),
	):
		daftar = rencana[kunci]
		if daftar:
			print(f"  PERIKSA: {len(daftar)} {keterangan}: {_ringkas(daftar)}")


def _ringkas(daftar, batas=20):
	"""Sebutkan sebagian saja kalau daftarnya panjang — ini keluaran migrate,
	bukan laporan."""
	isi = [nilai if isinstance(nilai, str) else " -> ".join(nilai) for nilai in daftar[:batas]]
	sisa = len(daftar) - len(isi)

	return ", ".join(isi) + (f", dan {sisa} lainnya" if sisa > 0 else "")
