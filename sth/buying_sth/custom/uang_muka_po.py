# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Uang muka Purchase Order yang diperhitungkan di Purchase Invoice.

Pembayaran terhadap PO dibuat lewat `get_payment_entry_uang_muka` di
purchase_order.py: jurnalnya D: Uang Muka / K: Bank dengan `against_voucher`
Purchase Order.

Uang muka itu dipakai lewat tabel `advances` bawaan, tapi rekonsiliasinya tidak.
Jalur bawaan merekonsiliasi dengan cara menimpa baris Payment Entry Reference di
tempat: referensinya berpindah dari Purchase Order ke Purchase Invoice dan GL
Payment Entry-nya diposting ulang. Payment Entry harus tetap menempel pada PO
yang dibayar, jadi baris advance yang menunjuk PO dilewati di
`update_against_document_in_jv` dan pengurangan hutangnya dijurnal di invoice
sendiri:

    D: Hutang Invoice (credit_to)   K: Akun Uang Muka

Karena Payment Entry tidak pernah disentuh, `unallocated_amount`-nya tidak
pernah berkurang — penjaga bawaan yang mencegah satu uang muka terpakai dua kali
ikut hilang untuk baris-baris itu. Penggantinya `terpakai_di_invoice_lain` di
bawah: sisanya dihitung dari baris `Purchase Invoice Advance` milik invoice lain
yang masih submitted. Invoice yang dibatalkan otomatis melepas jatahnya karena
docstatus barisnya ikut jadi 2.

Advance selain uang muka PO — Journal Entry, atau Payment Entry yang tidak
menunjuk PO — tidak disentuh sama sekali dan tetap lewat jalur bawaan.

Uang muka yang tidak jadi dipakai ditarik balik lewat Payment Entry penerimaan
yang menunjuk PO yang sama, dibuatkan `get_payment_entry_pengembalian_uang_muka`
di purchase_order.py: jurnalnya D: Bank / K: Uang Muka, kebalikan persis dari
pembayarannya. Payment Entry pembayarannya tidak ikut dibatalkan, jadi sisanya
juga tidak bisa dibaca dari dokumen mana pun — dihitung di bagian bawah berkas
ini sebagai dibayar - dipakai invoice - dikembalikan.
"""

import frappe
from frappe import _
from frappe.utils import flt


def po_di_invoice(doc):
	"""Purchase Order yang disebut item-item invoice ini."""
	return sorted({item.purchase_order for item in doc.get("items") if item.get("purchase_order")})


def akun_uang_muka_pe(payment_entry, purchase_order, paid_to=None):
	"""Akun yang benar-benar terdebit saat PO itu dibayar.

	Dibaca dari GL Entry-nya, bukan dihitung ulang dari Procurement Settings,
	supaya invoice tetap mengkredit akun yang sama walau setting-nya berubah
	setelah pembayaran. paid_to dipakai kalau GL-nya tidak ketemu.
	"""
	akun = frappe.db.get_value(
		"GL Entry",
		{
			"voucher_type": "Payment Entry",
			"voucher_no": payment_entry,
			"against_voucher_type": "Purchase Order",
			"against_voucher": purchase_order,
			"debit": (">", 0),
			"is_cancelled": 0,
		},
		"account",
	)

	return akun or paid_to or frappe.db.get_value("Payment Entry", payment_entry, "paid_to")


def referensi_pe_ke_po(reference_rows):
	"""Baris Payment Entry Reference yang menunjuk Purchase Order, dipeta per nama."""
	if not reference_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select
			per.name,
			per.parent as payment_entry,
			per.reference_name as purchase_order,
			per.allocated_amount,
			per.docstatus
		from `tabPayment Entry Reference` per
		where per.name in %(rows)s
			and per.reference_doctype = 'Purchase Order'
		""",
		{"rows": list(reference_rows)},
		as_dict=True,
	)

	return {row.name: row for row in hasil}


