import csv

import frappe
from frappe.utils import cint, cstr, flt

from sth.mill.doctype.security_check_point.security_check_point import nilai_per_blok
from sth.patches.koreksi_unit_kebun_security_check_point import _dorong_ke_spb

# Isian pos yang ikut dikirim tapi dibuang waktu kirimannya masuk, disalin dari
# log payload API Security Check Point 1-23 September 2026: total janjang dan
# brondolan, serta kebun dan divisi pengirim (spb_unit, spb_divisi). Hanya 65
# kiriman 22-23 September yang membawanya. spb_unit dan spb_divisi disimpan apa
# adanya — kiriman pos TPRM disambung "*" per blok — dan diurai dengan
# nilai_per_blok yang sama dengan jalur API.
BERKAS = ("sth", "file", "payload_security_check_point.csv")


def execute(names=None, simpan=True, dorong_ke_spb=True):
	"""Isi total janjang/brondolan dan kebun/divisi Security Check Point dari payload aslinya.

	Field-field itu belum ada, atau map_api_kebun_spb belum jalan, waktu
	kirimannya masuk — jadi angkanya dibuang frappe dan dokumennya tersimpan
	dengan kebun kosong dan divisi pos pabrik (MILL-TPRM, MILL-ASRM).

	**Total janjang dan brondolan** diisi kalau payload-nya membawa angka; yang
	null (semua kiriman pos TPRM) dibiarkan.

	**Kebun hanya diisi kalau masih kosong** — kebun yang sudah terisi bisa
	jadi hasil koreksi orang, lihat koreksi_unit_kebun_security_check_point.
	Divisinya ikut diganti bersama kebun. Kalau kebunnya sudah sama dengan
	payload tapi divisinya masih bukan milik kebun itu (sisa divisi pabrik),
	divisinya saja yang diisi. Divisi payload yang bukan milik kebunnya tidak
	ditulis dan dilaporkan.

	Dokumen dicari lewat nama dari respons API, lalu dipastikan trans_no-nya
	sama dengan kiriman; yang berbeda dilaporkan dan dilewati. Ditulis lewat
	db.set_value karena semuanya sudah submit, dan yang nilainya sudah sama tidak
	disentuh, jadi aman diulang.

	Kebun yang baru diisi ikut diturunkan ke SPB dan Timbangan-nya lewat
	dorong_koreksi_ke_spb, sama seperti patch koreksi_unit_kebun.

	Tidak didaftarkan di patches.txt; jalankan sendiri:

	    bench --site <site> execute sth.patches.isi_payload_security_check_point.execute

	Uji coba tanpa menulis apa pun, atau tanpa menyentuh SPB:

	    from sth.patches.isi_payload_security_check_point import execute
	    execute(simpan=False)
	    execute(dorong_ke_spb=False)
	"""
	rencana = _susun_rencana(_baca_berkas(names))

	if simpan:
		for b in rencana.ubah:
			frappe.db.set_value("Security Check Point", b.name, dict(b.beda))

		frappe.db.commit()

	_cetak_ringkasan(rencana, simpan)

	if simpan and dorong_ke_spb:
		_dorong_ke_spb([
			b.name for b in rencana.ubah
			if b.lama.docstatus == 1 and ("kebun" in b.beda or "divisi" in b.beda)
		])


def _baca_berkas(names=None):
	if isinstance(names, str):
		names = [n.strip() for n in names.split(",")]

	names = {n for n in (names or []) if n}

	baris = []
	with open(frappe.get_app_path(*BERKAS), encoding="utf-8") as f:
		for b in csv.DictReader(f):
			name = cstr(b.get("name")).strip()
			if not name or (names and name not in names):
				continue

			baris.append(frappe._dict(
				name=name,
				trans_no=cstr(b.get("trans_no")).strip(),
				# Sel kosong berarti payload-nya null, bukan nol.
				total_jjg=cint(b.get("total_jjg")) if cstr(b.get("total_jjg")).strip() else None,
				total_brd=flt(b.get("total_brd")) if cstr(b.get("total_brd")).strip() else None,
				kebun=nilai_per_blok(b.get("spb_unit")),
				divisi=nilai_per_blok(b.get("spb_divisi")),
			))

	return baris


