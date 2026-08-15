"""Menarik kembali prefiks kode divisi dari nama Blok dan TPH, satu kebun sekali jalan.

rename_blok_berprefiks_kode_divisi mengawali seluruh nama Blok dengan kode
divisi, dan rename_tph_berprefiks_kode_divisi mengikutkan TPH-nya. Untuk sebagian
kebun penamaan itu ditarik kembali; kebun yang tidak disebut tetap seperti
sesudah kedua patch tersebut.

Ada kebun yang Bloknya tetap berprefiks tapi TPH-nya tidak; untuk itu ada
namai_tph_dari_nama_blok, yang menurunkan nama TPH dari field `nama` Blok alih-alih
dari nama dokumennya.

Isi berkas ini dipakai bersama oleh patch per kebun — lihat
kembalikan_nama_blok_tpre dan saudara-saudaranya. Yang membedakan cuma Unit yang
dikerjakan, jadi tiap kebun baru cukup satu patch tipis yang menyebut Unit-nya.
"""

import frappe

# Diambil dari modulnya langsung, bukan lewat frappe.rename_doc: pintasan di
# frappe/__init__.py tidak meneruskan ignore_permissions ke fungsi aslinya.
from frappe.model.rename_doc import rename_doc

# Kolom bertipe Data yang menyimpan nama Blok apa adanya. Sama seperti waktu
# berangkat, rename_doc cuma menyusuri field Link dan Dynamic Link, jadi kolom
# seperti ini tetap memegang nama berprefiks kalau tidak diperbaiki sendiri.
KOLOM_TEKS = (
	("Sortasi", "blok"),
	("Detail Pekerjaan Traksi", "blok"),
)

# TPH-nya ribuan, dan tiap rename menyentuh beberapa tabel sekaligus. Kabar
# kemajuan dicetak sesekali supaya migrate yang berjalan lama tidak kelihatan
# seperti menggantung.
SETIAP = 500


def kembalikan_blok(unit):
	"""Kembalikan nama Blok milik satu Unit ke nama lamanya, mis. "TMDE01A01a" -> "A01a".

	Nama lamanya dibaca dari field `nama`, yang tidak ikut disentuh patch
	berprefiks. Nama itu dicocokkan dulu dengan nama dokumen tanpa kode divisi —
	dua-duanya harus menyebut petak yang sama. Yang tidak cocok dilewati dan
	dilaporkan, bukan dipilih salah satu diam-diam.

	Deskripsi sengaja tidak ikut dikembalikan. Sesudah nama dokumennya bernama
	lama lagi, Deskripsi-lah satu-satunya penyebutan Blok yang unik di seluruh
	sistem — dan Cost Center Blok dinamai dari situ, jadi Cost Center yang sudah
	ada beserta seluruh GL-nya tetap terpanggil tanpa perlu dibuat ulang. Blok
	yang Deskripsi-nya kosong atau belum punya Cost Center dilaporkan di akhir.

	Aman diulang, dan aman dijalankan di database yang Bloknya belum pernah
	berprefiks: yang sudah bernama lama dianggap selesai.
	"""
	rencana = _susun_rencana_blok(unit)

	for lama, baru in rencana["kembali"]:
		rename_doc(
			"Blok",
			lama,
			baru,
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)

	frappe.db.commit()

	# Dijalankan atas yang baru dikembalikan sekaligus yang sudah bernama lama
	# sejak sebelumnya, supaya baris yang tertinggal dari percobaan yang putus di
	# tengah jalan ikut dirapikan. Nama lama dan nama berprefiks tidak pernah
	# beririsan, jadi mengulanginya tidak mengubah apa pun untuk kedua kalinya.
	pasangan = rencana["kembali"] + rencana["sudah"]

	teks = _perbaiki_kolom_teks(pasangan)

	frappe.db.commit()

	tanpa_cc = _cost_center_belum_ada(rencana["deskripsi"])

	_cetak_laporan_blok(unit, rencana, teks, tanpa_cc)


