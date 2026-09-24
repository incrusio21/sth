import csv

import frappe
from frappe.utils import cstr

# Pemetaan nama dokumen -> unit, kebun, divisi yang benar, satu baris per
# Security Check Point. Disusun dari sheet "Security Check Point (cek1).xlsx"
# yang diperiksa per pabrik (TPRM, ASRM, ABAM), dipisah dari kode supaya bisa
# dibandingkan dengan excelnya sebagai tabel.
#
# Baris excel dicocokkan ke dokumen lewat Trans No saja — kolom ID di sheet per
# pabrik tidak sejajar dengan isi barisnya. Dokumen tanpa Trans No, dan Trans No
# yang muncul dua kali di excel dengan kebun/divisi berbeda, sengaja tidak dimuat.
BERKAS = ("sth", "file", "koreksi_unit_kebun_security_check_point.csv")

FIELDS = ("unit", "kebun", "divisi")

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 20


def execute(names=None, simpan=True, dorong_ke_spb=True):
	"""Betulkan unit, kebun, dan divisi Security Check Point September 2026.

	Isian pos selama ini campur aduk: `unit` sebagian berisi kebun (TPRE, TMDE,
	ASOE) padahal mestinya pabrik tempat posnya berdiri, `kebun` sebagian masih
	kode pabrik atau kosong, dan `divisi` banyak yang tertinggal divisi pabrik
	(MILL-TPRM, MILL-ASRM). Nilai yang benar sudah diperiksa orang pabrik di
	excel, dan itu yang dituliskan di sini.

	Sel yang kosong di excel artinya "tidak tahu", bukan "kosongkan": nilai yang
	sudah tersimpan dibiarkan. Divisi di excel ditulis sebagai nama tampilnya
	("DIVISI 07 TPRE"), jadi dicari lewat `nama` di dalam kebunnya; kalau sudah
	berupa kode (ASOE01) dipakai langsung. Divisi yang tidak ketemu atau bukan
	milik kebunnya tidak ditulis dan dilaporkan di akhir — unit dan kebun baris
	itu tetap dibetulkan.

	Ditulis lewat db.set_value karena hampir semuanya sudah submit. Yang sudah
	dibatalkan ikut dibetulkan supaya isiannya tidak berbeda dari amend-nya;
	yang nilainya sudah sama tidak disentuh, jadi patch ini aman diulang.

	**SPB dan Timbangan-nya ikut dibetulkan**, persis seperti kalau pos
	dibetulkan lewat form: begitu kebun pos berbeda dari unitnya, koreksi_pos
	menganggapnya koreksi, dan tanpa didorong sekarang pun kiriman EPCS berikutnya
	akan menariknya ke SPB lewat _ambil_koreksi_pos — cuma tidak jelas kapan.
	Yang didorong hanya pos yang sudah submit, sama dengan _ambil_koreksi_pos:
	pos yang dibatalkan ikut dibetulkan isinya tapi tidak menyentuh SPB. Pos
	diurutkan menurut waktu dibuat, jadi kalau satu SPB punya dua pos, yang
	terakhir yang menang, sama dengan _ambil_koreksi_pos.

	Tidak didaftarkan di patches.txt; jalankan sendiri:

	    bench --site <site> execute sth.patches.koreksi_unit_kebun_security_check_point.execute

	Uji coba tanpa menulis apa pun, untuk sebagian dokumen saja, atau tanpa
	menyentuh SPB:

	    from sth.patches.koreksi_unit_kebun_security_check_point import execute
	    execute(simpan=False)
	    execute(["REC-010926-027", "REC-010926-028"])
	    execute(dorong_ke_spb=False)
	"""
	pemetaan = _baca_pemetaan(names)
	rencana = _susun_rencana(pemetaan)

	if simpan:
		for b in rencana["ubah"]:
			frappe.db.set_value("Security Check Point", b.name, dict(b.beda))

		frappe.db.commit()

	_cetak_ringkasan(rencana, simpan)

	if simpan and dorong_ke_spb:
		_dorong_ke_spb([b.name for b in rencana["ubah"] if b.lama.docstatus == 1])


def _baca_pemetaan(names=None):
	"""Baca berkas pemetaan jadi dict nama dokumen -> {unit, kebun, divisi}."""
	if isinstance(names, str):
		names = [n.strip() for n in names.split(",")]

	names = {n for n in (names or []) if n}

	pemetaan = {}
	with open(frappe.get_app_path(*BERKAS), encoding="utf-8") as f:
		for baris in csv.DictReader(f):
			name = cstr(baris.get("name")).strip()
			if not name or (names and name not in names):
				continue

			pemetaan[name] = {field: cstr(baris.get(field)).strip() for field in FIELDS}

	return pemetaan


