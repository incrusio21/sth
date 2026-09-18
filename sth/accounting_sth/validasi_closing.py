# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Validasi kesiapan data sebelum Accounting Period ditutup.

Closing baru boleh jalan kalau tidak ada lagi pekerjaan yang menggantung di
periode itu. Ada tiga hal yang diperiksa:

1. Unit kebun se-company yang periodenya belum ditutup, kalau yang sedang
   ditutup unit mill. Kebun dulu, baru mill.
2. BKM yang isinya sudah ada tapi dokumennya masih draft. BKM kosong sengaja
   dibiarkan lewat -- yang menahan closing cuma yang sudah ada baris kerjanya.
3. Upah dan premi yang sudah lahir dari BKM (dan sumber payroll lain) tapi
   belum ikut slip gaji, terbaca dari Employee Payment Log yang belum is_paid.

Dua yang terakhir menahan closing karena seluruh costing -- Bengkel, Mill,
Panen, Perawatan -- dibangun dari dokumen-dokumen ini saat Accounting Period
disubmit. Kalau ada yang tertinggal, costing dan buku besarnya ikut kurang.

Urutan kebun-sebelum-mill dijaga dua arah. Arah tutupnya di pemeriksaan
pertama, arah bukanya di validasi_sebelum_batal: selama periode mill masih
tertutup, periode kebun di rentang yang sama tidak boleh dibatalkan.

