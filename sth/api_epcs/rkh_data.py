# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""API untuk membuat atau memperbarui Rencana Kerja Harian dari sistem luar (EPCS).

Satu kiriman EPCS = satu dokumen Rencana Kerja Harian. Kegiatan, blok, dan luas
pekerjaannya datang sebagai daftar dan disimpan di tabel Detail RKH Kegiatan;
gudang, penerima material, dan kemandoran berlaku untuk seluruh dokumen.

`trans_no` adalah patokannya. Kiriman dengan trans_no yang sudah pernah masuk
memperbarui dokumen yang sama, bukan melahirkan dokumen baru — jadi pengirim boleh
mengulang request tanpa takut dobel.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate
from frappe.utils.synchronization import filelock

from sth.custom.api import ITEM_API_MAP, KEGIATAN_API_MAP

# Nama field EPCS yang boleh dipakai selain nama field ERP-nya. Sistem luar
# menyebut hal yang sama dengan istilahnya sendiri, dan payload-nya tidak bisa
# diubah dari sini, jadi keduanya diterima apa adanya.
ALIAS_DOKUMEN = {
	"no_trans": "trans_no",
	"no_dokumen": "trans_no",
	"doc_no": "trans_no",
	"created_date": "tanggal_pembuatan",
	"tanggal_pembuatan_rkh": "tanggal_pembuatan",
	"used_date": "posting_date",
	"tanggal_penggunaan": "posting_date",
	"tanggal_penggunaan_rkh": "posting_date",
	"estate_code": "unit",
	"kode_estate": "unit",
	"divisi_code": "divisi",
	"kode_divisi": "divisi",
	"kemandoran": "gang_code",
	"kode_kemandoran": "gang_code",
	"central_warehouse": "gudang_central",
	"virtual_warehouse": "gudang_virtual",
	"nik_penerima": "nik_penerima_material",
	"penerima_material": "nik_penerima_material",
	"kegiatan": "kegiatan_detail",
	"rincian_kegiatan": "kegiatan_detail",
	"detail_kegiatan": "kegiatan_detail",
	"materials": "material",
	"rincian_material": "material",
	"detail_material": "material",
}

ALIAS_KEGIATAN = {
	"kegiatan_code": "kegiatan",
	"kode_kegiatan": "kegiatan",
	"nama_kegiatan": "kegiatan",
	"blok_code": "blok",
	"kode_blok": "blok",
	"luas": "target_volume",
	"luas_pekerjaan": "target_volume",
	"tk_laki_laki": "jumlah_tk_laki_laki",
	"tenaga_kerja_laki_laki": "jumlah_tk_laki_laki",
	"jumlah_tenaga_kerja_laki_laki": "jumlah_tk_laki_laki",
	"tk_perempuan": "jumlah_tk_perempuan",
	"tenaga_kerja_perempuan": "jumlah_tk_perempuan",
	"jumlah_tenaga_kerja_perempuan": "jumlah_tk_perempuan",
}

ALIAS_MATERIAL = {
	"item_code": "item",
	"kode_material": "item",
	"material_code": "item",
	"jumlah_material": "dosis",
	"jumlah": "dosis",
	"qty": "dosis",
	"satuan": "uom",
}

# Kolom yang ikut menentukan apakah sebuah kiriman benar-benar mengubah dokumen.
# Turunan seperti kategori, tipe kegiatan, tarif, dan amount sengaja tidak ikut:
# semuanya dihitung ulang tiap kali dokumen disimpan.
FIELD_SIDIK_JARI = (
	"posting_date", "tanggal_pembuatan", "unit", "divisi", "gang_code",
	"mandor", "mandor1", "kerani", "gudang_central", "gudang_virtual",
	"nik_penerima_material",
)

FIELD_SIDIK_JARI_KEGIATAN = (
	"kegiatan", "blok", "batch", "target_volume",
	"jumlah_tk_laki_laki", "jumlah_tk_perempuan",
)

FIELD_SIDIK_JARI_MATERIAL = ("item", "dosis", "uom")

# Jabatan yang dianggap memegang peran mandor dan kerani di sebuah kemandoran.
#
# Dicocokkan ke `designation_name`, bukan ke field `designation` karyawan: di ERP
# ini nama dokumen Designation berupa kode (MD05, KR04, NS06) sementara teks
# jabatannya — "MANDOR PERAWATAN", "KERANI DIVISI" — ada di designation_name.
#
# Sengaja tidak memakai awalan kodenya. KR09 misalnya bernama "KEPALA GUDANG",
# bukan kerani; yang dicocokkan teksnya membuatnya tidak ikut terjaring.
POLA_JABATAN = {
	"mandor": "%MANDOR%",
	"kerani": "%KERANI%",
}


