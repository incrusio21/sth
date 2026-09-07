import frappe
from frappe.model.meta import get_field_precision

from sth.overrides.purchase_invoice import NON_VOUCHER_BASE_FIELDS, VAT_TOTAL_BASE_FIELDS

CHILD_DOCTYPE = "Non Voucher Match"
PARENT_DOCTYPE = "Purchase Invoice"

# conversion_rate 0 atau NULL diperlakukan sebagai 1: dokumen lama yang kursnya
# belum pernah diisi memang memakai mata uang perusahaan.
KURS = "COALESCE(NULLIF(pi.conversion_rate, 0), 1)"


def execute():
	"""Isi kolom base_* pajak Purchase Invoice untuk dokumen yang sudah ada.

	Kolomnya baru ditambahkan, jadi seluruh dokumen lama masih nol sementara
	laporan Equalisasi Pajak dan PPN Masukan sudah membacanya. Dua kelompok
	sekaligus: nominal tiap baris Non Voucher Match, dan Total PPN / Total PPh
	Lainnya di dokumennya sendiri untuk alur Voucher Match.

	Rumusnya sama persis dengan SthPurchaseInvoice.set_non_voucher_base_amounts
	dan set_base_vat_totals, cuma dikerjakan lewat UPDATE supaya tidak perlu
	memuat Purchase Invoice satu per satu.

	Kolom base_* bawaan ERPNext (base_total, base_discount_amount, dan
	base_amount di Purchase Invoice Item) tidak ikut disentuh: isinya sudah
	benar sejak dulu.

	Yang ditulis cuma kolom turunan yang read-only; angka transaksi dan GL tidak
	disentuh, jadi aman dijalankan berulang kali.
	"""
	isi_baris_non_voucher_match()
	isi_total_pajak_dokumen()


def isi_baris_non_voucher_match():
	assignments, belum_cocok = klausa(
		NON_VOUCHER_BASE_FIELDS, "nvm", presisi(CHILD_DOCTYPE, "base_dpp")
	)

	perlu_diisi = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabNon Voucher Match` nvm
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = nvm.parent
		WHERE nvm.parenttype = 'Purchase Invoice'
			AND ({0})
		""".format(belum_cocok)
	)[0][0]

	if not perlu_diisi:
		print("Semua baris Non Voucher Match sudah punya nilai mata uang perusahaan, dilewati.")
		return

	frappe.db.sql(
		"""
		UPDATE `tabNon Voucher Match` nvm
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = nvm.parent
		SET
			{0}
		WHERE nvm.parenttype = 'Purchase Invoice'
			AND ({1})
		""".format(assignments, belum_cocok)
	)

	print("{0} baris Non Voucher Match diisi nilai mata uang perusahaannya.".format(perlu_diisi))


def isi_total_pajak_dokumen():
	meta = meta_dengan_custom_field()
	assignments, belum_cocok = klausa(
		VAT_TOTAL_BASE_FIELDS, "pi", get_field_precision(meta.get_field("base_total_ppn"))
	)

	perlu_diisi = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabPurchase Invoice` pi
		WHERE {0}
		""".format(belum_cocok)
	)[0][0]

	if not perlu_diisi:
		print("Semua Purchase Invoice sudah punya total pajak mata uang perusahaan, dilewati.")
		return

	frappe.db.sql(
		"""
		UPDATE `tabPurchase Invoice` pi
		SET
			{0}
		WHERE {1}
		""".format(assignments, belum_cocok)
	)

	print("{0} Purchase Invoice diisi total pajak mata uang perusahaannya.".format(perlu_diisi))


def meta_dengan_custom_field():
	"""Meta Purchase Invoice yang dijamin sudah memuat custom field base_*.

	Patch post_model_sync dijalankan sebelum sync_customizations() milik migrate,
	jadi custom field yang baru ditambahkan di buying_sth/custom belum ada waktu
	patch ini kena giliran. Field DocType biasa tidak kena masalah ini karena
	sudah ikut tahap model sync, makanya baris Non Voucher Match aman.

	Disinkronkan duluan di sini; migrate tetap menyinkronkan lagi setelahnya dan
	itu tidak masalah karena sync_customizations idempoten.
	"""
	from frappe.modules.utils import sync_customizations

	meta = frappe.get_meta(PARENT_DOCTYPE)
	if meta.get_field("base_total_ppn"):
		return meta

	sync_customizations(app="sth")
	frappe.clear_cache(doctype=PARENT_DOCTYPE)

	# cached=False supaya tidak kena meta yang masih tersimpan di proses ini.
	meta = frappe.get_meta(PARENT_DOCTYPE, cached=False)
	if not meta.get_field("base_total_ppn"):
		frappe.throw(
			"Custom field base_total_ppn gagal disinkronkan ke {0}.".format(PARENT_DOCTYPE)
		)

	return meta


def presisi(doctype, fieldname):
	return get_field_precision(frappe.get_meta(doctype).get_field(fieldname))


def klausa(mapping, alias, precision):
	"""Rakit potongan SET dan penyaring "belum cocok" dari pemetaan kolomnya.

	Penyaringnya dipakai dua kali: sekali buat menghitung berapa yang perlu
	diisi, sekali lagi di UPDATE-nya supaya baris yang sudah benar tidak ikut
	ditulis ulang.
	"""
	hitung = "ROUND({0}.`{1}` * {2}, {3})"

	assignments = ",\n\t\t\t".join(
		"{0}.`{1}` = {2}".format(alias, base_field, hitung.format(alias, field, KURS, precision))
		for field, base_field in mapping.items()
	)
	belum_cocok = " OR ".join(
		"COALESCE({0}.`{1}`, 0) != {2}".format(
			alias, base_field, hitung.format(alias, field, KURS, precision)
		)
		for field, base_field in mapping.items()
	)
	return assignments, belum_cocok
