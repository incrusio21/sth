# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

from sth.finance_sth.doctype.pdo_bahan_bakar_vtwo.pdo_bahan_bakar_vtwo import process_pdo_bahan_bakar
from sth.finance_sth.doctype.pdo_perjalanan_dinas_vtwo.pdo_perjalanan_dinas_vtwo import process_pdo_perjalanan_dinas
from sth.finance_sth.doctype.pdo_kas_vtwo.pdo_kas_vtwo import process_pdo_kas
from sth.finance_sth.doctype.pdo_dana_cadangan_vtwo.pdo_dana_cadangan_vtwo import process_pdo_dana_cadangan
from sth.finance_sth.doctype.pdo_non_pdo_vtwo.pdo_non_pdo_vtwo import process_pdo_non_pdo

PROCESSORS_INSERT = {
	"Bahan Bakar": process_pdo_bahan_bakar,
	"Perjalanan Dinas": process_pdo_perjalanan_dinas,
	"Kas": process_pdo_kas,
	"Dana Cadangan": process_pdo_dana_cadangan,
	"NON PDO": process_pdo_non_pdo,
}
pdo_categories = ["Bahan Bakar", "Perjalanan Dinas", "Kas", "Dana Cadangan", "NON PDO"]

class PermintaanDanaOperasional(Document):
	def validate(self):
		self.update_pdo_default_account()
		self.validate_child_tables()
		if self.docstatus == 0:
			self.hitung_total()

		self.check_duplicate()

	def update_pdo_default_account(self):
		pass
		# if not self.bahan_bakar_debit_to:
		# 	self.bahan_bakar_debit_to = frappe.get_doc("Company", self.company).default_pdo_bahan_bakar_account

	def check_duplicate(self):
		filters = {
			"months": self.months,
			"fiscal_year": self.fiscal_year,
			"unit": self.unit,
			"docstatus": ["!=", 2],  # exclude Cancelled
		}

		# Exclude dokumen saat ini jika sudah tersimpan (edit mode)
		if self.name:
			filters["name"] = ["!=", self.name]

		existing = frappe.db.get_value(
			"Permintaan Dana Operasional",
			filters,
			["name", "months", "fiscal_year", "unit"],
			as_dict=True,
		)

		if existing:
			frappe.throw(
				_(
					"Permintaan Dana Operasional sudah ada untuk "
					"<b>Bulan: {0}</b>, <b>Tahun Fiskal: {1}</b>, <b>Unit: {2}</b>.<br><br>"
					"Dokumen yang sudah ada: <a href='/app/permintaan-dana-operasional/{3}'>{3}</a>"
				).format(
					self.months,
					self.fiscal_year,
					self.unit,
					existing.name,
				),
				title=_("Duplikasi Permintaan Dana Operasional"),
			)
		
	def on_update(self):
		if self.docstatus == 0:
			self.outstanding_amount = self.grand_total_pdo

	def before_submit(self):
		self.submit_pdo_vtwo()
		self.outstanding_amount = self.grand_total_pdo

	def before_cancel(self):
		self.cancel_pdo_vtwo()

	def on_trash(self):
		self.delete_pdo_vtwo()

	def process_data_to_insert_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if not self.get(f"pdo_{fieldname}") and not self.get(f"{fieldname}_transaction_number"):
				continue
			
			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
				continue

			data = {
				"grand_total": self.get(f"grand_total_{fieldname}"),
				"outstanding_amount": self.get(f"outstanding_amount_{fieldname}"),
				"credit_to": self.get(f"{fieldname}_credit_to"),
				"reference_doc": "Permintaan Dana Operasional",
				"reference_name": self.name,
				"employee": frappe.db.get_single_value("Payment Settings", "internal_employee"),
				"cost_center": self.get(f"{fieldname}_cost_center"),
				"company": self.company,
				"unit": self.unit,
				"posting_date": self.posting_date,
				"required_by": self.required_by,
			}

			if pdo == "Bahan Bakar":
				data.update({"debit_to": self.get(f"{fieldname}_debit_to")})
			
			childs = self.get(f"pdo_{fieldname}")
			
			handlers = PROCESSORS_INSERT.get(pdo)
			if handlers:
				handlers(data, childs)
	
	def submit_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number") and self.get(f"grand_total_{fieldname}") > 0:
				print(str(pdo))
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.submit()
	
	def cancel_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number") and self.get(f"grand_total_{fieldname}") > 0:
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.cancel()
	
	def delete_pdo_vtwo(self):
		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if self.get(f"pdo_{fieldname}") and self.get(f"{fieldname}_transaction_number"):
				doctype_vtwo = f"PDO {pdo} Vtwo"
				docname_vtwo = self.get(f"{fieldname}_transaction_number")
				doc = frappe.get_doc(doctype_vtwo, docname_vtwo)
				doc.delete()
	
	def validate_child_tables(self):
		validation_map = {
			"pdo_bahan_bakar": ["plafon", "unit_price", "revised_plafon", "revised_unit_price"],
			"pdo_perjalanan_dinas": ["plafon", "hari_dinas", "revised_plafon", "revised_duty_day"],
			"pdo_kas": ["qty", "price", "revised_qty", "revised_price"],
			"pdo_dana_cadangan": ["amount", "revised_amount"],
			"pdo_non_pdo": ["qty", "price", "revised_qty", "revised_price"],
		}

		for pdo in pdo_categories:
			fieldname = pdo.lower().replace(" ", "_")

			if not self.get(f"pdo_{fieldname}") and not self.get(f"{fieldname}_transaction_number"):
				continue
			for row in self.get(f"pdo_{fieldname}"):
				for valid in validation_map[f"pdo_{fieldname}"]:
					if row.get(valid):
						if row.get(valid) > 0:
							continue
						msg = f"Pada Tabel {pdo} baris ke {row.idx} field currency atau angka harus lebih besar dari 0"
						frappe.throw(msg)
	
	def hitung_total(self):
		list_pdo = ["Bahan Bakar","Perjalanan Dinas", "Kas", "Dana Cadangan"]

		tipe_mapping = {
			'Bahan Bakar': {
				'child_table': 'pdo_bahan_bakar',
				'amount_field': 'revised_price_total',
				'grand_total_field': 'grand_total_bahan_bakar',
				'outstanding_field': 'outstanding_amount_bahan_bakar',
				'before_amount_field' : 'price_total'
			},
			'Perjalanan Dinas': {
				'child_table': 'pdo_perjalanan_dinas',
				'amount_field': 'revised_total',
				'grand_total_field': 'grand_total_perjalanan_dinas',
				'outstanding_field': 'outstanding_amount_perjalanan_dinas',
				'before_amount_field' : 'total'
			},
			'Kas': {
				'child_table': 'pdo_kas',
				'amount_field': 'revised_total',
				'grand_total_field': 'grand_total_kas',
				'outstanding_field': 'outstanding_amount_kas',
				'before_amount_field' : 'total'
			},
			'Dana Cadangan': {
				'child_table': 'pdo_dana_cadangan',
				'amount_field': 'amount',
				'grand_total_field': 'grand_total_dana_cadangan',
				'outstanding_field': 'outstanding_amount_dana_cadangan',
				'before_amount_field' : 'amount'
			}
		}

		for row in self.get("pdo_kas"):
			if row.qty == 0 and row.revised_qty == 0:
				row.qty = 1
				row.total = row.qty * row.price

		total = 0
		for satu_pdo in list_pdo:
			grand_total = 0
			mapping = tipe_mapping[satu_pdo]
			for row in self.get(mapping['child_table']):
				if row.get(mapping['amount_field']):
					if row.get(mapping['amount_field']):
						grand_total += row.get(mapping['amount_field'])
				else:
					if row.get(mapping['before_amount_field']):
						grand_total += row.get(mapping['before_amount_field'])

			self.set(mapping['grand_total_field'], grand_total)
			self.set(mapping['outstanding_field'], grand_total)

			total += grand_total

		self.grand_total_pdo = total
		if self.docstatus == 0:
			self.outstanding_amount	= total




