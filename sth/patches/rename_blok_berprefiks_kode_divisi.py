import csv

import frappe

# Diambil dari modulnya langsung, bukan lewat frappe.rename_doc: pintasan di
# frappe/__init__.py tidak meneruskan ignore_permissions ke fungsi aslinya.
from frappe.model.rename_doc import rename_doc

DOCTYPE = "Blok"

# Pemetaan nama lama -> nama baru, satu baris per Blok. Sengaja disimpan sebagai
# berkas terpisah, bukan ditempel di dalam kode: daftarnya datang dari sheet
# excel yang disusun orang kebun, jadi lebih enak dibandingkan dan diperbaiki
# sebagai tabel.
BERKAS = ("sth", "file", "rename_blok.csv")

# Kolom bertipe Data yang menyimpan nama Blok apa adanya. frappe.rename_doc
# hanya menyusuri field bertipe Link dan Dynamic Link, jadi kolom seperti ini
# tetap memegang nama lama kalau tidak diperbaiki sendiri.
KOLOM_TEKS = (
	("Sortasi", "blok"),
	("Detail Pekerjaan Traksi", "blok"),
)


def execute():
	"""Ganti nama Blok jadi kode divisi + nama lama, mis. "G03a" -> "TMDE01G03a".

	Nama Blok cuma unik di dalam satu divisi — "A06a" di ASRE01 dan "A06a" di
	divisi lain adalah dua petak yang berbeda. Selama ini nama itu dipakai apa
	adanya sebagai nama dokumen, jadi begitu kebun kedua ikut masuk sistem,
	blok yang namanya kebetulan sama tidak bisa dibedakan lagi. Diawali kode
	divisi, namanya jadi unik di seluruh sistem.

	Karena Blok dinamai `field:blok`, nama dokumen dan isi field `blok` harus
	bergerak bersama; frappe.rename_doc yang mengurus keduanya sekaligus dengan
	seluruh field Link yang menunjuk ke Blok.

	Nama baru tiap Blok sama dengan Deskripsi-nya yang sekarang, dan Cost Center
	Blok selama ini dinamai dari Deskripsi itu — jadi Cost Center yang sudah ada
	otomatis sudah bernama benar dan tidak perlu ikut diganti. Blok yang
	Deskripsi-nya ternyata tidak sama dengan nama barunya dilaporkan di akhir:
	Cost Center miliknya bernama lain, dan pemakaian berikutnya akan membuat
	Cost Center baru yang kosong alih-alih memakai yang lama.

	Sesudah rename, Deskripsi disamakan dengan nama dokumen supaya keduanya
	tidak lagi bisa berbeda diam-diam.

	Patch ini aman diulang: pasangan yang nama barunya sudah ada dan nama
	lamanya sudah hilang dianggap selesai dan dilewati.
	"""
	pemetaan = _baca_pemetaan()

	rencana = _susun_rencana(pemetaan)

	for lama, baru in rencana["ganti"]:
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

	# Keduanya dijalankan atas seluruh pemetaan, bukan cuma yang baru diganti,
	# supaya baris yang tertinggal dari percobaan sebelumnya ikut kena. Nama lama
	# dan nama baru tidak pernah beririsan, jadi mengulanginya tidak mengubah apa
	# pun untuk kedua kalinya.
	teks = _perbaiki_kolom_teks(pemetaan)
	deskripsi = _samakan_deskripsi(pemetaan)

	frappe.db.commit()

	_cetak_laporan(rencana, teks, deskripsi)


def _baca_pemetaan():
	"""Baca berkas pemetaan jadi daftar pasangan (nama lama, nama baru)."""
	jalur = frappe.get_app_path(*BERKAS)

	pemetaan = []
	with open(jalur, encoding="utf-8") as f:
		for baris in csv.DictReader(f):
			lama = (baris.get("nama_lama") or "").strip()
			baru = (baris.get("nama_baru") or "").strip()
			if lama and baru and lama != baru:
				pemetaan.append((lama, baru))

	if not pemetaan:
		frappe.throw(f"Berkas pemetaan `{jalur}` kosong atau tidak terbaca")

	_pastikan_pemetaan_waras(pemetaan, jalur)

	return pemetaan


def _pastikan_pemetaan_waras(pemetaan, jalur):
	"""Tolak pemetaan yang tidak bisa dijalankan sebagai satu putaran.

	Nama lama atau nama baru yang muncul dua kali berarti ada dua blok
	diarahkan ke satu nama — hasilnya tergantung urutan baris, dan salah
	satunya pasti kalah. Nama yang muncul di kedua kolom (lama untuk satu
	baris, baru untuk baris lain) bikin urutan penggantian jadi penting; lebih
	baik dihentikan di sini daripada menghasilkan penamaan yang tidak jelas
	asal-usulnya.
	"""
	lama = [p[0] for p in pemetaan]
	baru = [p[1] for p in pemetaan]

	for daftar, sebutan in ((lama, "nama lama"), (baru, "nama baru")):
		kembar = sorted({n for n in daftar if daftar.count(n) > 1})
		if kembar:
			frappe.throw(f"{sebutan.capitalize()} kembar di `{jalur}`: {', '.join(kembar)}")

	beririsan = sorted(set(lama) & set(baru))
	if beririsan:
		frappe.throw(
			f"Nama berikut di `{jalur}` dipakai sebagai nama lama sekaligus nama baru, "
			f"penggantian jadi bergantung urutan: {', '.join(beririsan)}"
		)