def _as_list(nilai):
	"""Daftar baris dari payload, entah sudah list atau masih JSON string."""
	if not nilai:
		return []

	if isinstance(nilai, str):
		nilai = json.loads(nilai)

	if isinstance(nilai, dict):
		return [nilai]

	return list(nilai)


def _terjemahkan(baris, alias):
	"""Salin satu dict dengan nama field EPCS diganti nama field ERP.

	Nama ERP yang sudah benar menang atas aliasnya: pengirim yang mengirim keduanya
	sekaligus jelas bermaksud memakai yang eksplisit.
	"""
	hasil = {}

	for key, value in (baris or {}).items():
		if key in alias:
			hasil[alias[key]] = value

	for key, value in (baris or {}).items():
		if key not in alias:
			hasil[key] = value

	return hasil


def _nama_lock(trans_no):
	return "rkh-trans-no-" + re.sub(r"[^A-Za-z0-9]+", "-", trans_no)[:64]


def _cari_unit(kode):
	"""Nama dokumen Unit untuk kode estate kiriman.

	Nama Unit di ERP berformat "{unit} - {company}", sedangkan EPCS mengirim kode
	pendeknya saja, jadi dicoba dua-duanya.
	"""
	kode = cstr(kode).strip()
	if not kode:
		return None

	if frappe.db.exists("Unit", kode):
		return kode

	return frappe.db.get_value("Unit", {"unit": kode}, "name")


def _cari_petugas(gang_code, peran):
	"""NIK karyawan di kemandoran ini yang jabatannya mandor / kerani.

	EPCS cuma mengirim kode kemandoran, sedangkan RKH mewajibkan mandor dan kerani,
	dan master Kemandoran sendiri tidak menyimpan siapa orangnya. Satu-satunya
	jalan yang ada: karyawan yang field kemandoran-nya menunjuk kemandoran itu,
	disaring lewat nama jabatannya.

	Kalau kandidatnya lebih dari satu diambil yang NIK-nya paling kecil, supaya
	kiriman berulang untuk kemandoran yang sama selalu jatuh ke orang yang sama.
	"""
	if not gang_code:
		return None

	baris = frappe.db.sql(
		"""
		SELECT e.name
		FROM `tabEmployee` e
		INNER JOIN `tabDesignation` d ON d.name = e.designation
		WHERE e.kemandoran = %(gang_code)s
			AND e.status = 'Active'
			AND UPPER(COALESCE(d.designation_name, '')) LIKE %(pola)s
		ORDER BY e.name
		LIMIT 1
		""",
		{"gang_code": gang_code, "pola": POLA_JABATAN[peran]},
	)

	return baris[0][0] if baris else None


def _sidik_jari(doc):
	"""Ringkasan isi dokumen yang benar-benar berasal dari kiriman.

	Dipakai untuk membedakan kiriman ulang — yang harus berakhir tanpa mengubah
	apa-apa — dari perubahan sungguhan.
	"""
	return (
		tuple(cstr(doc.get(f)) for f in FIELD_SIDIK_JARI),
		tuple(
			tuple(cstr(r.get(f)) for f in FIELD_SIDIK_JARI_KEGIATAN)
			for r in doc.get("kegiatan_detail") or []
		),
		tuple(
			tuple(cstr(r.get(f)) for f in FIELD_SIDIK_JARI_MATERIAL)
			for r in doc.get("material") or []
		),
	)


