# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Validasi kesiapan data sebelum Accounting Period ditutup.

Closing baru boleh jalan kalau tidak ada lagi pekerjaan yang menggantung di
periode itu. Ada dua hal yang diperiksa:

1. BKM yang isinya sudah ada tapi dokumennya masih draft. BKM kosong sengaja
   dibiarkan lewat -- yang menahan closing cuma yang sudah ada baris kerjanya.
2. Upah dan premi yang sudah lahir dari BKM (dan sumber payroll lain) tapi
   belum ikut slip gaji, terbaca dari Employee Payment Log yang belum is_paid.

Keduanya menahan closing karena seluruh costing -- Bengkel, Mill, Panen,
Perawatan -- dibangun dari dokumen-dokumen ini saat Accounting Period disubmit.
Kalau ada yang tertinggal, costing dan buku besarnya ikut kurang.

Pemeriksaan ketiga -- transaksi berjurnal yang masih draft, dijaring dari
doctype yang pernah menghasilkan GL Entry -- dilepas atas permintaan user
(2 Sep 2026). Jaringnya terlalu lebar: dokumen draft apa pun yang doctype-nya
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