def kembalikan_tph(unit):
	"""Kembalikan nama TPH milik satu Unit mengikuti Bloknya yang sudah bernama lama.

	Nama TPH disusun dari nama Bloknya ditambah nomor urut. Sesudah Bloknya
	dikembalikan, TPH-nya jadi satu-satunya yang masih berprefiks kode divisi.

	Sama seperti waktu berangkat, nama barunya diturunkan dari data: kode divisi
	diambil dari Blok yang ditunjuk TPH, lalu dilepas dari depan nama TPH. Yang
	tersisa harus diawali nama Bloknya sendiri — kalau tidak, TPH itu dilewati dan
	dilaporkan, bukan ditebak.

	Field `nama` yang isinya sama persis dengan kode ikut disamakan lagi sesudahnya.

	Aman diulang, dan aman dijalankan sebelum Bloknya sempat dikembalikan: TPH
	milik Blok yang masih berprefiks dilewati.
	"""
	rencana = _susun_rencana_tph(unit)

	for nomor, (lama, baru) in enumerate(rencana["kembali"], start=1):
		rename_doc(
			"TPH",
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

	nama = _samakan_nama_tph([baru for _, baru in rencana["kembali"] + rencana["sudah"]])

	frappe.db.commit()

	_cetak_laporan_tph(unit, rencana, nama)


def namai_tph_dari_nama_blok(units):
	"""Namai TPH dari field `nama` Bloknya, bukan dari nama dokumen Blok.

	Untuk kebun yang Bloknya tetap diawali kode divisi, tapi TPH-nya dikehendaki
	memakai penyebutan lama: "ASRE01A06a-001" jadi "A06a-001" sementara Bloknya
	tetap bernama "ASRE01A06a".

	Nomor urut di belakang tidak diutak-atik — yang ditukar cuma bagian nama Blok
	di depannya, dan cuma kalau nama TPH itu memang diawali nama dokumen Bloknya.
	Yang tidak mengikuti pola itu dilewati dan dilaporkan.

	Perlu diingat, sesudah ini nama TPH tidak lagi dijamin unik oleh kode divisi;
	yang menjaganya tinggal pemeriksaan bentrok di sini. TPH yang nama barunya
	sudah dipakai dokumen lain tidak diganti, bukan ditimpa.

	Aman diulang: yang namanya sudah mengikuti field `nama` Blok dianggap selesai.
	"""
	rencana = _susun_rencana_tph_dari_nama(units)

	for nomor, (lama, baru) in enumerate(rencana["ganti"], start=1):
		rename_doc(
			"TPH",
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

	nama = _samakan_nama_tph([baru for _, baru in rencana["ganti"] + rencana["sudah"]])

	frappe.db.commit()

	print(
		f"TPH {'/'.join(units)} dinamai dari field Nama Blok: "
		f"{len(rencana['ganti'])} TPH diganti namanya"
	)

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} TPH sudah mengikuti field Nama Blok, dilewati")

	if nama:
		print(f"  {nama} TPH field Nama-nya disamakan dengan nama dokumen")

	_cetak_periksa(
		rencana,
		(
			("tanpa_nama_blok", "TPH Bloknya field Nama-nya kosong, jadi tidak ada nama yang bisa dipakai"),
			("pola_lain", "TPH kodenya tidak diawali nama Blok, jadi tidak bisa diturunkan"),
			("bentrok", "TPH TIDAK diganti karena nama barunya sudah dipakai dokumen lain"),
		),
	)


def _susun_rencana_tph_dari_nama(units):
	"""Pilah tiap TPH milik kebun-kebun ini, tanpa mengubah apa pun."""
	rencana = {
		"ganti": [],
		"sudah": [],
		"tanpa_nama_blok": [],
		"pola_lain": [],
		"bentrok": [],
	}

	blok_unit = {
		b.name: (b.nama or "").strip()
		for b in frappe.get_all(
			"Blok",
			filters={"unit": ["in", list(units)]},
			fields=["name", "nama"],
			limit_page_length=0,
		)
	}

	tph = frappe.get_all("TPH", fields=["name", "blok"], limit_page_length=0)
	nama_terpakai = {t.name for t in tph}

	for t in tph:
		# TPH di luar kebun ini bukan urusan patch, termasuk yang tidak punya Blok
		if not t.blok or t.blok not in blok_unit:
			continue

		nama_blok = blok_unit[t.blok]

		if not nama_blok:
			rencana["tanpa_nama_blok"].append(t.name)
			continue

		if t.name.startswith(t.blok):
			baru = nama_blok + t.name[len(t.blok):]
		elif t.name.startswith(nama_blok):
			# sudah memakai penyebutan lama; ikut didaftar supaya field `nama`
			# tetap dirapikan kalau putaran sebelumnya putus
			rencana["sudah"].append((t.name, t.name))
			continue
		else:
			rencana["pola_lain"].append((t.name, t.blok))
			continue

		if baru == t.name:
			rencana["sudah"].append((t.name, t.name))
			continue

		if baru in nama_terpakai:
			rencana["bentrok"].append((t.name, baru))
			continue

		# didaftarkan sekarang juga supaya dua TPH tidak bisa dijadwalkan ke nama
		# yang sama dalam satu putaran
		nama_terpakai.add(baru)
		rencana["ganti"].append((t.name, baru))

	return rencana


def _susun_rencana_blok(unit):
	"""Pilah tiap Blok milik Unit menurut keadaannya, tanpa mengubah apa pun.

	Semua diperiksa dulu sebelum satu pun diganti, supaya patch tidak berhenti di
	tengah jalan dengan sebagian blok bernama lama dan sebagian masih berprefiks.
	"""
	rencana = {
		"kembali": [],
		"sudah": [],
		"deskripsi": [],
		"tanpa_divisi": [],
		"tanpa_nama": [],
		"tanpa_deskripsi": [],
		"tak_berprefiks": [],
		"beda_nama": [],
		"bentrok": [],
	}

	# seluruh Blok, bukan cuma milik Unit ini: nama lama yang dituju bisa saja
	# sudah dipakai blok di kebun lain — persis keadaan yang bikin prefiks ini ada
	nama_terpakai = set(frappe.get_all("Blok", pluck="name", limit_page_length=0))

	bloks = frappe.get_all(
		"Blok",
		filters={"unit": unit},
		fields=["name", "nama", "divisi", "deskripsi"],
		limit_page_length=0,
	)

	for b in bloks:
		target = (b.nama or "").strip()

		if not b.divisi:
			# tanpa Divisi tidak ada kode yang bisa dilepas, jadi tidak ada
			# pembanding untuk memastikan field `nama` menyebut petak yang sama
			rencana["tanpa_divisi"].append(b.name)
			continue

		berprefiks = b.name.startswith(b.divisi)

		if target and b.name == target:
			# sudah bernama lama; pasangannya disusun ulang supaya kolom Data tetap
			# ikut dirapikan kalau putaran sebelumnya putus
			rencana["sudah"].append((b.divisi + b.name, b.name))
			_catat_deskripsi(rencana, b)
			continue

		if not target:
			rencana["tanpa_nama"].append(b.name)
			continue

		if not berprefiks:
			# namanya bukan hasil patch berprefiks, tapi juga tidak sama dengan
			# field `nama` — asal-usulnya tidak jelas, jadi tidak disentuh
			rencana["tak_berprefiks"].append((b.name, target))
			continue

		dari_prefiks = b.name[len(b.divisi):]

		if target != dari_prefiks:
			# field `nama` dan nama dokumen tanpa kode divisi menyebut dua hal
			# berbeda; cuma orang kebun yang tahu mana yang benar
			rencana["beda_nama"].append((b.name, target))
			continue

		if target in nama_terpakai:
			rencana["bentrok"].append((b.name, target))
			continue

		# didaftarkan sekarang juga supaya dua blok tidak bisa dijadwalkan ke nama
		# yang sama dalam satu putaran
		nama_terpakai.add(target)
		rencana["kembali"].append((b.name, target))
		_catat_deskripsi(rencana, b)

	return rencana


def _catat_deskripsi(rencana, b):
	"""Simpan Deskripsi blok yang ditangani — dari situlah Cost Center dinamai."""
	deskripsi = (b.deskripsi or "").strip()

	if deskripsi:
		rencana["deskripsi"].append(deskripsi)
	else:
		rencana["tanpa_deskripsi"].append(b.name)


def _perbaiki_kolom_teks(pasangan):
	"""Kembalikan nama Blok di kolom Data yang tidak ikut terbawa rename_doc."""
	hasil = {}

	if not pasangan:
		return hasil

	for doctype, kolom in KOLOM_TEKS:
		if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, kolom):
			continue

		tabel = f"tab{doctype}"

		# isi kolom didaftar dulu supaya cuma nama yang benar-benar dipakai yang
		# disentuh, dan jumlah baris terpengaruh bisa dihitung sebelum diubah
		terpakai = set(frappe.db.sql_list(f"SELECT DISTINCT `{kolom}` FROM `{tabel}`"))
		perlu = [(lama, baru) for lama, baru in pasangan if lama in terpakai]

		if not perlu:
			continue

		jumlah = frappe.db.sql(
			f"SELECT COUNT(*) FROM `{tabel}` WHERE `{kolom}` IN %s",
			(tuple(lama for lama, _ in perlu),),
		)[0][0]

		for lama, baru in perlu:
			frappe.db.sql(f"UPDATE `{tabel}` SET `{kolom}` = %s WHERE `{kolom}` = %s", (baru, lama))

		hasil[f"{doctype}.{kolom}"] = jumlah

	return hasil


