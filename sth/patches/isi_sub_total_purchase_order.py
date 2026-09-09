import frappe
from frappe.model.meta import get_field_precision

DOCTYPE = "Purchase Order"
FIELDNAME = "sub_total"


def execute():
	"""Isi Sub Total Purchase Order untuk dokumen yang sudah ada.

	Field sub_total sudah lama ada di Purchase Order, tapi yang mengisinya baru
	ditambahkan belakangan dan cuma di sisi klien: calculate_sub_total() dipanggil
	dari validate() serta dari trigger qty dan rate di purchase_order.js. Artinya
	dokumen yang tidak pernah dibuka dan disimpan lagi setelah itu — praktisnya
	semua PO lama — sub_total-nya masih nol, sedangkan print format PO sudah
	mencetaknya sebagai baris "Sub Total".

	Rumusnya disamakan dengan yang di klien: jumlah amount seluruh baris item.
	Tiga tabel lain yang ikut dihitung calculate_sub_total (charges, pengeluaran
	barang, dan Non Voucher Match) tidak ada di Purchase Order — itu bawaan
	Purchase Invoice yang ikut tersalin waktu fungsinya dipindahkan — jadi di
	sini yang tersisa memang cuma total item.

	Diskon dokumen sengaja tidak dikurangkan: di print format PO diskon berdiri
	sebagai barisnya sendiri di bawah Sub Total, jadi sub_total memang angka
	sebelum diskon.

	sub_total kolom turunan yang read-only, jadi tidak ada angka transaksi
	maupun GL yang tersentuh. Baris yang nilainya sudah cocok dilewati, jadi
	aman dijalankan berulang kali.
	"""
	presisi = get_field_precision(meta_dengan_custom_field().get_field(FIELDNAME))
	total_item = "ROUND(COALESCE(it.total, 0), {0})".format(presisi)

	# LEFT JOIN, bukan INNER: PO tanpa satu pun baris item pun harus ikut
	# dinolkan kalau sub_total-nya terlanjur terisi.
	sumber = """
		FROM `tabPurchase Order` po
		LEFT JOIN (
			SELECT parent, SUM(amount) AS total
			FROM `tabPurchase Order Item`
			WHERE parenttype = 'Purchase Order'
			GROUP BY parent
		) it ON it.parent = po.name
		WHERE COALESCE(po.`{0}`, 0) != {1}
	""".format(FIELDNAME, total_item)

	perlu_diisi = frappe.db.sql("SELECT COUNT(*) {0}".format(sumber))[0][0]
	if not perlu_diisi:
		print("Semua Purchase Order sudah punya Sub Total yang cocok, dilewati.")
		return

	# Join dan penyaringnya ditulis ulang, bukan dipakai ulang dari `sumber`:
	# di sintaks UPDATE, SET duduk di antara JOIN dan WHERE, jadi potongannya
	# tidak bisa disisipkan utuh seperti di SELECT COUNT(*) barusan.
	frappe.db.sql(
		"""
		UPDATE `tabPurchase Order` po
		LEFT JOIN (
			SELECT parent, SUM(amount) AS total
			FROM `tabPurchase Order Item`
			WHERE parenttype = 'Purchase Order'
			GROUP BY parent
		) it ON it.parent = po.name
		SET po.`{0}` = {1}
		WHERE COALESCE(po.`{0}`, 0) != {1}
		""".format(FIELDNAME, total_item)
	)

	print("{0} Purchase Order diisi Sub Total-nya.".format(perlu_diisi))


def meta_dengan_custom_field():
	"""Meta Purchase Order yang dijamin sudah memuat custom field sub_total.

	Patch post_model_sync jalan sebelum sync_customizations() milik migrate, jadi
	di site yang custom field-nya belum pernah tersinkron, sub_total belum ada
	waktu patch ini kena giliran. Disinkronkan duluan di sini; migrate tetap
	menyinkronkan lagi setelahnya dan itu tidak masalah karena sync_customizations
	idempoten.
	"""
	from frappe.modules.utils import sync_customizations

	meta = frappe.get_meta(DOCTYPE)
	if meta.get_field(FIELDNAME):
		return meta

	sync_customizations(app="sth")
	frappe.clear_cache(doctype=DOCTYPE)

	# cached=False supaya tidak kena meta yang masih tersimpan di proses ini.
	meta = frappe.get_meta(DOCTYPE, cached=False)
	if not meta.get_field(FIELDNAME):
		frappe.throw("Custom field {0} gagal disinkronkan ke {1}.".format(FIELDNAME, DOCTYPE))

	return meta