@frappe.whitelist()
def filter_type(doctype, txt, searchfield, start, page_len, filters):
	ect = frappe.qb.DocType("Expense Claim Type")
	eca = frappe.qb.DocType("Expense Claim Account")
	
	# query = (
	# 	frappe.qb.from_(ect)
	# 	.select(ect.name.as_('value'))
	# 	.inner_join(eca)
	# 	.on(
	# 		(ect.name == eca.parent) &
	# 		(ect.custom_routine_type == filters.get('routine_type')) 
	# 	)
	# 	.where(
	# 		(eca.company == filters.get('company')) &
	# 		(ect.name.like(f"%{txt}%"))  
	# 	)
	# )
	if filters.get("pdo_type"):
		query = (
			frappe.qb.from_(ect)
			.select(ect.name.as_('value'))
			.inner_join(eca)
			.on(
				(ect.name == eca.parent) 
			)
			.where(
				(eca.company == filters.get('company')) &
				(ect.name.like(f"%{txt}%"))  &
				(ect.custom_pdo_type == filters.get("pdo_type"))  
			)
		)
	else:
		query = (
			frappe.qb.from_(ect)
			.select(ect.name.as_('value'))
			.inner_join(eca)
			.on(
				(ect.name == eca.parent) 
			)
			.where(
				(eca.company == filters.get('company')) &
				(ect.name.like(f"%{txt}%"))  
			)
		)

	return query.run()

