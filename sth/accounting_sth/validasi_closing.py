# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Validasi kesiapan data sebelum Accounting Period ditutup.

Closing baru boleh jalan kalau tidak ada lagi pekerjaan yang menggantung di
periode itu. Ada tiga hal yang diperiksa:

1. BKM yang isinya sudah ada tapi dokumennya masih draft. BKM kosong sengaja
   dibiarkan lewat -- yang menahan closing cuma yang sudah ada baris kerjanya.
2. Upah dan premi yang sudah lahir dari BKM (dan sumber payroll lain) tapi
   belum ikut slip gaji, terbaca dari Employee Payment Log yang belum is_paid.
3. Transaksi berjurnal yang masih draft, yaitu dokumen dari doctype yang pernah
   menghasilkan GL Entry.

Ketiganya menahan closing karena seluruh costing -- Bengkel, Mill, Panen,
Perawatan -- dibangun dari dokumen-dokumen ini saat Accounting Period disubmit.
Kalau ada yang tertinggal, costing dan buku besarnya ikut kurang.
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

# Doctype yang punya GL Entry tapi tidak ikut pemeriksaan draft umum.
#
# BKM diperiksa sendiri di cek_bkm_draft dengan syarat "ada isi kerjanya", jadi
# kalau ikut di sini BKM kosong pun ikut menahan closing. Salary Slip sudah
# dipegang check_unsubmitted_salary_slip yang pesannya lebih terarah.
DIKECUALIKAN_DARI_CEK_DRAFT = BKM_DOCTYPES + ("Salary Slip",)

# Doctype yang tanggal periodenya bukan posting_date. Nilainya None berarti
# dokumen itu tidak bisa dilingkupi periode, jadi dilewati.
FIELD_TANGGAL = {
	"Asset": "available_for_use_date",
	"Asset Repair": "completion_date",
	"Period Closing Voucher": "period_end_date",
	"Bank Clearance": None,
}

# Banyaknya baris yang ditampilkan per bagian. Sisanya cukup dihitung supaya
# pesan errornya tidak jadi halaman sendiri.
BATAS_BARIS = 50


def validasi_sebelum_closing(doc, method=None):
	"""Hook before_submit Accounting Period."""
	bagian = []

	bagian.extend(cek_bkm_draft(doc))
	bagian.extend(cek_upah_belum_masuk_gaji(doc))
	bagian.extend(cek_transaksi_berjurnal_draft(doc))

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


def filter_periode(doc, doctype, meta=None):
	"""Filter draft satu doctype di periode ini, mengikuti field yang dia punya.

	Dokumen yang unitnya masih kosong ikut terjaring supaya tidak lolos hanya
	karena unitnya lupa diisi. Doctype yang memang tidak punya field unit
	diperiksa se-company; ini sengaja lebih ketat daripada meloloskannya.
	"""
	meta = meta or frappe.get_meta(doctype)

	fieldname = FIELD_TANGGAL.get(doctype, "posting_date")
	if not fieldname or not meta.has_field(fieldname):
		return None, None

	filters = {
		"docstatus": 0,
		fieldname: ["between", [doc.start_date, doc.end_date]],
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


def cek_transaksi_berjurnal_draft(doc):
	"""Dokumen draft dari doctype yang punya jurnal."""
	temuan = []

	for doctype in doctype_berjurnal(doc):
		meta = frappe.get_meta(doctype)
		if not meta.is_submittable:
			continue

		filters, or_filters = filter_periode(doc, doctype, meta)
		if filters is None:
			continue

		fieldname = FIELD_TANGGAL.get(doctype, "posting_date")

		for d in frappe.get_all(
			doctype,
			filters=filters,
			or_filters=or_filters,
			fields=["name", "{0} as tanggal".format(fieldname)],
			order_by="{0} asc, name asc".format(fieldname),
		):
			temuan.append((doctype, d.name, d.tanggal))

	if not temuan:
		return []

	return [bagian_tabel(
		_("Masih ada transaksi berjurnal yang belum disubmit:"),
		[_("Doctype"), _("Dokumen"), _("Tanggal")],
		temuan,
	)]


def doctype_berjurnal(doc):
	"""Doctype yang pernah menghasilkan GL Entry, plus yang dikunci periode ini.

	Diambil dari isi buku besar, bukan daftar tetap, supaya doctype baru yang
	menjurnal ikut terjaring tanpa perlu didaftarkan lagi di sini. Closed
	Document ikut dibaca supaya dokumen inti akuntansi tetap terperiksa di site
	yang buku besarnya masih kosong.
	"""
	daftar = {
		row[0] for row in frappe.db.sql("SELECT DISTINCT voucher_type FROM `tabGL Entry`")
		if row[0]
	}

	daftar.update(d.document_type for d in (doc.get("closed_documents") or []) if d.document_type)
	daftar.difference_update(DIKECUALIKAN_DARI_CEK_DRAFT)

	return sorted(dt for dt in daftar if frappe.db.exists("DocType", dt))


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
