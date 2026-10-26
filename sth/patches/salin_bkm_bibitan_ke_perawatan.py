import frappe
from frappe.utils import cint


def execute(terapkan=0, nama=None):
	"""Buat BKM Perawatan untuk BKM Bibitan submitted yang belum punya salinan.

	BKM Bibitan yang disubmit sebelum penyalinan otomatis ada tidak pernah
	tersalin. Patch ini memanggil buat_bkm_perawatan yang sama dengan on_submit,
	jadi hasilnya persis seperti dokumen baru: nomor sama dengan BKM Bibitan-nya,
	lalu disubmit beserta Payment Log, Attendance, Stock Entry dan GL-nya.

	Default-nya uji coba: tiap dokumen dicoba lalu di-rollback, dan yang gagal
	dilaporkan dengan pesannya. Tulis sungguhan dengan terapkan=1. nama membatasi
	ke satu BKM Bibitan, untuk dicoba satu per satu dulu.

	Tiap dokumen punya savepoint sendiri dan langsung di-commit kalau berhasil,
	jadi satu dokumen yang gagal tidak membatalkan yang lain, dan patch aman
	diulang — yang sudah punya salinan dilewati.
	"""
	terapkan = cint(terapkan)
	isi_trans_no_salinan(terapkan)

	filters = {"docstatus": 1}
	if nama:
		filters["name"] = nama

	sudah_disalin = set(frappe.get_all(
		"Buku Kerja Mandor Perawatan",
		filters={"voucher_type": "Buku Kerja Mandor Bibitan", "docstatus": ["<", 2]},
		pluck="voucher_no",
	))

	daftar = [
		d for d in frappe.get_all(
			"Buku Kerja Mandor Bibitan", filters=filters, pluck="name", order_by="posting_date, creation"
		)
		if d not in sudah_disalin
	]

	berhasil, gagal = [], []

	for name in daftar:
		frappe.db.savepoint("salin_bkm_bibitan")
		try:
			frappe.get_doc("Buku Kerja Mandor Bibitan", name).buat_bkm_perawatan()
		except Exception as e:
			frappe.db.rollback(save_point="salin_bkm_bibitan")
			gagal.append((name, f"{type(e).__name__}: {frappe.utils.strip_html(str(e))}"))
			continue
		finally:
			frappe.clear_messages()

		if terapkan:
			frappe.db.commit()
		else:
			frappe.db.rollback(save_point="salin_bkm_bibitan")

		berhasil.append(name)

	print("{}: {} BKM Bibitan belum tersalin, {} {}, {} gagal".format(
		"DITERAPKAN" if terapkan else "UJI COBA (tidak ada yang disimpan)",
		len(daftar), len(berhasil), "disalin" if terapkan else "bisa disalin", len(gagal),
	))
	for name, pesan in gagal:
		print(f"  GAGAL {name}: {pesan}")

	if not terapkan:
		frappe.db.rollback()


def isi_trans_no_salinan(terapkan):
	"""Isi trans_no salinan yang dibuat sebelum trans_no ikut disalin.

	Ditulis lewat SQL langsung, sama untuk draft maupun submitted: trans_no
	cuma catatan asal kiriman dan tidak ikut hitungan apa pun.
	"""
	kosong = frappe.db.sql("""
		SELECT bkmp.name, bbt.trans_no
		FROM `tabBuku Kerja Mandor Perawatan` bkmp
		INNER JOIN `tabBuku Kerja Mandor Bibitan` bbt ON bbt.name = bkmp.voucher_no
		WHERE bkmp.voucher_type = 'Buku Kerja Mandor Bibitan'
			AND IFNULL(bkmp.trans_no, '') = ''
			AND IFNULL(bbt.trans_no, '') != ''
	""", as_dict=True)

	if terapkan:
		for d in kosong:
			frappe.db.set_value("Buku Kerja Mandor Perawatan", d.name, "trans_no", d.trans_no, update_modified=False)
		frappe.db.commit()

	print("trans_no salinan yang kosong: {} {}".format(len(kosong), "diisi" if terapkan else "akan diisi"))