@frappe.whitelist()
def get_expense_account(company, parent):
	default_account = frappe.db.get_value("Expense Claim Account", {
		"company": company,
		"parent": parent
	}, "default_account")
	
	return default_account

@frappe.whitelist()
def filter_fund_type(doctype, txt, searchfield, start, page_len, filters):
	account = frappe.qb.DocType("Account")
	account_type = list(["Cash", "Bank"])
	query = (
		frappe.qb.from_(account)
		.select(account.name.as_('value'))
		.where(
			(account.company == filters.get('company')) &
			(account.disabled == 0) &
			(account.account_type.isin(account_type)) &
			(account.name.like(f"%{txt}%"))  
		)
	)

	return query.run()

@frappe.whitelist()
def create_payment_voucher(source_name, target_doc=None):
	
	def validate_source(source):
		if source.payment_voucher:
			frappe.throw(_("Payment Voucher already created: {0}").format(source.payment_voucher))
	
	def set_missing_values(source, target):
		unit_doc = frappe.get_doc("Unit", source.unit)
		# if not unit_doc.bank_account:
		# 	frappe.throw(_("Bank Account not set for Unit: {0}").format(source.unit))
		# target.paid_to = unit_doc.bank_account
		
		target.payment_type = "Internal Transfer"
		# target.paid_to = unit_doc.bank_account
		# target.paid_from = "1111001 - KAS HO - TML"

		target.tipe_transfer = "PDO"

		settings = frappe.get_doc("PDO Account Settings")
		account_row = next(
			(row for row in settings.pdo_account_settings_table if row.company == target.company),
			None
		)	

		target.mode_of_payment = "Cash"
		# target.paid_from = account_row.kas_ho_account
		target.paid_to = account_row.kas_dan_bank_dalam_perjalanan
		
		
		total_amount = (
			(source.grand_total_bahan_bakar or 0) +
			(source.grand_total_perjalanan_dinas or 0) +
			(source.grand_total_kas or 0) +
			(source.grand_total_dana_cadangan or 0) +
			(source.grand_total_non_pdo or 0)
		)
		
		if total_amount <= 0:
			frappe.throw(_("Total amount must be greater than zero"))
		
		target.paid_amount = total_amount
		target.received_amount = total_amount
		target.posting_date = frappe.utils.today()
		target.source_exchange_rate = 1
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.remarks = _("Payment HO for Permintaan Dana Operasional {0}").format(source.name)
		target.unit = ""
		target.naming_series = "ACC-PAY-.YYYY.-"
	
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	validate_source(source_doc)
	
	doclist = get_mapped_doc(
		"Permintaan Dana Operasional",
		source_name,
		{
			"Permintaan Dana Operasional": {
				"doctype": "Payment Entry",
				"field_map": {
					"name": "permintaan_dana_operasional",
					"unit": "unit",
					"company": "company"
				}
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist

@frappe.whitelist()
def create_payment_voucher_kebun(source_name, target_doc=None):
	
	def validate_source(source):
		if source.payment_voucher_kebun:
			frappe.throw(_("Payment Voucher already created: {0}").format(source.payment_voucher_kebun))

	
	def set_missing_values(source, target):
		unit_doc = frappe.get_doc("Unit", source.unit)
		target.payment_type = "Internal Transfer"
		target.tipe_transfer = "Penerimaan Dana PDO"

		settings = frappe.get_doc("PDO Account Settings")
		account_row = next(
			(row for row in settings.pdo_account_settings_table if row.company == target.company),
			None
		)	

		target.paid_from = account_row.kas_ho_account
		target.paid_to = account_row.kas_dan_bank_dalam_perjalanan
		
		
		total_amount = (
			(source.grand_total_bahan_bakar or 0) +
			(source.grand_total_perjalanan_dinas or 0) +
			(source.grand_total_kas or 0) +
			(source.grand_total_dana_cadangan or 0) +
			(source.grand_total_non_pdo or 0)
		)
		
		if total_amount <= 0:
			frappe.throw(_("Total amount must be greater than zero"))
		
		# Set basic fields
		target.payment_type = "Internal Transfer"
		target.source_exchange_rate = 1
		target.paid_amount = total_amount
		target.received_amount = total_amount
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.tipe_transfer = "Penerimaan Dana PDO"
		target.payment_voucher_kas_pdo = []
		target.remarks = _("Penerimaan Kebun for Permintaan Dana Operasional {0}").format(source.name)
		payment_voucher = frappe.get_doc("Payment Entry", source.payment_voucher)
		target.paid_from = payment_voucher.paid_to
		target.naming_series = "ACC-PAY-.YYYY.-"
		
		unit_doc = frappe.get_doc("Unit", source.unit)
		if not unit_doc.bank_account:
			frappe.throw(_("Bank Account not set for Unit: {0}").format(source.unit))
		target.paid_to = unit_doc.bank_account
		target.mode_of_payment = "Bank Draft"
	
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	validate_source(source_doc)
	
	doclist = get_mapped_doc(
		"Permintaan Dana Operasional",
		source_name,
		{
			"Permintaan Dana Operasional": {
				"doctype": "Payment Entry",
				"field_map": {
					"name": "permintaan_dana_operasional",
					"unit": "unit",
					"company": "company"
				}
			}
		},
		target_doc,
		set_missing_values
	)
	
	return doclist


# Peta tipe PDO ke child table dan nama field-nya. Di level modul karena dipakai
# dua jalur realisasi: tombol di PDO dan tombol di Payment Entry.
TIPE_MAPPING = {
	'Bahan Bakar': {
		'child_table': 'pdo_bahan_bakar',
		'debit_account_field': None,  # Uses header field instead
		'header_debit_field': 'bahan_bakar_debit_to',  # Account at header level
		'employee_field': 'employee',
		'amount_field': 'revised_price_total',
		'grand_total_field': 'grand_total_bahan_bakar',
		'outstanding_field': 'outstanding_amount_bahan_bakar',
		'before_amount_field': 'price_total',
		'detail_field': None
	},
	'Perjalanan Dinas': {
		'child_table': 'pdo_perjalanan_dinas',
		'debit_account_field': 'debit_to',  # Field in child table
		'header_debit_field': None,  # No header field
		'employee_field': 'employee',
		'amount_field': 'revised_total',
		'grand_total_field': 'grand_total_perjalanan_dinas',
		'outstanding_field': 'outstanding_amount_perjalanan_dinas',
		'before_amount_field': 'total',
		'detail_field': None
	},
	'Kas': {
		'child_table': 'pdo_kas',
		'debit_account_field': 'debit_to',  # Field in child table
		'header_debit_field': None,
		'employee_field': 'employee',
		'amount_field': 'revised_total',
		'grand_total_field': 'grand_total_kas',
		'outstanding_field': 'outstanding_amount_kas',
		'before_amount_field': 'total',
		'detail_field': 'type'
	},
	'Dana Cadangan': {
		'child_table': 'pdo_dana_cadangan',
		'debit_account_field': 'fund_type',  # Field in child table
		'header_debit_field': None,
		'employee_field': 'employee',
		'amount_field': 'revised_amount',
		'grand_total_field': 'grand_total_dana_cadangan',
		'outstanding_field': 'outstanding_amount_dana_cadangan',
		'before_amount_field': 'amount',
		'detail_field': None
	}
}

# Satu baris realisasi gabungan bisa mewakili beberapa baris PDO sekaligus,
# jadi pdo_child_name menyimpan daftar yang dipisah tanda ini.
PEMISAH_CHILD = ","


def gabung_per_item_barang(rows):
	"""Gabungkan baris realisasi jadi satu baris per nama barang. Fungsi murni.

	Kuncinya `item_barang` saja: satu centangan = satu baris, apa pun isinya.
	`debit_to` aman ikut digabung karena untuk tipe Kas selalu diambil dari
	Expense Claim Type, jadi sama untuk satu nama barang.

	`penerima` hanya dibawa kalau semua baris yang digabung memang orang yang
	sama. Kalau berbeda, dikosongkan — mengisi salah satu nama akan membuat baris
	itu seolah-olah milik satu pegawai padahal uangnya untuk beberapa orang.
	"""
	gabungan = {}
	urutan = []

	for row in rows:
		kunci = row.get("item_barang")

		if kunci not in gabungan:
			gabungan[kunci] = dict(row, total=0.0, pdo_child_name=[])
			urutan.append(kunci)

		baris = gabungan[kunci]
		baris["total"] = flt(baris["total"]) + flt(row.get("total"))

		if baris.get("penerima") != row.get("penerima"):
			baris["penerima"] = None

		if row.get("pdo_child_name"):
			baris["pdo_child_name"].append(row["pdo_child_name"])

	hasil = []
	for kunci in urutan:
		baris = gabungan[kunci]
		baris["pdo_child_name"] = PEMISAH_CHILD.join(baris["pdo_child_name"])
		hasil.append(baris)

	return hasil


def build_baris_realisasi(source_doc, tipe_pdo, ppd=None, nama_barang=None):
	"""Baris `payment_voucher_kas_pdo` untuk satu realisasi PDO.

	Satu tempat untuk dua jalur: tombol Realisasi di PDO dan tombol Realisasi PDO
	di Payment Entry. Sebelumnya jalur kedua membangun barisnya sendiri di JS dan
	melewatkan `revised_total`, akun dari Expense Claim Type, serta penjagaan
	terhadap realisasi ganda.

	Balikan: {"rows": [...], "note": str|None, "paid_to": str|None}
	"""
	if tipe_pdo not in TIPE_MAPPING:
		frappe.throw(_("Invalid Tipe PDO selected"))

	if ppd and tipe_pdo != "Perjalanan Dinas":
		frappe.throw(_("Pertanggungjawaban Perjalanan Dinas hanya berlaku untuk tipe Perjalanan Dinas"))

	nama_terpilih = nama_barang
	if isinstance(nama_terpilih, str):
		# frappe.call mengirim null sebagai string kosong, bukan None
		nama_terpilih = frappe.parse_json(nama_terpilih) if nama_terpilih.strip() else None

	if nama_terpilih and tipe_pdo != "Kas":
		frappe.throw(_("Pilihan Nama Barang hanya berlaku untuk tipe Kas"))

	mapping = TIPE_MAPPING[tipe_pdo]
	debit_account_field = mapping['debit_account_field']
	header_debit_field = mapping['header_debit_field']
	employee_field = mapping['employee_field']
	detail_field = mapping['detail_field']
	amount_field = mapping['amount_field']
	before_amount_field = mapping['before_amount_field']

	child_data = getattr(source_doc, mapping['child_table'], [])
	if not child_data:
		frappe.throw(_("No data found in {0} table").format(tipe_pdo))

	if nama_terpilih:
		# baris yang sudah masuk realisasi sebelumnya tidak boleh ikut lagi
		sudah_realisasi = get_realisasi_pdo_child_names(source_doc.name, tipe_pdo)
		child_data = [
			row for row in child_data
			if row.get(detail_field) in nama_terpilih and row.name not in sudah_realisasi
		]

		if not child_data:
			frappe.throw(_("Tidak ada baris List Kas yang cocok dengan Nama Barang yang dipilih"))

	realisasi_per_baris = get_realisasi_ppd(ppd, source_doc.name) if ppd else None

	header_debit_account = getattr(source_doc, header_debit_field, None) if header_debit_field else None

	# For Bahan Bakar, get debit account from header
	if header_debit_field and not header_debit_account:
		frappe.throw(_("Debit account field {0} not found in source document").format(header_debit_field))

	paid_to = header_debit_account
	rincian_nama_barang = {}
	rows = []

	for row in child_data:
		employee = getattr(row, employee_field, None) if hasattr(row, employee_field) else None

		if realisasi_per_baris is not None:
			# Nilai dibayar = realisasi PPD, sisa plafon tidak ikut dicairkan
			amount = flt(realisasi_per_baris.get(row.name))
			if amount <= 0:
				continue
		else:
			amount = getattr(row, amount_field, 0) or getattr(row, before_amount_field, 0)

		if debit_account_field and row.get(debit_account_field):
			debit_account = row.get(debit_account_field)
		elif header_debit_account:
			debit_account = header_debit_account
		else:
			debit_account = None

		if tipe_pdo in ("Perjalanan Dinas", "Kas"):
			ex_claim_doc = frappe.get_doc("Expense Claim Type", row.type)

			for ex_claim_row in ex_claim_doc.accounts:
				if ex_claim_row.company == source_doc.company:
					debit_account = ex_claim_row.default_account
					if not header_debit_account:
						header_debit_account = ex_claim_row.default_account
						paid_to = header_debit_account

		item_barang = row.get(detail_field) if detail_field else None
		if item_barang:
			rincian_nama_barang[item_barang] = flt(rincian_nama_barang.get(item_barang)) + flt(amount)

		rows.append({
			'no_pdo': source_doc.name,
			'tipe_pdo': tipe_pdo,
			'penerima': employee,
			'total': flt(amount),
			'debit_to': debit_account,
			'pdo_child_name': row.name,
			'item_barang': item_barang
		})

	note = None
	if nama_terpilih:
		# Satu baris per centangan. Penggabungan hanya untuk jalur nama barang —
		# tipe lain tetap satu baris per baris PDO seperti sebelumnya.
		rows = gabung_per_item_barang(rows)

		if rincian_nama_barang:
			note = "\n".join(
				"{0}: {1}".format(nama, frappe.format_value(total, {"fieldtype": "Currency"}))
				for nama, total in rincian_nama_barang.items()
			)

	return {"rows": rows, "note": note, "paid_to": paid_to}


@frappe.whitelist()
def get_baris_realisasi(source_name, tipe_pdo, ppd=None, nama_barang=None):
	"""Baris realisasi untuk Payment Entry yang sudah tersimpan.

	PE yang belum tersimpan memakai `create_payment_voucher_alokasi` yang membuat
	dokumen baru; yang sudah tersimpan cuma perlu isi tabelnya.
	"""
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	hasil = build_baris_realisasi(source_doc, tipe_pdo, ppd, nama_barang)
	hasil["total"] = flt(sum(flt(row["total"]) for row in hasil["rows"]))

	return hasil


@frappe.whitelist()
def create_payment_voucher_alokasi(source_name, tipe_pdo, target_doc=None, ppd=None, nama_barang=None):
	"""Create Payment Voucher Kas from Permintaan Dana Operasional

	Bila `ppd` (Pertanggungjawaban Perjalanan Dinas) diisi, nilai tiap baris diambil dari
	realisasi PPD tersebut, bukan dari plafon PDO. Dengan begitu PPD berfungsi sebagai DP
	dan realisasi yang dibayarkan otomatis terpotong.

	Bila `nama_barang` diisi (khusus tipe Kas), hanya baris List Kas dengan nama barang
	tersebut yang direalisasi, jadi satu baris Payment Entry per nama barang yang
	dicentang, dan rinciannya ditulis ke field Keterangan.
	"""

	if tipe_pdo not in TIPE_MAPPING:
		frappe.throw(_("Invalid Tipe PDO selected"))

	def set_missing_values(source, target):
		# Get Payment Voucher to fetch paid_to account
		if not source.payment_voucher:
			frappe.throw(_("Payment Voucher not found for this PDO"))

		# Set basic fields
		target.payment_type = "Internal Transfer"
		target.source_exchange_rate = 1
		target.paid_from_account_currency = "IDR"
		target.paid_to_account_currency = "IDR"
		target.tipe_transfer = "Realisasi PDO"
		target.naming_series = "ACC-PAY-.YYYY.-"
		target.payment_voucher_kas_pdo = []

		target.remarks = _("Realisasi PDO tipe {1} for Permintaan Dana Operasional {0}").format(source.name, tipe_pdo)

		if ppd:
			target.pertanggungjawaban_perjalanan_dinas = ppd
			target.remarks += _(" - potongan DP dari Pertanggungjawaban Perjalanan Dinas {0}").format(ppd)

		unit_doc = frappe.get_doc("Unit", source.unit)
		if not unit_doc.bank_account:
			frappe.throw(_("Bank Account not set for Unit: {0}").format(source.unit))
		target.paid_from = unit_doc.bank_account
		target.mode_of_payment = "Kas"

		hasil = build_baris_realisasi(source, tipe_pdo, ppd, nama_barang)

		if hasil["paid_to"]:
			target.paid_to = hasil["paid_to"]

		for baris in hasil["rows"]:
			target.append('payment_voucher_kas_pdo', baris)

		if hasil["note"]:
			target.note = hasil["note"]

	# Map document
	doclist = get_mapped_doc(
		"Permintaan Dana Operasional",
		source_name,
		{
			"Permintaan Dana Operasional": {
				"doctype": "Payment Entry",
				"field_map": {
					"company": "company",
					"unit": "unit"
				}
			}
		},
		target_doc,
		set_missing_values
	)
	
	if ppd and not doclist.payment_voucher_kas_pdo:
		frappe.throw(
			_("Pertanggungjawaban Perjalanan Dinas {0} tidak memiliki nilai realisasi yang bisa dicairkan.").format(ppd)
		)

	total = 0
	for row in doclist.payment_voucher_kas_pdo:
		total += row.total
		# pdo_doc = frappe.get_doc("Permintaan Dana Operasional", row.no_pdo)
		# if row.tipe_pdo == "Bahan Bakar":
		# 	total += pdo_doc.outstanding_amount_bahan_bakar
		# elif row.tipe_pdo == "Perjalanan Dinas":
		# 	total += pdo_doc.outstanding_amount_perjalanan_dinas
		# elif row.tipe_pdo == "Kas":
		# 	total += pdo_doc.outstanding_amount_kas
		# elif row.tipe_pdo == "Dana Cadangan":
		# 	total += pdo_doc.outstanding_amount_dana_cadangan

	doclist.paid_amount = total
	doclist.received_amount = total
	doclist.permintaan_dana_operasional = ""

	return doclist

def get_realisasi_ppd(ppd, source_name):
	"""Peta {nama baris pdo_perjalanan_dinas: nilai realisasi} dari sebuah PPD."""
	doc = frappe.get_doc("Pertanggungjawaban Perjalanan Dinas", ppd)

	if doc.docstatus != 1:
		frappe.throw(_("Pertanggungjawaban Perjalanan Dinas {0} belum disubmit.").format(ppd))

	if doc.no_pdo != source_name:
		frappe.throw(
			_("Pertanggungjawaban Perjalanan Dinas {0} bukan milik PDO {1}.").format(ppd, source_name)
		)

	if doc.realisasi_payment_entry:
		frappe.throw(
			_("Pertanggungjawaban Perjalanan Dinas {0} sudah direalisasi pada {1}.").format(
				ppd, doc.realisasi_payment_entry
			)
		)

	realisasi = {}
	for row in doc.costings:
		if not row.pdo_child_name:
			continue
		realisasi[row.pdo_child_name] = flt(realisasi.get(row.pdo_child_name)) + flt(row.jumlah_verifikasi_hrd)

	if not realisasi:
		frappe.throw(
			_("Costings pada {0} tidak terhubung ke baris List Perjalanan Dinas PDO. Muat ulang data dari PDO.").format(ppd)
		)

	return realisasi


def get_realisasi_pdo_child_names(source_name, tipe_pdo):
	"""Baris PDO yang sudah ditarik ke Payment Entry realisasi (draft maupun submit).
	PE yang dibatalkan tidak dihitung, jadi barisnya bebas dipakai lagi.

	Satu baris Payment Entry bisa mewakili beberapa baris PDO sekaligus sejak
	penggabungan per nama barang, jadi isinya dipecah dulu. Baris lama yang cuma
	berisi satu nama tetap terbaca — memecah string tanpa pemisah menghasilkan
	string itu sendiri."""
	rows = frappe.get_all(
		"Payment Voucher Kas PDO",
		filters={
			"no_pdo": source_name,
			"tipe_pdo": tipe_pdo,
			"docstatus": ["<", 2]
		},
		pluck="pdo_child_name"
	)

	names = set()
	for row in rows:
		if not row:
			continue
		names.update(nama.strip() for nama in row.split(PEMISAH_CHILD) if nama.strip())

	return names


@frappe.whitelist()
def get_kas_nama_barang(source_name):
	"""Nama barang di List Kas yang belum direalisasi, dikelompokkan beserta totalnya."""
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	sudah_realisasi = get_realisasi_pdo_child_names(source_name, "Kas")

	rincian = {}
	for row in doc.pdo_kas:
		if not row.type or row.name in sudah_realisasi:
			continue

		amount = flt(row.revised_total) or flt(row.total)
		if amount <= 0:
			continue

		rincian[row.type] = flt(rincian.get(row.type)) + amount

	return [
		{
			"value": nama,
			"label": "{0} ({1})".format(nama, frappe.format_value(total, {"fieldtype": "Currency"})),
			"amount": total
		}
		for nama, total in rincian.items()
	]


@frappe.whitelist()
def get_available_tipe_pdo(source_name):
	"""Get list of tipe_pdo that still have outstanding amounts"""
	
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	
	available_types = []
	
	tipe_checks = [
		('Bahan Bakar', 'outstanding_amount_bahan_bakar', 'grand_total_bahan_bakar'),
		('Perjalanan Dinas', 'outstanding_amount_perjalanan_dinas', 'grand_total_perjalanan_dinas'),
		('Kas', 'outstanding_amount_kas', 'grand_total_kas'),
		('Dana Cadangan', 'outstanding_amount_dana_cadangan', 'grand_total_dana_cadangan')
	]
	
	for tipe, outstanding_field, grand_total_field in tipe_checks:
		outstanding = getattr(doc, outstanding_field, 0) or 0
		grand_total = getattr(doc, grand_total_field, 0) or 0
		
		# Show option if there's a grand total and outstanding amount > 0
		if grand_total > 0 and outstanding > 0:
			available_types.append({
				'value': tipe,
				'label': f'{tipe} (Outstanding: {frappe.format_value(outstanding, {"fieldtype": "Currency"})})'
			})
	
	return available_types

@frappe.whitelist()
def get_pdo_type_by_category(doctype, txt, searchfield, start, page_len, filters):
	category = filters.get('category') if isinstance(filters, dict) else frappe.parse_json(filters).get('category')
	
	return frappe.db.sql("""
		SELECT DISTINCT
			pt.name, pt.name
		FROM
			`tabPDO Type` pt
		INNER JOIN
			`tabPDO Category Type Table` pct ON pct.parent = pt.name
		WHERE
			pct.category = %(category)s
			AND pt.{searchfield} LIKE %(txt)s
		LIMIT %(start)s, %(page_len)s
	""".format(searchfield=searchfield), {
		'category': category,
		'txt': '%{}%'.format(txt),
		'start': start,
		'page_len': page_len
	})