def _susun_rencana(pemetaan):
	"""Pilah tiap pasangan menurut keadaannya di database.

	Semua diperiksa dulu sebelum satu pun diganti, supaya patch tidak berhenti
	di tengah jalan dengan sebagian blok sudah bernama baru dan sebagian belum.
	Deskripsi ikut dibaca di sini, selagi masih apa adanya.
	"""
	rencana = {"ganti": [], "sudah": [], "hilang": [], "bentrok": [], "beda_deskripsi": []}

	semua_nama = [nama for pasangan in pemetaan for nama in pasangan]
	deskripsi = dict(
		frappe.get_all(
			DOCTYPE,
			filters={"name": ["in", semua_nama]},
			fields=["name", "deskripsi"],
			as_list=True,
			limit_page_length=0,
		)
	)

	for lama, baru in pemetaan:
		ada_lama = lama in deskripsi
		ada_baru = baru in deskripsi

		if ada_lama and ada_baru:
			# dua dokumen berbeda memperebutkan satu nama; menggantinya berarti
			# menabrak dokumen yang sudah ada, jadi dilewati dan dilaporkan
			rencana["bentrok"].append((lama, baru))
			continue

		if ada_lama:
			rencana["ganti"].append((lama, baru))
		elif ada_baru:
			rencana["sudah"].append((lama, baru))
		else:
			rencana["hilang"].append((lama, baru))
			continue

		# Cost Center Blok dinamai dari Deskripsi. Selama Deskripsi sama dengan
		# nama baru, Cost Center yang sudah ada tetap terpakai sesudah kode
		# beralih membaca nama dokumen; kalau berbeda, Cost Center lama beserta
		# seluruh GL-nya akan ditinggalkan tanpa suara.
		sekarang = deskripsi[lama if ada_lama else baru]
		if sekarang != baru:
			rencana["beda_deskripsi"].append((baru, sekarang))

	return rencana


def _perbaiki_kolom_teks(pemetaan):
	"""Ganti nama Blok di kolom Data yang tidak ikut terbawa rename_doc."""
	hasil = {}

	for doctype, kolom in KOLOM_TEKS:
		if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, kolom):
			continue

		tabel = f"tab{doctype}"

		# isi kolom didaftar dulu supaya cuma nama yang benar-benar dipakai yang
		# disentuh, dan jumlah baris terpengaruh bisa dihitung sebelum diubah
		terpakai = set(frappe.db.sql_list(f"SELECT DISTINCT `{kolom}` FROM `{tabel}`"))
		perlu = [(lama, baru) for lama, baru in pemetaan if lama in terpakai]

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


def _samakan_deskripsi(pemetaan):
	"""Isi Deskripsi dengan nama dokumennya sendiri.

	Ditulis lewat SQL, bukan lewat dokumen, karena Blok punya on_update yang
	membuat Cost Center dan menyentuh field cost_center — pekerjaan yang tidak
	ada urusannya dengan menyalin satu kolom, dan berat kalau dijalankan untuk
	ratusan blok sekaligus. `modified` sengaja dibiarkan supaya jejak perubahan
	dokumennya tidak bergeser gara-gara patch.
	"""
	nama_baru = tuple(baru for _, baru in pemetaan)
	belum_sama = "name IN %s AND (deskripsi IS NULL OR deskripsi != name)"

	# dihitung lebih dulu: UPDATE tidak mengembalikan jumlah baris lewat frappe.db.sql
	jumlah = frappe.db.sql(f"SELECT COUNT(*) FROM `tabBlok` WHERE {belum_sama}", (nama_baru,))[0][0]

	if jumlah:
		frappe.db.sql(f"UPDATE `tabBlok` SET deskripsi = name WHERE {belum_sama}", (nama_baru,))

	return jumlah


def _cetak_laporan(rencana, teks, deskripsi):
	print(f"Rename Blok: {len(rencana['ganti'])} blok diganti namanya")

	if rencana["sudah"]:
		print(f"  {len(rencana['sudah'])} blok sudah bernama baru sejak sebelumnya, dilewati")

	if rencana["hilang"]:
		daftar = ", ".join(lama for lama, _ in rencana["hilang"])
		print(f"  {len(rencana['hilang'])} blok di berkas pemetaan tidak ada di database: {daftar}")

	if rencana["bentrok"]:
		daftar = ", ".join(f"{lama} -> {baru}" for lama, baru in rencana["bentrok"])
		print(
			f"  {len(rencana['bentrok'])} blok TIDAK diganti karena nama barunya sudah "
			f"dipakai dokumen lain: {daftar}"
		)

	for kolom, jumlah in teks.items():
		print(f"  {jumlah} baris {kolom} ikut disesuaikan")

	if deskripsi:
		print(f"  {deskripsi} blok Deskripsi-nya disamakan dengan nama dokumen")

	if rencana["beda_deskripsi"]:
		daftar = ", ".join(f"{baru} (deskripsi: {sekarang or '-'})" for baru, sekarang in rencana["beda_deskripsi"])
		print(
			f"  PERIKSA: {len(rencana['beda_deskripsi'])} blok Deskripsi-nya berbeda dari nama baru, "
			f"jadi Cost Center miliknya bernama lain dan tidak akan terpakai lagi: {daftar}"
		)