def _cost_center_belum_ada(deskripsi):
	"""Deskripsi yang belum punya Cost Center senama.

	Cuma dilaporkan, tidak dibuatkan: Cost Center Blok baru lahir waktu Bloknya
	disimpan lewat dokumen atau waktu naik TM, jadi yang tidak ketemu di sini
	umumnya blok TBM yang memang belum pernah membutuhkannya.
	"""
	if not deskripsi:
		return []

	ada = set(
		frappe.get_all(
			"Cost Center",
			filters={"cost_center_name": ["in", list(set(deskripsi))]},
			pluck="cost_center_name",
			limit_page_length=0,
		)
	)

	return sorted(set(deskripsi) - ada)


def _susun_rencana_tph(unit):
	"""Pilah tiap TPH milik Unit menurut keadaannya, tanpa mengubah apa pun.

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

	blok_unit = {
		b.name: b.divisi
		for b in frappe.get_all(
			"Blok", filters={"unit": unit}, fields=["name", "divisi"], limit_page_length=0
		)
	}

	tph = frappe.get_all("TPH", fields=["name", "blok"], limit_page_length=0)
	nama_terpakai = {t.name for t in tph}

	for t in tph:
		# TPH di luar kebun ini bukan urusan patch, termasuk yang tidak punya Blok:
		# penamaannya sudah selesai sejak patch berprefiks
		if not t.blok or t.blok not in blok_unit:
			continue

		divisi = blok_unit[t.blok]

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


def _samakan_nama_tph(nama_baru):
	"""Isi field `nama` TPH dengan nama dokumennya sendiri.

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