def pasangan_uang_muka_po(doc):
	"""Baris `advances` yang uang mukanya milik PO, berpasangan dengan data PE-nya.

	Baris advance sendiri tidak menyimpan PO mana yang dibayar — yang tahu hanya
	baris Payment Entry Reference yang ditunjuk `reference_row`. Datanya ikut
	dikembalikan supaya pemanggilnya tidak perlu query ulang.
	"""
	kandidat = [
		d
		for d in doc.get("advances") or []
		if d.reference_type == "Payment Entry" and d.reference_row
	]
	if not kandidat:
		return []

	info = referensi_pe_ke_po([d.reference_row for d in kandidat])

	return [(d, info[d.reference_row]) for d in kandidat if d.reference_row in info]


def advance_uang_muka_po(doc):
	"""Baris `advances` yang tidak boleh direkonsiliasi ke Payment Entry-nya."""
	return [baris for baris, _ in pasangan_uang_muka_po(doc)]


def saring_advance_beda_akun(doc, entries):
	"""Buang Payment Entry yang uang mukanya tidak duduk di akun hutang invoice.

	Rekonsiliasi bawaan mengasumsikan uang muka dan tagihannya berada di akun
	party yang sama: yang dilakukannya hanya memindahkan referensi Payment Entry
	ke invoice, akunnya tidak ikut pindah. Uang muka PO dibayar ke akun Uang
	Muka, bukan ke credit_to, jadi asumsi itu tidak berlaku — sisa Payment Entry
	yang belum dialokasikan ke PO mana pun akan tampak melunasi invoice padahal
	uangnya masih menggantung di akun uang muka.

	Baris yang menunjuk PO tetap lolos: baris itu dijurnal sendiri di
	get_gl_entries() dan dilewati waktu rekonsiliasi, jadi beda akun justru
	memang yang diharapkan.
	"""
	menganggur = {
		d.get("reference_name")
		for d in entries
		if d.get("reference_type") == "Payment Entry" and not d.get("against_order")
	}
	if not menganggur:
		return entries

	# paid_to adalah akun party untuk payment_type Pay, yaitu satu-satunya tipe
	# yang bisa jadi advance di Purchase Invoice.
	akun = dict(
		frappe.db.sql(
			"""
			select name, paid_to
			from `tabPayment Entry`
			where name in %(pe)s
			""",
			{"pe": list(menganggur)},
		)
	)

	return [
		d
		for d in entries
		if d.get("reference_type") != "Payment Entry"
		or d.get("against_order")
		or akun.get(d.get("reference_name")) == doc.credit_to
	]