def _susun_rencana(baris):
	rencana = frappe._dict(ubah=[], sama=0, hilang=[], trans_no_beda=[], kebun_lain=[], divisi_salah=[])

	if not baris:
		return rencana

	lama = {
		d.name: d
		for d in frappe.get_all(
			"Security Check Point",
			filters={"name": ["in", [b.name for b in baris]]},
			fields=["name", "docstatus", "creation", "trans_no", "total_jjg", "total_brd", "kebun", "divisi"],
			limit_page_length=0,
		)
	}

	for b in baris:
		scp = lama.get(b.name)

		if not scp:
			rencana.hilang.append(b.name)
			continue

		if cstr(scp.trans_no) != b.trans_no:
			rencana.trans_no_beda.append(f"{b.name}: {scp.trans_no or '(kosong)'} di site, {b.trans_no} di payload")
			continue

		beda = {}

		if b.total_jjg is not None and cint(scp.total_jjg) != b.total_jjg:
			beda["total_jjg"] = b.total_jjg
		if b.total_brd is not None and flt(scp.total_brd) != b.total_brd:
			beda["total_brd"] = b.total_brd

		beda.update(_kebun_divisi(scp, b, rencana))

		if not beda:
			rencana.sama += 1
			continue

		rencana.ubah.append(frappe._dict(name=b.name, creation=scp.creation, lama=scp, beda=beda))

	rencana.ubah.sort(key=lambda b: b.creation)

	return rencana


def _kebun_divisi(scp, b, rencana):
	"""Kebun dan divisi yang perlu ditulis untuk satu dokumen, {} kalau tidak ada."""
	if not b.kebun:
		return {}

	if scp.kebun and scp.kebun != b.kebun:
		rencana.kebun_lain.append(f"{scp.name}: {scp.kebun} di site, {b.kebun} di payload")
		return {}

	if not frappe.db.exists("Unit", b.kebun):
		rencana.divisi_salah.append(f"{scp.name}: kebun {b.kebun} tidak terdaftar")
		return {}

	beda = {} if scp.kebun else {"kebun": b.kebun}

	# Divisi yang sudah milik kebunnya dibiarkan: bisa jadi hasil koreksi orang.
	if scp.divisi and frappe.db.get_value("Divisi", scp.divisi, "unit") == b.kebun:
		return beda

	if b.divisi and frappe.db.get_value("Divisi", b.divisi, "unit") == b.kebun:
		beda["divisi"] = b.divisi
	elif b.divisi:
		rencana.divisi_salah.append(f"{scp.name}: divisi {b.divisi} bukan milik {b.kebun}")

	return beda


def _cetak_ringkasan(rencana, simpan):
	kata = "diisi" if simpan else "akan diisi (uji coba, belum ditulis)"
	print(f"Isian payload Security Check Point: {len(rencana.ubah)} dokumen {kata}, {rencana.sama} sudah sama")

	for b in rencana.ubah:
		perubahan = ", ".join(
			f"{field} {b.lama.get(field) or '(kosong)'} -> {nilai}" for field, nilai in b.beda.items()
		)
		print(f"  {b.name}: {perubahan}")

	for judul, daftar in (
		("Tidak ditemukan di site ini", rencana.hilang),
		("Trans No berbeda, dilewati", rencana.trans_no_beda),
		("Kebun sudah terisi lain, kebun/divisi dibiarkan", rencana.kebun_lain),
		("Kebun/divisi payload tidak dipakai", rencana.divisi_salah),
	):
		if daftar:
			print(f"  {judul}: {len(daftar)}")
			for d in daftar:
				print(f"    {d}")