Pernah ada pemeriksaan keempat -- transaksi berjurnal yang masih draft,
dijaring dari doctype yang pernah menghasilkan GL Entry -- dan dilepas atas
permintaan user (2 Sep 2026). Jaringnya terlalu lebar: dokumen draft apa pun yang doctype-nya
pernah menjurnal ikut menahan closing, padahal banyak di antaranya tidak
memengaruhi costing periode itu.
"""

import frappe
from frappe import _

# BKM yang harus sudah selesai sebelum periodenya ditutup. Nama tabel isinya
# tidak didaftarkan: yang dipakai semua field bertipe Table milik doctype-nya,
# supaya tidak basi kalau ada tabel baru atau fieldname-nya berubah.
BKM_DOCTYPES = (
	"Buku Kerja Mandor Panen",
	"Buku Kerja Mandor Perawatan",
	"Buku Kerja Mandor Traksi",
	"Buku Kerja Mandor Bengkel",
)

# Banyaknya baris yang ditampilkan per bagian. Sisanya cukup dihitung supaya
# pesan errornya tidak jadi halaman sendiri.
BATAS_BARIS = 50


def tutup_sementara(doc):
	"""Periode ini ditutup sementara, cuma untuk mengunci transaksi saat memeriksa.

	Pemeriksaan kesiapan closing dilewati: yang dicari justru dokumen yang masih
	menggantung, jadi menahan penguncian karena ada yang menggantung membuat
	fiturnya tidak ada gunanya. Sisa jalannya submit tetap seperti biasa - BKM
	tetap di-posting dan costing tetap dibuat.
	"""
	return bool(doc.get("tutup_sementara"))


def validasi_sebelum_closing(doc, method=None):
	"""Hook before_submit Accounting Period."""
	if tutup_sementara(doc):
		return

	bagian = []

	bagian.extend(cek_kebun_belum_closing(doc))
	bagian.extend(cek_bkm_draft(doc))
	bagian.extend(cek_upah_belum_masuk_gaji(doc))

	if not bagian:
		return

	frappe.throw(
		title=_("Closing Periode Tidak Dapat Dilanjutkan"),
		msg=_("""
			<p>Closing periode <b>{periode}</b> tidak dapat dilanjutkan karena:</p>
			{isi}
			<p style="margin-top:12px;">Silakan selesaikan item-item di atas sebelum melakukan closing.</p>
		""").format(periode=frappe.utils.escape_html(doc.name), isi="".join(bagian))
	)


def cek_kebun_belum_closing(doc):
	"""Unit kebun se-company yang periodenya belum ditutup, waktu mill mau tutup.

	Harga pokok TBS yang dipakai mill baru lahir waktu periode kebun ditutup: di
	situ BKM Panen dan Perawatan pindah ke Posted beserta GL Entry-nya, dan di
	situ juga Costing Panen serta Costing Perawatan dibuat. Mill yang ditutup
	lebih dulu karena itu berdiri di atas buku kebun yang belum lengkap, dan
	angkanya tidak ikut berubah waktu kebun menyusul ditutup.

	Yang dicari unit dengan centang Plantation tanpa centang Mill di company yang
	sama; unit HO/RO dan unit mill sendiri tidak ikut. Periodenya harus persis
	rentang tanggal yang sama -- permintaan user -- jadi periode kebun yang
	tanggalnya dipotong beda tidak dianggap memenuhi, dan unit kebun yang
	periodenya belum dibuat sama sekali ikut menahan.

	Ditutup berarti docstatus 1 dan workflow_state "Submitted", sama dengan yang
	dipakai penguncian dokumen di validate_accounting_period_on_doc_save. Periode
	yang disubmit lewat kode tanpa melewati workflow memang belum menjalankan
	posting BKM maupun costing, jadi tepat kalau di sini pun belum terhitung
	tutup.
	"""
	if not (doc.company and doc.unit):
		return []

	if not frappe.db.get_value("Unit", doc.unit, "mill"):
		return []

	kebun = frappe.get_all(
		"Unit",
		filters={"company": doc.company, "plantation": 1, "mill": 0, "ho": 0},
		pluck="name",
		order_by="name asc",
	)

	if not kebun:
		return []

	periode = {}
	for p in frappe.get_all(
		"Accounting Period",
		filters={
			"company": doc.company,
			"unit": ["in", kebun],
			"start_date": doc.start_date,
			"end_date": doc.end_date,
		},
		fields=["name", "unit", "docstatus", "workflow_state"],
		order_by="name asc",
	):
		# kalau satu unit sempat punya periode batal di rentang yang sama, yang
		# sudah tutup yang menang -- jangan sampai dilaporkan belum tutup
		lama = periode.get(p.unit)
		if lama and sudah_tutup(lama):
			continue

		periode[p.unit] = p

	temuan = []
	beda_rentang = periode_beda_rentang(doc, [u for u in kebun if u not in periode])

	for unit in kebun:
		p = periode.get(unit)

		if p and sudah_tutup(p):
			continue

		if not p:
			lain = beda_rentang.get(unit)
			if lain:
				temuan.append((unit, lain.name, _("Rentang tanggal berbeda: {0} s/d {1}").format(
					frappe.format(lain.start_date, {"fieldtype": "Date"}),
					frappe.format(lain.end_date, {"fieldtype": "Date"}),
				)))
			else:
				temuan.append((unit, "-", _("Belum dibuat")))
		elif p.docstatus == 0:
			temuan.append((unit, p.name, _("Draft")))
		elif p.docstatus == 2:
			temuan.append((unit, p.name, _("Dibatalkan")))
		else:
			temuan.append((unit, p.name, p.workflow_state or _("Belum Submitted")))

	if not temuan:
		return []

	return [bagian_tabel(
		_("Unit <b>kebun</b> berikut periodenya belum ditutup. Closing kebun dulu, baru mill:"),
		[_("Unit"), _("Accounting Period"), _("Status")],
		temuan,
	)]


def sudah_tutup(periode):
	"""Accounting Period yang benar-benar sudah ditutup."""
	return periode.docstatus == 1 and periode.workflow_state == "Submitted"


def periode_beda_rentang(doc, units):
	"""Periode unit kebun yang tanggalnya bersinggungan tapi tidak persis sama.

	Cuma untuk pesannya. Tanpa ini unit yang periodenya sudah ada dan sudah
	ditutup - tapi rentangnya dipotong beda - dilaporkan sebagai "Belum dibuat",
	dan orang akan mencari dokumen yang sebenarnya ada di depan matanya.
	"""
	if not units:
		return {}

	hasil = {}
	for p in frappe.get_all(
		"Accounting Period",
		filters={
			"company": doc.company,
			"unit": ["in", units],
			"docstatus": ["<", 2],
			"start_date": ["<=", doc.end_date],
			"end_date": [">=", doc.start_date],
		},
		fields=["name", "unit", "start_date", "end_date"],
		order_by="start_date asc",
	):
		hasil.setdefault(p.unit, p)

	return hasil


def validasi_sebelum_batal(doc, method=None):
	"""Hook before_cancel Accounting Period.

	Kebalikan arah dari cek_kebun_belum_closing. Membatalkan periode kebun
	melepas BKM Panen dan Perawatan dari state Posted berikut GL Entry-nya
	(lihat unpost_bkm_on_cancel), sedangkan Costing Mill dan buku besar mill yang
	sudah ditutup tetap berdiri di atas angka lama. Jadi kalau mill-nya belum
	dibuka, kebunnya belum boleh dibatalkan.

	Tidak dilewati untuk periode yang ditutup sementara: penutupan sementara
	cuma melewati pemeriksaan kesiapan, BKM-nya tetap diposting dan costing-nya
	tetap dibuat, jadi pembatalannya sama berbahayanya.
	"""
	bagian = cek_mill_masih_tertutup(doc)

	if not bagian:
		return

	frappe.throw(
		title=_("Pembatalan Periode Tidak Dapat Dilanjutkan"),
		msg=_("""
			<p>Periode <b>{periode}</b> tidak dapat dibatalkan karena:</p>
			{isi}
			<p style="margin-top:12px;">Batalkan closing mill terlebih dahulu, baru periode kebun ini.</p>
		""").format(periode=frappe.utils.escape_html(doc.name), isi="".join(bagian))
	)


def cek_mill_masih_tertutup(doc):
	"""Unit mill se-company yang periodenya masih tertutup di rentang yang sama."""
	if not (doc.company and doc.unit):
		return []

	unit = frappe.db.get_value("Unit", doc.unit, ["plantation", "mill", "ho"], as_dict=True)

	# yang dijaga cuma pembatalan periode kebun; mill dan HO tidak menunggu siapa pun
	if not unit or unit.mill or unit.ho or not unit.plantation:
		return []

	mill = frappe.get_all(
		"Unit",
		filters={"company": doc.company, "mill": 1},
		pluck="name",
		order_by="name asc",
	)

	if not mill:
		return []

	temuan = [
		(p.unit, p.name, p.workflow_state)
		for p in frappe.get_all(
			"Accounting Period",
			filters={
				"company": doc.company,
				"unit": ["in", mill],
				"start_date": doc.start_date,
				"end_date": doc.end_date,
				"docstatus": 1,
			},
			fields=["name", "unit", "docstatus", "workflow_state"],
			order_by="name asc",
		)
		if sudah_tutup(p)
	]

	if not temuan:
		return []

	return [bagian_tabel(
		_("Periode unit <b>mill</b> berikut masih tertutup di rentang tanggal yang sama:"),
		[_("Unit"), _("Accounting Period"), _("Status")],
		temuan,
	)]


def filter_periode(doc, doctype, meta=None):
	"""Filter draft satu doctype di periode ini, mengikuti field yang dia punya.

	Dokumen yang unitnya masih kosong ikut terjaring supaya tidak lolos hanya
	karena unitnya lupa diisi. Doctype yang memang tidak punya field unit
	diperiksa se-company; ini sengaja lebih ketat daripada meloloskannya.
	"""
	meta = meta or frappe.get_meta(doctype)

	if not meta.has_field("posting_date"):
		return None, None

	filters = {
		"docstatus": 0,
		"posting_date": ["between", [doc.start_date, doc.end_date]],
	}

	if meta.has_field("company"):
		filters["company"] = doc.company

	or_filters = None
	if meta.has_field("unit"):
		or_filters = [
			[doctype, "unit", "=", doc.unit],
			[doctype, "unit", "is", "not set"],
		]

	return filters, or_filters


def cek_bkm_draft(doc):
	"""BKM draft yang sudah ada baris isinya."""
	temuan = []

	for doctype in BKM_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue

		meta = frappe.get_meta(doctype)
		filters, or_filters = filter_periode(doc, doctype, meta)
		if filters is None:
			continue

		draft = frappe.get_all(
			doctype,
			filters=filters,
			or_filters=or_filters,
			fields=["name", "posting_date"],
			order_by="posting_date asc, name asc",
		)

		if not draft:
			continue

		berisi = nama_yang_ada_isinya(doctype, meta, [d.name for d in draft])

		for d in draft:
			if d.name in berisi:
				temuan.append((doctype, d.name, d.posting_date))

	if not temuan:
		return []

	return [bagian_tabel(
		_("Masih ada <b>Buku Kerja Mandor</b> berisi hasil kerja yang belum disubmit:"),
		[_("Doctype"), _("Dokumen"), _("Tanggal")],
		temuan,
	)]


def nama_yang_ada_isinya(doctype, meta, names):
	"""Nama dokumen yang punya minimal satu baris di salah satu tabel anaknya."""
	berisi = set()

	for df in meta.get_table_fields():
		sisa = [name for name in names if name not in berisi]
		if not sisa:
			break

		berisi.update(frappe.get_all(
			df.options,
			filters={"parenttype": doctype, "parentfield": df.fieldname, "parent": ["in", sisa]},
			pluck="parent",
		))

	return berisi


def cek_upah_belum_masuk_gaji(doc):
	"""Employee Payment Log periode ini yang belum ditarik slip gaji.

	Log dibuat saat BKM disubmit dan baru ditandai is_paid waktu slip gaji yang
	memakainya ikut disubmit. Selama masih ada yang belum, berarti upah atau
	premi periode ini belum diproses sampai gaji.

	Log bernilai nol tidak ikut dihitung. Baris seperti itu memang dibiarkan ada
	oleh create_or_update_payment_log (removed_if_zero False) dan tetap ditarik
	slip gaji seperti yang lain, tapi tidak ada upah yang tertinggal karenanya,
	jadi tidak perlu menahan closing.
	"""
	kondisi_unit = ""
	if frappe.get_meta("Employee").has_field("unit"):
		kondisi_unit = "AND (emp.unit = %(unit)s OR IFNULL(emp.unit, '') = '')"

	rows = frappe.db.sql("""
		SELECT
			epl.voucher_type,
			epl.voucher_no,
			COUNT(DISTINCT epl.employee) AS jumlah_karyawan,
			SUM(epl.amount) AS total
		FROM `tabEmployee Payment Log` epl
		INNER JOIN `tabEmployee` emp ON emp.name = epl.employee
		WHERE epl.docstatus < 2
		  AND epl.company = %(company)s
		  AND epl.payroll_date BETWEEN %(start)s AND %(end)s
		  AND IFNULL(epl.is_paid, 0) = 0
		  AND IFNULL(epl.amount, 0) <> 0
		  {kondisi_unit}
		GROUP BY epl.voucher_type, epl.voucher_no
		ORDER BY epl.voucher_type, epl.voucher_no
	""".format(kondisi_unit=kondisi_unit), {
		"company": doc.company,
		"unit": doc.unit,
		"start": doc.start_date,
		"end": doc.end_date,
	}, as_dict=True)

	if not rows:
		return []

	return [bagian_tabel(
		_("Masih ada upah/premi yang belum masuk <b>slip gaji</b>:"),
		[_("Sumber"), _("Dokumen"), _("Karyawan"), _("Jumlah")],
		[
			(r.voucher_type, r.voucher_no, r.jumlah_karyawan, frappe.utils.fmt_money(r.total))
			for r in rows
		],
	)]


def bagian_tabel(judul, header, rows):
	"""Satu bagian pesan error: judul menyusul tabel isinya."""
	sisa = len(rows) - BATAS_BARIS

	baris = "".join(
		"<tr>{0}</tr>".format("".join(
			"<td>{0}</td>".format(frappe.utils.escape_html(str(nilai if nilai is not None else "")))
			for nilai in row
		))
		for row in rows[:BATAS_BARIS]
	)

	kolom = "".join("<th>{0}</th>".format(h) for h in header)

	keterangan = ""
	if sisa > 0:
		keterangan = "<p><i>{0}</i></p>".format(_("dan {0} dokumen lainnya").format(sisa))

	return """
		<p style="margin-top:12px;">{judul}</p>
		<table class="table table-bordered table-sm" style="margin-top:8px;">
			<thead><tr>{kolom}</tr></thead>
			<tbody>{baris}</tbody>
		</table>
		{keterangan}
	""".format(judul=judul, kolom=kolom, baris=baris, keterangan=keterangan)


@frappe.whitelist()
def cek_kesiapan_closing(accounting_period):
	"""Jalankan pemeriksaannya tanpa menutup periodenya.

	Dipakai untuk melihat lebih dulu apa saja yang masih menggantung::

		bench --site <site> execute sth.accounting_sth.validasi_closing.cek_kesiapan_closing --args "['AGUSTUS 2026 - TML']"
	"""
	doc = frappe.get_doc("Accounting Period", accounting_period)

	validasi_sebelum_closing(doc)

	frappe.msgprint(_("Periode {0} siap ditutup.").format(frappe.bold(doc.name)))