def _cetak_laporan_blok(unit, rencana, teks, tanpa_cc):
	print(f"Kembalikan nama Blok {unit}: {len(rencana['kembali'])} blok dikembalikan ke nama lama")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} blok sudah bernama lama sejak sebelumnya, dilewati")

	for kolom, jumlah in teks.items():
		print(f"  {jumlah} baris {kolom} ikut disesuaikan")

	_cetak_periksa(
		rencana,
		(
			("tanpa_divisi", "blok tidak punya Divisi, jadi kode yang dilepas tidak bisa dipastikan"),
			("tanpa_nama", "blok field Nama-nya kosong, jadi nama lamanya tidak diketahui"),
			("tak_berprefiks", "blok namanya tidak diawali kode divisi tapi berbeda dari field Nama"),
			("beda_nama", "blok field Nama-nya berbeda dari nama dokumen tanpa kode divisi"),
			("bentrok", "blok TIDAK dikembalikan karena nama lamanya sudah dipakai dokumen lain"),
			("tanpa_deskripsi", "blok Deskripsi-nya kosong, jadi Cost Center-nya tidak bisa dinamai"),
		),
	)

	if tanpa_cc:
		print(
			f"  PERIKSA: {len(tanpa_cc)} Deskripsi belum punya Cost Center senama, "
			f"jadi pemakaian berikutnya membuat Cost Center baru yang kosong: {_ringkas(tanpa_cc)}"
		)


def _cetak_laporan_tph(unit, rencana, nama):
	print(f"Kembalikan nama TPH {unit}: {len(rencana['kembali'])} TPH dikembalikan ke nama lama")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} TPH sudah bernama lama sejak sebelumnya, dilewati")

	if nama:
		print(f"  {nama} TPH field Nama-nya disamakan dengan nama dokumen")

	_cetak_periksa(
		rencana,
		(
			("tanpa_divisi", "TPH Bloknya tanpa Divisi, jadi kode yang dilepas tidak bisa dipastikan"),
			("blok_belum_kembali", "TPH Bloknya masih diawali kode divisi"),
			("pola_lain", "TPH kodenya tidak diawali kode divisi + nama Blok, jadi tidak bisa diturunkan"),
			("bentrok", "TPH TIDAK dikembalikan karena nama lamanya sudah dipakai dokumen lain"),
		),
	)


def _cetak_periksa(rencana, keterangan):
	for kunci, sebutan in keterangan:
		daftar = rencana[kunci]
		if daftar:
			print(f"  PERIKSA: {len(daftar)} {sebutan}: {_ringkas(daftar)}")


def _ringkas(daftar, batas=20):
	"""Sebutkan sebagian saja kalau daftarnya panjang — ini keluaran migrate,
	bukan laporan."""
	isi = [nilai if isinstance(nilai, str) else " -> ".join(nilai) for nilai in daftar[:batas]]
	sisa = len(daftar) - len(isi)

	return ", ".join(isi) + (f", dan {sisa} lainnya" if sisa > 0 else "")
