import frappe
from frappe.utils import cint, flt

from erpnext.accounts.general_ledger import make_reverse_gl_entries

# Tiga doctype ini tidak lagi menjurnal saat submit: potongan dan BPJS dijurnal
# Payroll Entry lewat Additional Salary dan Employee Payment Log.
DOCTYPES = ("Employee Potongan", "BPJS TK", "BPJS KES")


def execute(terapkan=0, doctype=None, nama=None):
	"""Batalkan GL Entry yang masih hidup dari Employee Potongan dan BPJS TK/KES.

	Bawaannya cuma melaporkan. Yang mau dibatalkan dijalankan dengan terapkan=1:

	    bench --site <site> execute sth.patches.batalkan_gl_potongan_dan_bpjs.execute
	    bench --site <site> execute sth.patches.batalkan_gl_potongan_dan_bpjs.execute \
	        --kwargs "{'terapkan': 1, 'doctype': 'BPJS KES'}"

	GL-nya dibalik seperti waktu dokumennya di-cancel, dengan tanggal posting
	yang sama, lalu outstanding_amount dokumennya dinolkan. Dokumennya sendiri
	tetap Submitted.

	Dokumen yang sudah dibayar lewat Payment Entry atau Journal Entry tersubmit
	dilewati dan dilaporkan: pembayarannya mendebit hutang yang dikredit GL ini,
	jadi membalik GL-nya saja membuat hutang itu bersaldo debit. Periode yang
	sudah ditutup akan menolak - dokumennya dilaporkan gagal dan sisanya tetap
	jalan.

	Sengaja tidak didaftarkan di patches.txt: membalik jurnal bukan sesuatu yang
	boleh jalan sendiri tiap migrate.
	"""
	terapkan = cint(terapkan)
	dokumen = cari_voucher(doctype=doctype, nama=nama)

	if not dokumen:
		print("Tidak ada GL hidup dari {0}.".format(", ".join(DOCTYPES)))
		return

	dibayar = cari_pembayaran(dokumen)

	print("{0} dokumen ber-GL hidup, mode {1}\n".format(
		len(dokumen), "TERAPKAN" if terapkan else "LAPORAN SAJA"
	))

	dibatalkan, dilewati, gagal = [], [], []
	for d in dokumen:
		label = "{0} {1} ({2}, {3}, debit {4:,.2f})".format(
			d.voucher_type, d.voucher_no, d.company, d.posting_date, flt(d.debit)
		)

		if pembayaran := dibayar.get((d.voucher_type, d.voucher_no)):
			dilewati.append(label)
			print("LEWAT  {0} - sudah dibayar: {1}".format(label, ", ".join(sorted(pembayaran))))
			continue

		if not terapkan:
			print("AKAN   {0}".format(label))
			continue

		try:
			make_reverse_gl_entries(voucher_type=d.voucher_type, voucher_no=d.voucher_no)
			frappe.db.set_value(
				d.voucher_type, d.voucher_no, "outstanding_amount", 0, update_modified=False
			)
			frappe.db.commit()
			dibatalkan.append(label)
			print("BATAL  {0}".format(label))
		except Exception as e:
			frappe.db.rollback()
			gagal.append(label)
			print("GAGAL  {0} - {1}".format(label, frappe.utils.strip_html(str(e))))

	print("\nRingkasan: {0} dibatalkan, {1} dilewati karena sudah dibayar, {2} gagal{3}".format(
		len(dibatalkan), len(dilewati), len(gagal),
		"" if terapkan else ", {0} akan dibatalkan".format(len(dokumen) - len(dilewati)),
	))


def cari_voucher(doctype=None, nama=None):
	doctypes = (doctype,) if doctype else DOCTYPES
	kondisi = ""
	if nama:
		kondisi = "AND voucher_no = %(nama)s"

	return frappe.db.sql("""
		SELECT voucher_type, voucher_no, company,
			MIN(posting_date) AS posting_date, SUM(debit) AS debit
		FROM `tabGL Entry`
		WHERE is_cancelled = 0
		  AND voucher_type IN %(doctypes)s
		  {kondisi}
		GROUP BY voucher_type, voucher_no, company
		ORDER BY voucher_type, posting_date, voucher_no
	""".format(kondisi=kondisi), {"doctypes": doctypes, "nama": nama}, as_dict=True)


def cari_pembayaran(dokumen):
	"""Payment Entry dan Journal Entry tersubmit yang menaut tiap dokumen."""
	nama = tuple({d.voucher_no for d in dokumen})
	hasil = {}

	for dt, anak, kolom_tipe, kolom_nama in (
		("Payment Entry", "Payment Entry Reference", "reference_doctype", "reference_name"),
		("Journal Entry", "Journal Entry Account", "reference_type", "reference_name"),
	):
		for r in frappe.db.sql("""
			SELECT c.`{tipe}` AS voucher_type, c.`{nama}` AS voucher_no, p.name
			FROM `tab{anak}` c
			JOIN `tab{dt}` p ON p.name = c.parent
			WHERE p.docstatus = 1
			  AND c.`{tipe}` IN %(doctypes)s
			  AND c.`{nama}` IN %(nama)s
		""".format(anak=anak, dt=dt, tipe=kolom_tipe, nama=kolom_nama),
			{"doctypes": DOCTYPES, "nama": nama}, as_dict=True):
			hasil.setdefault((r.voucher_type, r.voucher_no), set()).add(r.name)

	return hasil