def _isi_dokumen(doc, kiriman):
	"""Tuangkan kiriman EPCS ke dokumen RKH, termasuk kedua tabelnya.

	Field yang tidak ikut di payload dibiarkan apa adanya, bukan dikosongkan —
	kiriman perbaikan yang cuma membawa sebagian field tidak boleh menghapus sisanya,
	dan posting_date yang hilang akan membuat dokumennya ditolak sebagai field wajib.

	Tabelnya lain: kalau dikirim, diisi ulang dari nol. Kiriman EPCS selalu membawa
	rencana harian itu secara utuh, jadi baris yang tidak ada lagi di kiriman memang
	sudah dihapus dari rencananya.
	"""
	if "unit" in kiriman:
		unit = _cari_unit(kiriman.get("unit"))
		if kiriman.get("unit") and not unit:
			frappe.throw(
				_("Kode Estate {0} tidak ditemukan sebagai Unit.").format(frappe.bold(kiriman.get("unit"))),
				title=_("Estate Tidak Dikenali")
			)

		doc.unit = unit
		if unit:
			doc.company = kiriman.get("company") or frappe.db.get_value("Unit", unit, "company")

	for fieldname in ("divisi", "gang_code", "gudang_central", "gudang_virtual",
			"nik_penerima_material", "mandor", "mandor1", "kerani", "company"):
		if fieldname in kiriman:
			doc.set(fieldname, kiriman.get(fieldname))

	for fieldname in ("posting_date", "tanggal_pembuatan"):
		if kiriman.get(fieldname):
			doc.set(fieldname, getdate(kiriman.get(fieldname)))

	# EPCS tidak mengirim mandor maupun kerani, sementara RKH mewajibkan keduanya.
	# Dicari dari kemandorannya, dan hanya kalau belum ada isinya — nilai yang sudah
	# ditetapkan sebelumnya, dari kiriman atau dari form, tidak ditimpa tebakan ini.
	for peran in ("mandor", "kerani"):
		if not doc.get(peran):
			doc.set(peran, _cari_petugas(doc.gang_code, peran))

	if "kegiatan_detail" in kiriman:
		doc.set("kegiatan_detail", [])
		for baris in _as_list(kiriman.get("kegiatan_detail")):
			baris = _terjemahkan(baris, ALIAS_KEGIATAN)
			kegiatan = cstr(baris.get("kegiatan")).strip()

			doc.append("kegiatan_detail", {
				# kode induk yang dikirim sistem luar diterjemahkan ke kode anaknya,
				# sama seperti yang dilakukan BKM lewat fix_kegiatan_from_api
				"kegiatan": KEGIATAN_API_MAP.get(kegiatan, kegiatan),
				"blok": baris.get("blok"),
				"batch": baris.get("batch"),
				"target_volume": flt(baris.get("target_volume")),
				"jumlah_tk_laki_laki": cint(baris.get("jumlah_tk_laki_laki")),
				"jumlah_tk_perempuan": cint(baris.get("jumlah_tk_perempuan")),
			})

	if "material" in kiriman:
		doc.set("material", [])
		for baris in _as_list(kiriman.get("material")):
			baris = _terjemahkan(baris, ALIAS_MATERIAL)
			item = cstr(baris.get("item")).strip()

			doc.append("material", {
				"item": ITEM_API_MAP.get(item, item),
				"dosis": flt(baris.get("dosis")),
				"uom": baris.get("uom"),
				"rate": flt(baris.get("rate")),
			})


def _validasi_petugas(doc):
	"""Pesan yang menyebut kemandorannya, bukan sekadar 'field wajib diisi'.

	Tanpa ini kiriman gagal dengan pesan bawaan Frappe yang menyebut nama field,
	sementara yang sebenarnya kurang adalah data karyawan di master.
	"""
	for peran in ("mandor", "kerani"):
		if doc.get(peran):
			continue

		frappe.throw(
			_("{0} untuk Kemandoran {1} tidak ketemu. Pastikan ada karyawan aktif "
			  "dengan Kode Kemandoran itu dan jabatan yang memuat kata {2}, atau "
			  "kirim NIK-nya lewat field {3}.").format(
				_(peran.title()), frappe.bold(doc.gang_code or "-"),
				frappe.bold(peran.upper()), frappe.bold(peran)
			),
			title=_("Petugas Kemandoran Tidak Ditemukan")
		)


def _hasil(doc, status, message=None):
	"""Balasan endpoint. Nomor RKH selalu ikut, apa pun yang terjadi dengan kirimannya.

	Pengirim tidak punya cara lain mengetahui dokumen mana yang mewakili trans_no-nya;
	tanpa nomor itu, kiriman yang ditolak cuma terlihat sebagai request gagal dan
	diulang terus tanpa ada yang berubah di sini.
	"""
	hasil = {
		"name": doc.name,
		"trans_no": doc.trans_no,
		"docstatus": doc.docstatus,
		"status": status,
		"grand_total": doc.grand_total,
	}

	if message:
		hasil["message"] = message

	return hasil


def _buat(kiriman, trans_no, submit):
	doc = frappe.new_doc("Rencana Kerja Harian")
	doc.trans_no = trans_no
	_isi_dokumen(doc, kiriman)
	_validasi_petugas(doc)

	# ditahan di draft dulu supaya kiriman berikutnya masih bisa memperbaikinya;
	# submit di bawah dijalankan sendiri kalau pengirim memang sudah final
	doc.flags.lewati_submit_otomatis = True
	doc.insert()

	if submit:
		doc.submit()

	return _hasil(doc, "created")


