import csv

import frappe
from frappe.utils import cint, cstr, flt

# Total janjang dan brondolan yang dicatat pos, disalin dari log payload API
# Security Check Point 1-23 September 2026. Hanya kiriman yang memang membawa
# angkanya yang dimuat — 30 kiriman pos ASRM tanggal 22-23 September; kiriman pos
# TPRM mengirim null.
BERKAS = ("sth", "file", "total_janjang_security_check_point.csv")


def execute(names=None, simpan=True):
	"""Isi total_jjg dan total_brd Security Check Point dari payload API aslinya.

	Kedua field itu belum ada waktu kirimannya masuk, jadi angkanya ikut dikirim
	tapi dibuang frappe dan dokumennya tersimpan kosong. Angka pos inilah yang
	dipakai sebagai pembanding hitungan rincian SPB, dan yang diteruskan API
	Timbangan ke EPCS.

	Yang lain tidak disentuh — kebun dan divisi di payload yang sama diurus
	patch koreksi_unit_kebun_security_check_point.

	Dokumen dicari lewat nama dari respons API, lalu dipastikan trans_no-nya
	sama dengan kiriman; yang berbeda dilaporkan dan dilewati. Ditulis lewat
	db.set_value karena semuanya sudah submit. Yang nilainya sudah sama tidak
	disentuh, jadi aman diulang; yang sudah berisi angka lain ikut ditimpa dan
	angka lamanya dicetak.

	Tidak didaftarkan di patches.txt; jalankan sendiri:

	    bench --site <site> execute sth.patches.isi_total_janjang_security_check_point.execute

	Uji coba tanpa menulis apa pun:

	    from sth.patches.isi_total_janjang_security_check_point import execute
	    execute(simpan=False)
	"""
	rencana = _susun_rencana(_baca_berkas(names))

	if simpan:
		for b in rencana.ubah:
			frappe.db.set_value("Security Check Point", b.name, b.beda)

		frappe.db.commit()

	_cetak_ringkasan(rencana, simpan)


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
				total_jjg=cint(b.get("total_jjg")),
				total_brd=flt(b.get("total_brd")),
			))

	return baris


def _susun_rencana(baris):
	rencana = frappe._dict(ubah=[], sama=0, hilang=[], trans_no_beda=[])

	if not baris:
		return rencana

	lama = {
		d.name: d
		for d in frappe.get_all(
			"Security Check Point",
			filters={"name": ["in", [b.name for b in baris]]},
			fields=["name", "trans_no", "total_jjg", "total_brd"],
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
		if cint(scp.total_jjg) != b.total_jjg:
			beda["total_jjg"] = b.total_jjg
		if flt(scp.total_brd) != b.total_brd:
			beda["total_brd"] = b.total_brd

		if not beda:
			rencana.sama += 1
			continue

		rencana.ubah.append(frappe._dict(name=b.name, lama=scp, beda=beda))

	return rencana


def _cetak_ringkasan(rencana, simpan):
	kata = "diisi" if simpan else "akan diisi (uji coba, belum ditulis)"
	print(f"Total janjang/brondolan Security Check Point: {len(rencana.ubah)} dokumen {kata}, {rencana.sama} sudah sama")

	for b in rencana.ubah:
		perubahan = ", ".join(f"{field} {b.lama.get(field) or 0} -> {nilai}" for field, nilai in b.beda.items())
		print(f"  {b.name}: {perubahan}")

	for judul, daftar in (
		("Tidak ditemukan di site ini", rencana.hilang),
		("Trans No berbeda, dilewati", rencana.trans_no_beda),
	):
		if daftar:
			print(f"  {judul}: {len(daftar)}")
			for d in daftar:
				print(f"    {d}")