def terpakai_di_invoice_lain(reference_rows, kecuali=None):
	"""Berapa tiap baris uang muka sudah dipakai invoice submitted yang lain."""
	if not reference_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select pia.reference_row, sum(pia.allocated_amount) as dipakai
		from `tabPurchase Invoice Advance` pia
		where pia.parenttype = 'Purchase Invoice'
			and pia.docstatus = 1
			and pia.reference_type = 'Payment Entry'
			and pia.reference_row in %(rows)s
			and pia.parent != %(kecuali)s
		group by pia.reference_row
		""",
		{"rows": list(reference_rows), "kecuali": kecuali or ""},
		as_dict=True,
	)

	return {row.reference_row: flt(row.dipakai) for row in hasil}


def koreksi_advance_uang_muka_po(doc):
	"""Rapikan baris uang muka PO yang baru ditarik `set_advances()` bawaan.

	Bawaan mengisi advance_amount dari allocated_amount baris Payment Entry
	Reference — angka penuh, karena bawaan mengandalkan unallocated_amount
	Payment Entry yang di sini memang tidak pernah berkurang. Sisanya dipotong
	dengan yang sudah dipakai invoice lain dan yang sudah dikembalikan ke
	supplier, alokasinya dibatasi tagihan yang belum tertutup advance lain, dan
	baris yang sudah habis dibuang.
	"""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return

	uang_muka = {baris.reference_row: info for baris, info in pasangan}
	rincian = sisa_per_baris(uang_muka, kecuali=doc.name)

	sisa_tagihan = flt(doc.get("rounded_total") or doc.grand_total)
	for baris in doc.get("advances"):
		if baris.reference_row not in uang_muka:
			sisa_tagihan -= flt(baris.allocated_amount)

	tersisa = []
	for baris in doc.get("advances"):
		info = uang_muka.get(baris.reference_row)
		if info is None:
			tersisa.append(baris)
			continue

		sisa = flt(rincian[baris.reference_row]["sisa"])
		if sisa <= 0:
			continue

		baris.advance_amount = sisa
		baris.allocated_amount = max(min(flt(baris.allocated_amount), sisa, sisa_tagihan), 0)
		sisa_tagihan -= flt(baris.allocated_amount)
		tersisa.append(baris)

	doc.set("advances", tersisa)
	for urutan, baris in enumerate(doc.get("advances"), start=1):
		baris.idx = urutan


def validate_uang_muka_po(doc):
	"""Pastikan tiap baris uang muka PO masih sah dan tidak melebihi sisanya."""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return

	if doc.get("is_return"):
		frappe.throw(
			_("Uang muka Purchase Order tidak berlaku untuk Debit Note."),
			title=_("Uang Muka PO"),
		)

	baris_pe = [baris.reference_row for baris, _ in pasangan]
	if len(set(baris_pe)) != len(baris_pe):
		frappe.throw(
			_("Ada pembayaran uang muka yang tercantum lebih dari sekali di tabel Advances."),
			title=_("Uang Muka PO"),
		)

	rincian = sisa_per_baris(
		{baris.reference_row: info for baris, info in pasangan}, kecuali=doc.name
	)

	for baris, info in pasangan:
		if info.docstatus != 1:
			frappe.throw(
				_("Pembayaran uang muka di baris {0} sudah dibatalkan.").format(baris.idx),
				title=_("Uang Muka PO"),
			)

		rinci = rincian[baris.reference_row]
		sisa = flt(rinci["sisa"])
		dipakai = flt(baris.allocated_amount, baris.precision("allocated_amount"))

		if dipakai < 0:
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} tidak boleh negatif.").format(baris.idx),
				title=_("Uang Muka PO"),
			)

		if dipakai > flt(sisa, baris.precision("advance_amount")):
			frappe.throw(
				_("Uang muka yang dipakai di baris {0} ({1}) melebihi sisanya ({2}). "
				  "Payment Entry {3} sudah terpakai {4} di invoice lain dan {5} sudah "
				  "dikembalikan ke supplier.").format(
					baris.idx,
					frappe.format_value(dipakai, {"fieldtype": "Currency"}),
					frappe.format_value(sisa, {"fieldtype": "Currency"}),
					info.payment_entry,
					frappe.format_value(rinci["terpakai"], {"fieldtype": "Currency"}),
					frappe.format_value(rinci["dikembalikan"], {"fieldtype": "Currency"}),
				),
				title=_("Uang Muka PO"),
			)

		if not akun_uang_muka_pe(info.payment_entry, info.purchase_order):
			frappe.throw(
				_("Akun uang muka untuk Payment Entry {0} tidak ketemu.").format(info.payment_entry),
				title=_("Uang Muka PO"),
			)

		baris.advance_amount = sisa

	# Penjaga ini sengaja hanya dipasang kalau ada uang muka PO. Kelebihan alokasi
	# advance biasa masih dicegat rekonsiliasi bawaan; uang muka PO melewati
	# rekonsiliasi itu, jadi kelebihannya baru ketahuan sebagai jurnal yang lebih
	# besar dari tagihan dan outstanding minus.
	total_advance = flt(doc.total_advance, doc.precision("total_advance"))
	tagihan = flt(doc.get("rounded_total") or doc.grand_total, doc.precision("grand_total"))

	if total_advance > tagihan:
		frappe.throw(
			_("Total advance ({0}), termasuk uang muka Purchase Order, melebihi nilai invoice ({1}).").format(
				frappe.format_value(total_advance, {"fieldtype": "Currency"}),
				frappe.format_value(tagihan, {"fieldtype": "Currency"}),
			),
			title=_("Uang Muka PO"),
		)


def party_akun_uang_muka(doc, akun_uang_muka, purchase_order):
	"""Party dan against_voucher untuk leg kredit akun uang muka.

	Akun uang muka biasanya dipasang bertipe Payable supaya saldonya bisa
	ditelusuri per supplier. Kalau begitu, `validate_party` di general_ledger
	mewajibkan party di setiap GL entry yang menyentuhnya, dan Payment Ledger
	Entry-nya ikut terbentuk. against_voucher-nya dibuat sama dengan yang
	dipakai Payment Entry waktu membayar PO — Purchase Order, bukan invoice ini
	— supaya kreditnya menutup debit uang muka yang sudah ada di sana, bukan
	menggantung sebagai saldo baru.

	Akun bertipe lain tidak masuk payment ledger, jadi dibiarkan tanpa party
	seperti jurnal biasa.
	"""
	if frappe.get_cached_value("Account", akun_uang_muka, "account_type") not in (
		"Payable",
		"Receivable",
	):
		return {}

	return {
		"party_type": "Supplier",
		"party": doc.supplier,
		"against_voucher_type": "Purchase Order",
		"against_voucher": purchase_order,
	}


def kurangi_baris_hutang(doc, gl_entries, jumlah, jumlah_base=None):
	"""Potong baris hutang invoice sebesar uang muka yang dipakai.

	Dipotong langsung di barisnya, bukan ditambahkan sebagai baris debit
	terpisah. merge_similar_entries() menjumlahkan debit dan kredit sendiri-
	sendiri, jadi baris debit terpisah akan tetap menyisakan angka di kedua sisi
	walaupun barisnya sudah menyatu. Dengan dipotong di sini, credit_to keluar
	sebagai satu baris bernilai bersih di sisi kredit saja.

	Mengembalikan False kalau baris hutangnya tidak ada — invoice tipe SPK dan
	Leasing tidak memanggil make_supplier_gl_entry() sama sekali.
	"""
	if jumlah_base is None:
		jumlah_base = jumlah

	for entry in gl_entries:
		if entry.get("account") != doc.credit_to or not flt(entry.get("credit")):
			continue

		# credit memakai mata uang perusahaan, credit_in_transaction_currency
		# memakai mata uang invoice, dan credit_in_account_currency ikut mata
		# uang akun hutangnya.
		entry["credit"] = flt(entry.get("credit")) - jumlah_base
		entry["credit_in_account_currency"] = flt(entry.get("credit_in_account_currency")) - (
			jumlah_base if doc.party_account_currency == doc.company_currency else jumlah
		)
		entry["credit_in_transaction_currency"] = flt(entry.get("credit_in_transaction_currency")) - jumlah

		return True

	return False


def gl_entries_uang_muka(doc, gl_entries):
	"""K: akun uang muka, dan hutang invoice dipotong sebesar yang dialokasikan.

	Potongan hutangnya memakai `against_voucher` invoice ini sendiri supaya
	outstanding-nya berkurang lewat payment ledger, tanpa menyentuh Payment
	Entry yang membayar PO. Mengembalikan jumlah baris jurnal yang berubah.
	"""
	pasangan = pasangan_uang_muka_po(doc)
	if not pasangan:
		return 0

	cost_center = doc.cost_center or frappe.db.get_value("Company", doc.company, "cost_center")
	# Kolom debit/credit GL memakai mata uang perusahaan, sedangkan
	# allocated_amount memakai mata uang invoice. Untuk invoice rupiah
	# kursnya 1 sehingga nilainya sama.
	kurs = flt(doc.conversion_rate) or 1.0
	akun_dipakai = []
	total = 0
	total_base = 0
	ditambahkan = 0

	for baris, info in pasangan:
		dipakai = flt(baris.allocated_amount, baris.precision("allocated_amount"))
		if not dipakai:
			continue

		dipakai_base = flt(dipakai * kurs, baris.precision("allocated_amount"))

		akun_uang_muka = akun_uang_muka_pe(info.payment_entry, info.purchase_order)
		keterangan = _("Uang muka {0} lewat {1}").format(info.purchase_order, info.payment_entry)

		kredit = {
			"account": akun_uang_muka,
			"against": doc.credit_to,
			"credit": dipakai_base,
			"credit_in_transaction_currency": dipakai,
			"cost_center": cost_center,
			"project": doc.project,
			"remarks": keterangan,
		}
		kredit.update(party_akun_uang_muka(doc, akun_uang_muka, info.purchase_order))

		gl_entries.append(doc.get_gl_dict(kredit))

		akun_dipakai.append(akun_uang_muka)
		total += dipakai
		total_base += dipakai_base
		ditambahkan += 1

	if not total:
		return ditambahkan

	if not kurangi_baris_hutang(doc, gl_entries, total, total_base):
		gl_entries.append(
			doc.get_gl_dict(
				{
					"account": doc.credit_to,
					"party_type": "Supplier",
					"party": doc.supplier,
					"due_date": doc.due_date,
					"against": ", ".join(sorted(set(akun_dipakai))),
					"debit": total_base,
					"debit_in_transaction_currency": total,
					"against_voucher": doc.name,
					"against_voucher_type": doc.doctype,
					"cost_center": cost_center,
					"project": doc.project,
				},
				doc.party_account_currency,
			)
		)
		ditambahkan += 1

	return ditambahkan


# ─── Sisa uang muka per Purchase Order ────────────────────────────────────────
#
# Uang muka yang sudah dibayar tidak pernah tercatat berkurang di dokumennya
# sendiri: baris Payment Entry Reference-nya tetap utuh menempel di PO. Yang
# mengurangi ada dua, dan keduanya dokumen lain — pemakaian di Purchase Invoice
# (tabel `advances`) dan pengembalian uang lewat Payment Entry penerimaan yang
# menunjuk PO yang sama. Sisanya karena itu selalu dihitung, bukan disimpan.


def baris_uang_muka_po(purchase_orders):
	"""Baris Payment Entry Reference yang membayar uang muka PO, urut waktu bayar.

	Hanya Payment Entry tipe Pay; yang tipe Receive justru pengembaliannya.
	"""
	if not purchase_orders:
		return []

	return frappe.db.sql(
		"""
		select
			per.name,
			per.parent as payment_entry,
			per.reference_name as purchase_order,
			per.allocated_amount,
			pe.posting_date,
			pe.paid_to as akun_uang_muka
		from `tabPayment Entry Reference` per
		inner join `tabPayment Entry` pe on pe.name = per.parent
		where per.reference_doctype = 'Purchase Order'
			and per.reference_name in %(po)s
			and per.docstatus = 1
			and pe.payment_type = 'Pay'
		order by pe.posting_date, pe.name, per.idx
		""",
		{"po": list(purchase_orders)},
		as_dict=True,
	)


def baris_pengembalian_uang_muka(purchase_orders, kecuali_pe=None):
	"""Payment Entry penerimaan yang menarik balik uang muka PO.

	`kecuali_pe` melewati satu Payment Entry — dipakai waktu memvalidasi
	pengembalian yang sedang disubmit, karena frappe sudah menyetel docstatus 1
	sebelum validate dijalankan.
	"""
	if not purchase_orders:
		return []

	return frappe.db.sql(
		"""
		select
			per.parent as payment_entry,
			per.reference_name as purchase_order,
			per.allocated_amount,
			pe.posting_date,
			pe.paid_from as akun_uang_muka
		from `tabPayment Entry Reference` per
		inner join `tabPayment Entry` pe on pe.name = per.parent
		where per.reference_doctype = 'Purchase Order'
			and per.reference_name in %(po)s
			and per.docstatus = 1
			and pe.payment_type = 'Receive'
			and per.parent != %(kecuali_pe)s
		order by pe.posting_date, pe.name, per.idx
		""",
		{"po": list(purchase_orders), "kecuali_pe": kecuali_pe or ""},
		as_dict=True,
	)


def dikembalikan_per_baris(purchase_orders, kecuali_pe=None):
	"""Bagi uang muka yang sudah dikembalikan ke baris pembayarannya.

	Pengembalian menunjuk PO-nya, bukan baris pembayaran mana yang ditarik balik
	— satu PO bisa dibayar berkali-kali. Dibagi ke baris yang paling tua dulu,
	dibatasi sisa tiap baris setelah dipakai invoice, supaya pembagiannya sama
	siapa pun yang menghitung dan tidak berubah-ubah tiap kali dipanggil.

	Pemakaian invoice di sini sengaja dihitung tanpa pengecualian invoice mana
	pun: patokan pembagiannya harus satu, tidak boleh ikut invoice yang kebetulan
	sedang dibuka. Kelebihan yang tidak kebagian dibebankan ke baris terakhir
	supaya totalnya tidak bocor.
	"""
	total_per_po = {}
	for row in baris_pengembalian_uang_muka(purchase_orders, kecuali_pe=kecuali_pe):
		total_per_po[row.purchase_order] = flt(total_per_po.get(row.purchase_order)) + flt(
			row.allocated_amount
		)

	if not total_per_po:
		return {}

	baris = baris_uang_muka_po(total_per_po)
	terpakai = terpakai_di_invoice_lain([row.name for row in baris])

	hasil = {}
	baris_terakhir = {}
	for row in baris:
		baris_terakhir[row.purchase_order] = row.name

		belum_dibagi = flt(total_per_po.get(row.purchase_order))
		if belum_dibagi <= 0:
			continue

		muat = max(flt(row.allocated_amount) - terpakai.get(row.name, 0.0), 0.0)
		diambil = min(muat, belum_dibagi)
		if diambil:
			hasil[row.name] = flt(hasil.get(row.name)) + diambil
			total_per_po[row.purchase_order] = belum_dibagi - diambil

	for po, sisa in total_per_po.items():
		if flt(sisa, 2) > 0 and po in baris_terakhir:
			hasil[baris_terakhir[po]] = flt(hasil.get(baris_terakhir[po])) + sisa

	return hasil


def sisa_per_baris(info_per_baris, kecuali=None, kecuali_pe=None):
	"""Sisa tiap baris uang muka: dibayar - dipakai invoice - dikembalikan.

	`info_per_baris` memetakan nama baris Payment Entry Reference ke datanya,
	seperti yang dikembalikan referensi_pe_ke_po(). `kecuali` melewati satu
	Purchase Invoice, `kecuali_pe` satu Payment Entry pengembalian.
	"""
	if not info_per_baris:
		return {}

	terpakai = terpakai_di_invoice_lain(list(info_per_baris), kecuali=kecuali)
	dikembalikan = dikembalikan_per_baris(
		{info.purchase_order for info in info_per_baris.values()}, kecuali_pe=kecuali_pe
	)

	hasil = {}
	for nama, info in info_per_baris.items():
		dipakai = flt(terpakai.get(nama))
		kembali = flt(dikembalikan.get(nama))
		hasil[nama] = {
			"terpakai": dipakai,
			"dikembalikan": kembali,
			"sisa": flt(info.allocated_amount) - dipakai - kembali,
		}

	return hasil


def sisa_uang_muka_po(purchase_orders, kecuali_pe=None):
	"""Sisa uang muka tiap PO, dijumlahkan dari baris-baris pembayarannya."""
	baris = baris_uang_muka_po(purchase_orders)
	rincian = sisa_per_baris({row.name: row for row in baris}, kecuali_pe=kecuali_pe)

	hasil = {po: 0.0 for po in purchase_orders}
	for row in baris:
		hasil[row.purchase_order] = flt(hasil.get(row.purchase_order)) + flt(
			rincian[row.name]["sisa"]
		)

	return hasil


def invoice_pemakai_uang_muka(reference_rows):
	"""Purchase Invoice yang memakai tiap baris uang muka, untuk ditampilkan."""
	if not reference_rows:
		return {}

	hasil = frappe.db.sql(
		"""
		select pia.reference_row, pia.parent as purchase_invoice, pia.allocated_amount
		from `tabPurchase Invoice Advance` pia
		where pia.parenttype = 'Purchase Invoice'
			and pia.docstatus = 1
			and pia.reference_type = 'Payment Entry'
			and pia.reference_row in %(rows)s
		order by pia.parent
		""",
		{"rows": list(reference_rows)},
		as_dict=True,
	)

	peta = {}
	for row in hasil:
		peta.setdefault(row.reference_row, []).append(row)

	return peta


def rekap_uang_muka_po(purchase_order, kecuali_pe=None):
	"""Rincian uang muka satu PO: dibayar, dipakai, dikembalikan, dan sisanya.

	`kecuali_pe` melewati satu Payment Entry pengembalian — dipakai dokumen yang
	sedang disubmit, yang barisnya sudah berdocstatus 1 waktu validate jalan.
	"""
	po = frappe.db.get_value(
		"Purchase Order",
		purchase_order,
		["name", "supplier", "supplier_name", "company", "currency", "status", "docstatus"],
		as_dict=True,
	)
	if not po:
		frappe.throw(_("Purchase Order {0} tidak ditemukan.").format(purchase_order))

	baris = baris_uang_muka_po([purchase_order])
	rincian = sisa_per_baris({row.name: row for row in baris}, kecuali_pe=kecuali_pe)
	pemakai = invoice_pemakai_uang_muka([row.name for row in baris])

	rekap = {
		"purchase_order": po.name,
		"supplier": po.supplier,
		"supplier_name": po.supplier_name,
		"company": po.company,
		"currency": po.currency,
		"status": po.status,
		"baris": [],
		"pengembalian": baris_pengembalian_uang_muka([purchase_order], kecuali_pe=kecuali_pe),
		"total_dibayar": 0.0,
		"total_terpakai": 0.0,
		"total_dikembalikan": 0.0,
		"sisa": 0.0,
	}

	for row in baris:
		rinci = rincian[row.name]
		rekap["baris"].append(
			{
				"baris": row.name,
				"payment_entry": row.payment_entry,
				"posting_date": row.posting_date,
				"akun_uang_muka": row.akun_uang_muka,
				"dibayar": flt(row.allocated_amount),
				"terpakai": rinci["terpakai"],
				"dikembalikan": rinci["dikembalikan"],
				"sisa": rinci["sisa"],
				"invoice": pemakai.get(row.name, []),
			}
		)
		rekap["total_dibayar"] += flt(row.allocated_amount)
		rekap["total_terpakai"] += rinci["terpakai"]
		rekap["total_dikembalikan"] += rinci["dikembalikan"]
		rekap["sisa"] += rinci["sisa"]

	return rekap


def akun_uang_muka_tersisa(purchase_order, kecuali_pe=None):
	"""Akun tempat sisa uang muka PO ini duduk.

	Dibaca dari pembayarannya, bukan dari Procurement Settings, supaya
	pengembaliannya mengkredit akun yang benar-benar terdebit walaupun
	setting-nya sudah berganti sesudah pembayaran.
	"""
	akun = {
		row["akun_uang_muka"]
		for row in rekap_uang_muka_po(purchase_order, kecuali_pe=kecuali_pe)["baris"]
		if flt(row["sisa"]) > 0
	}

	if len(akun) > 1:
		frappe.throw(
			_("Sisa uang muka {0} duduk di lebih dari satu akun ({1}). "
			  "Kembalikan lewat Payment Entry sendiri-sendiri per akun.").format(
				purchase_order, ", ".join(sorted(akun))
			),
			title=_("Uang Muka PO"),
		)

	return akun.pop() if akun else None


def sisa_advance_uang_muka_po(doc, entries):
	"""Uang muka PO ditawarkan sebesar sisanya, bukan sebesar yang dibayar.

	Baris Payment Entry Reference-nya tidak pernah berkurang, jadi angka bawaan
	selalu utuh. Tanpa dipotong di sini, uang muka yang sudah habis dipakai
	invoice lain atau sudah dikembalikan tetap tampak tersedia dan penjaga
	Uang Muka Belum Diambil menahan invoice yang tidak punya apa-apa lagi untuk
	ditarik.
	"""
	kandidat = [
		d.get("reference_row")
		for d in entries
		if d.get("against_order") and d.get("reference_row")
	]
	if not kandidat:
		return entries

	rincian = sisa_per_baris(referensi_pe_ke_po(kandidat), kecuali=doc.name)

	hasil = []
	for d in entries:
		rinci = rincian.get(d.get("reference_row")) if d.get("against_order") else None
		if rinci is None:
			hasil.append(d)
			continue

		if flt(rinci["sisa"]) <= 0:
			continue

		d["amount"] = flt(rinci["sisa"])
		hasil.append(d)

	return hasil