def _perbarui(nama, kiriman, submit):
	doc = frappe.get_doc("Rencana Kerja Harian", nama)

	sebelum = _sidik_jari(doc)
	_isi_dokumen(doc, kiriman)
	berubah = _sidik_jari(doc) != sebelum

	if not berubah:
		# kiriman ulang — lazim terjadi waktu jaringan pengirim putus di tengah
		# request yang sebenarnya sudah berhasil
		doc.reload()

		if submit and doc.docstatus == 0:
			doc.submit()

		return _hasil(doc, "unchanged")

	if doc.docstatus == 1:
		# Dokumennya sudah disubmit, jadi perubahannya tidak bisa masuk. Dibalas
		# dengan nomor dokumennya dan status "submitted", bukan dilempar sebagai
		# error: pengirim tidak bisa membedakan error karena data ditolak dari error
		# karena jaringan, jadi kirimannya diulang terus. Status ini membuat
		# pengulangan itu berhenti sekaligus menyebutkan alasannya.
		doc.reload()

		return _hasil(doc, "submitted", _(
			"Rencana Kerja Harian {0} untuk Trans No {1} sudah disubmit, isinya tidak "
			"bisa diubah lagi lewat API. Batalkan dulu dokumennya kalau rencananya "
			"memang berubah."
		).format(doc.name, doc.trans_no))

	_validasi_petugas(doc)
	doc.save()

	if submit:
		doc.submit()

	return _hasil(doc, "updated")


@frappe.whitelist()
def create_or_update(**kwargs):
	"""Buat Rencana Kerja Harian baru, atau perbarui yang trans_no-nya sudah ada.

	Field dokumen (nama EPCS di kurung):

	    trans_no                 (No Trans / No Dokumen) — wajib, jadi patokan
	    tanggal_pembuatan        (Tanggal Pembuatan RKH)
	    posting_date             (Tanggal Penggunaan RKH)
	    unit                     (Kode Estate)
	    divisi                   (Kode Divisi)
	    gang_code                (Kode Kemandoran)
	    gudang_central           (Gudang Central)
	    gudang_virtual           (Gudang Virtual)
	    nik_penerima_material    (NIK Penerima Material)
	    kegiatan_detail          daftar baris kegiatan
	    material                 daftar baris material
	    submit                   1 (bawaan) untuk langsung disubmit, 0 untuk draft

	Baris kegiatan: kegiatan (Kode/Nama Kegiatan), blok (Kode blok), target_volume
	(Luas Pekerjaan), jumlah_tk_laki_laki, jumlah_tk_perempuan. Kategori kegiatan
	tidak perlu dikirim — diambil dari master Kegiatan.

	Baris material: item (Kode Material), dosis (Jumlah Material), uom (Satuan).
	Kategori material diambil dari master Item, tarifnya dari Rencana Kerja Bulanan
	Perawatan yang menaungi kegiatannya.

	mandor dan kerani wajib ada di RKH tapi tidak dikirim EPCS; keduanya dicari dari
	karyawan aktif di kemandoran yang sama. Boleh juga dikirim langsung sebagai NIK
	lewat field mandor / kerani / mandor1.

	Balasannya selalu memuat nomor dokumennya, lewat `name`, dengan `status`:

	    created    trans_no belum pernah masuk, dokumennya baru dibuat
	    updated    dokumen lamanya masih draft dan isinya diperbarui
	    unchanged  kiriman ulang, isinya sama persis, tidak ada yang diubah
	    submitted  dokumennya sudah disubmit, jadi perubahannya tidak bisa masuk;
	               alasannya ada di `message`
	"""
	kiriman = _terjemahkan(kwargs, ALIAS_DOKUMEN)

	trans_no = cstr(kiriman.get("trans_no")).strip()
	if not trans_no:
		frappe.throw(_("Parameter trans_no wajib diisi."), title=_("Trans No Kosong"))

	submit = cint(kiriman.get("submit", 1))

	# Dua kiriman dengan trans_no yang sama bisa masuk barengan. Tanpa lock keduanya
	# sama-sama tidak menemukan dokumen lama lalu membuat dokumen sendiri-sendiri —
	# persis masalah yang dulu terjadi di Security Check Point.
	with filelock(_nama_lock(trans_no), timeout=60):
		nama = frappe.db.get_value(
			"Rencana Kerja Harian",
			{"trans_no": trans_no, "docstatus": ("<", 2)},
			"name",
			order_by="creation",
		)

		if nama:
			return _perbarui(nama, kiriman, submit)

		return _buat(kiriman, trans_no, submit)