def _susun_rencana(pemetaan):
	rencana = frappe._dict(ubah=[], sama=0, batal=[], hilang=[], unit_salah=[], divisi_salah=[])

	if not pemetaan:
		return rencana

	lama = {
		d.name: d
		for d in frappe.get_all(
			"Security Check Point",
			filters={"name": ["in", list(pemetaan)]},
			fields=["name", "docstatus", "creation", *FIELDS],
			limit_page_length=0,
		)
	}
	units = set(frappe.get_all("Unit", pluck="name"))

	for name, target in pemetaan.items():
		scp = lama.get(name)

		if not scp:
			rencana.hilang.append(name)
			continue

		salah = [target[f] for f in ("unit", "kebun") if target[f] and target[f] not in units]
		if salah:
			rencana.unit_salah.append((name, salah))
			continue

		baru = {}
		if target["unit"]:
			baru["unit"] = target["unit"]
		if target["kebun"]:
			baru["kebun"] = target["kebun"]

		if target["divisi"]:
			kebun = baru.get("kebun") or scp.kebun
			divisi = _cari_divisi(target["divisi"], kebun)

			if divisi:
				baru["divisi"] = divisi
			else:
				rencana.divisi_salah.append((name, target["divisi"], kebun))

		beda = {field: value for field, value in baru.items() if scp.get(field) != value}

		if not beda:
			rencana.sama += 1
			continue

		rencana.ubah.append(frappe._dict(name=name, creation=scp.creation, lama=scp, beda=beda))

		if scp.docstatus == 2:
			rencana.batal.append(name)

	rencana.ubah.sort(key=lambda b: b.creation)

	return rencana


def _cari_divisi(divisi, kebun):
	"""Kode Divisi dari kode atau nama tampilnya, asal milik `kebun`. None kalau tidak."""
	if not kebun:
		return None

	if frappe.db.get_value("Divisi", divisi, "unit") == kebun:
		return divisi

	kandidat = frappe.get_all("Divisi", filters={"nama": divisi, "unit": kebun}, pluck="name")

	# Nama tampil tidak dijamin unik; kalau kembar, lebih baik dilaporkan daripada
	# menebak salah satunya.
	return kandidat[0] if len(kandidat) == 1 else None


def _dorong_ke_spb(names):
	"""Turunkan koreksi pos ke SPB dan Timbangan-nya, lewat jalur yang sama dengan form."""
	docs = [frappe.get_doc("Security Check Point", name) for name in names]
	spbs = list({doc.spb for doc in docs if doc.spb})

	if not spbs:
		return

	spb_sebelum = _potret("Surat Pengantar Buah", {"name": ["in", spbs]}, ("unit", "divisi"))
	tiket_sebelum = _potret("Timbangan", {"spb": ["in", spbs], "docstatus": ["<", 2]}, ("kebun", "divisi_kebun"))

	for doc in docs:
		if doc.spb:
			doc.dorong_koreksi_ke_spb()

	frappe.db.commit()

	spb_sesudah = _potret("Surat Pengantar Buah", {"name": ["in", spbs]}, ("unit", "divisi"))
	tiket_sesudah = _potret("Timbangan", {"spb": ["in", spbs], "docstatus": ["<", 2]}, ("kebun", "divisi_kebun"))

	print(f"  SPB yang unit/divisinya ikut dibetulkan: {_hitung_beda(spb_sebelum, spb_sesudah)}")
	print(f"  Timbangan yang kebun/divisi_kebun-nya ikut dibetulkan: {_hitung_beda(tiket_sebelum, tiket_sesudah)}")


def _potret(doctype, filters, fields):
	"""Nilai `fields` per dokumen, untuk dibandingkan sebelum dan sesudah."""
	return {
		d.name: tuple(d.get(f) for f in fields)
		for d in frappe.get_all(doctype, filters=filters, fields=["name", *fields], limit_page_length=0)
	}


def _hitung_beda(sebelum, sesudah):
	return sum(1 for name, nilai in sesudah.items() if sebelum.get(name) != nilai)


def _cetak_ringkasan(rencana, simpan):
	kata = "dibetulkan" if simpan else "akan dibetulkan (uji coba, belum ditulis)"
	print(f"Unit/kebun/divisi Security Check Point: {len(rencana.ubah)} dokumen {kata}, {rencana.sama} sudah benar")

	rekap = {}
	for b in rencana.ubah:
		kunci = tuple(
			f"{field} {b.lama.get(field) or '(kosong)'} -> {b.beda[field]}" for field in FIELDS if field in b.beda
		)
		rekap[kunci] = rekap.get(kunci, 0) + 1

	for kunci, jumlah in sorted(rekap.items(), key=lambda pasangan: -pasangan[1])[:BATAS_RINCIAN]:
		print(f"  {jumlah:>4}  {', '.join(kunci)}")

	if len(rekap) > BATAS_RINCIAN:
		print(f"  ... dan {len(rekap) - BATAS_RINCIAN} pola lain")

	_cetak_daftar("Tidak ditemukan di site ini", rencana.hilang)
	_cetak_daftar("Di antaranya yang sudah dibatalkan (tidak didorong ke SPB)", rencana.batal)
	_cetak_daftar(
		"Unit/kebun tidak terdaftar, dilewati",
		[f"{name}: {', '.join(salah)}" for name, salah in rencana.unit_salah],
	)
	_cetak_daftar(
		"Divisi tidak ketemu di kebunnya, divisi dibiarkan",
		[f"{name}: {divisi} di {kebun or '(kebun kosong)'}" for name, divisi, kebun in rencana.divisi_salah],
	)


def _cetak_daftar(judul, baris):
	if not baris:
		return

	print(f"  {judul}: {len(baris)}")

	for b in baris[:BATAS_RINCIAN]:
		print(f"    {b}")

	if len(baris) > BATAS_RINCIAN:
		print(f"    ... dan {len(baris) - BATAS_RINCIAN} lain")
