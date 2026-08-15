import frappe

# Diambil dari modulnya langsung, bukan lewat frappe.rename_doc: pintasan di
# frappe/__init__.py tidak meneruskan ignore_permissions ke fungsi aslinya.
from frappe.model.rename_doc import rename_doc

DOCTYPE = "Blok"

# Cuma kebun ini yang dikembalikan; divisi lain tetap berprefiks.
UNIT = "TPRE"

# Kolom bertipe Data yang menyimpan nama Blok apa adanya. Sama seperti waktu
# berangkat, rename_doc cuma menyusuri field Link dan Dynamic Link, jadi kolom
# seperti ini tetap memegang nama berprefiks kalau tidak diperbaiki sendiri.
KOLOM_TEKS = (
	("Sortasi", "blok"),
	("Detail Pekerjaan Traksi", "blok"),
)


def execute():
	"""Kembalikan nama Blok milik Unit TPRE ke nama lamanya, mis. "TPRE01A24l" -> "A24l".

	rename_blok_berprefiks_kode_divisi mengawali seluruh nama Blok dengan kode
	divisi. Untuk TPRE penamaan itu ditarik kembali; sebelas divisi di kebun lain
	tetap seperti sesudah patch tersebut.

	Nama lamanya dibaca dari field `nama`, yang tidak ikut disentuh patch
	berprefiks. Nama itu dicocokkan dulu dengan nama dokumen tanpa kode divisi —
	dua-duanya harus menyebut petak yang sama. Yang tidak cocok dilewati dan
	dilaporkan, bukan dipilih salah satu diam-diam.

	Deskripsi sengaja tidak ikut dikembalikan. Sesudah nama dokumen TPRE bernama
	lama lagi, Deskripsi-lah satu-satunya penyebutan Blok yang masih unik di
	seluruh sistem — dan Cost Center Blok dinamai dari situ, jadi Cost Center yang
	sudah ada beserta seluruh GL-nya tetap terpanggil tanpa perlu dibuat ulang.
	Blok yang Deskripsi-nya kosong atau belum punya Cost Center dilaporkan di
	akhir.

	Patch ini aman diulang, dan aman dijalankan di database yang Bloknya belum
	pernah berprefiks: yang sudah bernama lama dianggap selesai.
	"""
	rencana = _susun_rencana()

	for lama, baru in rencana["kembali"]:
		rename_doc(
			DOCTYPE,
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

	_cetak_laporan(rencana, teks, tanpa_cc)


def _susun_rencana():
	"""Pilah tiap Blok TPRE menurut keadaannya, tanpa mengubah apa pun.

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

	# seluruh Blok, bukan cuma TPRE: nama lama yang dituju bisa saja sudah dipakai
	# blok di kebun lain — persis keadaan yang bikin prefiks ini ada
	nama_terpakai = set(frappe.get_all(DOCTYPE, pluck="name", limit_page_length=0))

	bloks = frappe.get_all(
		DOCTYPE,
		filters={"unit": UNIT},
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

	Cuma dilaporkan, tidak dibuatkan: Cost Center TPRE sudah ada sejak sebelum
	blok-bloknya berganti nama, jadi yang tidak ketemu di sini pertanda ada yang
	tidak beres — bukan pekerjaan yang tertinggal.
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


def _cetak_laporan(rencana, teks, tanpa_cc):
	print(f"Kembalikan nama Blok {UNIT}: {len(rencana['kembali'])} blok dikembalikan ke nama lama")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} blok sudah bernama lama sejak sebelumnya, dilewati")

	for kolom, jumlah in teks.items():
		print(f"  {jumlah} baris {kolom} ikut disesuaikan")

	for kunci, keterangan in (
		("tanpa_divisi", "blok tidak punya Divisi, jadi kode yang dilepas tidak bisa dipastikan"),
		("tanpa_nama", "blok field Nama-nya kosong, jadi nama lamanya tidak diketahui"),
		("tak_berprefiks", "blok namanya tidak diawali kode divisi tapi berbeda dari field Nama"),
		("beda_nama", "blok field Nama-nya berbeda dari nama dokumen tanpa kode divisi"),
		("bentrok", "blok TIDAK dikembalikan karena nama lamanya sudah dipakai dokumen lain"),
		("tanpa_deskripsi", "blok Deskripsi-nya kosong, jadi Cost Center-nya tidak bisa dinamai"),
	):
		daftar = rencana[kunci]
		if daftar:
			print(f"  PERIKSA: {len(daftar)} {keterangan}: {_ringkas(daftar)}")

	if tanpa_cc:
		print(
			f"  PERIKSA: {len(tanpa_cc)} Deskripsi belum punya Cost Center senama, "
			f"jadi pemakaian berikutnya membuat Cost Center baru yang kosong: {_ringkas(tanpa_cc)}"
		)


def _ringkas(daftar, batas=20):
	"""Sebutkan sebagian saja kalau daftarnya panjang — ini keluaran migrate,
	bukan laporan."""
	isi = [nilai if isinstance(nilai, str) else " -> ".join(nilai) for nilai in daftar[:batas]]
	sisa = len(daftar) - len(isi)

	return ", ".join(isi) + (f", dan {sisa} lainnya" if sisa > 0 else "")
