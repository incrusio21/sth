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

# Uang muka Perjalanan Dinas bisa berasal dari dua doctype, tapi dicentang di satu
# MultiCheck. Nilainya "<doctype>::<nama dokumen>", dipisah tanda ini.
PEMISAH_UANG_MUKA = "::"

# Tipe PDO yang barisnya dipilih per nama pengguna, bukan sekaligus satu tabel
TIPE_PILIH_PENGGUNA = ("Bahan Bakar", "Perjalanan Dinas")

# sub_detail di List Kas tidak wajib diisi. Baris yang kosong tetap harus bisa
# direalisasi, jadi diwakili nilai ini di saringan PDO Type dialog realisasi.
KAS_TANPA_PDO_TYPE = "__tanpa_pdo_type__"


def cocok_pdo_type(row, pdo_type):
	"""Apakah baris List Kas termasuk PDO Type yang dipilih di dialog realisasi."""
	if not pdo_type:
		return True

	if pdo_type == KAS_TANPA_PDO_TYPE:
		return not row.get("sub_detail")

	return row.get("sub_detail") == pdo_type


def gabung_per_item_barang(rows):
	"""Gabungkan baris realisasi jadi satu baris per `item_barang`. Fungsi murni.

	`item_barang` berisi nama barang untuk tipe Kas dan nama pengguna untuk tipe
	Bahan Bakar: satu centangan = satu baris, apa pun isinya. `debit_to` aman ikut
	digabung karena untuk tipe Kas selalu diambil dari Expense Claim Type dan untuk
	Bahan Bakar dari satu field di header, jadi sama untuk satu kunci.

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


def parse_pilihan(nilai):
	"""Daftar centangan dari dialog. frappe.call mengirim null sebagai string kosong."""
	if isinstance(nilai, str):
		return frappe.parse_json(nilai) if nilai.strip() else None

	return nilai or None


def build_baris_realisasi(source_doc, tipe_pdo, ppd=None, nama_barang=None, pengguna=None, uang_muka=None, pdo_type=None):
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

	nama_terpilih = parse_pilihan(nama_barang)
	pengguna_terpilih = parse_pilihan(pengguna)
	uang_muka_terpilih = parse_pilihan(uang_muka)

	if nama_terpilih and tipe_pdo != "Kas":
		frappe.throw(_("Pilihan Nama Barang hanya berlaku untuk tipe Kas"))

	if pengguna_terpilih and tipe_pdo not in TIPE_PILIH_PENGGUNA:
		frappe.throw(_("Pilihan Pengguna hanya berlaku untuk tipe Bahan Bakar dan Perjalanan Dinas"))

	if uang_muka_terpilih:
		if tipe_pdo != "Perjalanan Dinas":
			frappe.throw(_("Pilihan Uang Muka hanya berlaku untuk tipe Perjalanan Dinas"))

		if ppd:
			frappe.throw(
				_("Pilih salah satu: field Pertanggungjawaban Perjalanan Dinas atau centangan Uang Muka")
			)

		if not pengguna_terpilih:
			frappe.throw(_("Pilih Pengguna dulu sebelum memilih Uang Muka"))

	uang_muka_per_nama = hitung_uang_muka(source_doc.name, pengguna_terpilih, uang_muka_terpilih)

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

	if pdo_type:
		if tipe_pdo != "Kas":
			frappe.throw(_("Pilihan PDO Type hanya berlaku untuk tipe Kas"))

		# Disaring duluan: satu Jenis bisa dipakai beberapa PDO Type, jadi tanpa ini
		# centangan Jenis akan ikut menarik baris dari PDO Type yang tidak dipilih.
		child_data = [row for row in child_data if cocok_pdo_type(row, pdo_type)]

		if not child_data:
			frappe.throw(_("Tidak ada baris List Kas untuk PDO Type yang dipilih"))

	if nama_terpilih:
		# baris yang sudah masuk realisasi sebelumnya tidak boleh ikut lagi
		sudah_realisasi = get_realisasi_pdo_child_names(source_doc.name, tipe_pdo)
		child_data = [
			row for row in child_data
			if row.get(detail_field) in nama_terpilih and row.name not in sudah_realisasi
		]

		if not child_data:
			frappe.throw(_("Tidak ada baris List Kas yang cocok dengan Nama Barang yang dipilih"))

	if pengguna_terpilih:
		child_data = [row for row in child_data if row.get(employee_field) in pengguna_terpilih]

		if tipe_pdo == "Perjalanan Dinas":
			# Beda dengan Bahan Bakar: plafon perjalanan dinas dicairkan sekali,
			# jadi baris yang sudah ditarik tidak boleh ikut lagi.
			sudah_realisasi = get_realisasi_pdo_child_names(source_doc.name, tipe_pdo)
			child_data = [row for row in child_data if row.name not in sudah_realisasi]

		if not child_data:
			frappe.throw(
				_("Tidak ada baris List {0} yang cocok dengan Pengguna yang dipilih").format(tipe_pdo)
			)

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
		elif pengguna_terpilih and tipe_pdo == "Bahan Bakar":
			# Nominalnya diketik manual di Payment Entry. Plafon PDO cuma acuan —
			# realisasi bahan bakar jarang sama persis dengan plafonnya.
			amount = 0
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

		penerima = employee
		if pengguna_terpilih:
			# Pengguna jadi kunci penggabungan, ditulis apa adanya ke item_barang.
			# penerima cuma diisi kalau pengguna itu memang Employee — untuk kategori
			# Biaya Umum / Operasional isinya teks bebas, bukan pegawai.
			item_barang = employee
			penerima = cari_employee(employee)

		rows.append({
			'no_pdo': source_doc.name,
			'tipe_pdo': tipe_pdo,
			'penerima': penerima,
			'total': flt(amount),
			'debit_to': debit_account,
			'pdo_child_name': row.name,
			'item_barang': item_barang
		})

	note = None
	if nama_terpilih or pengguna_terpilih:
		# Satu baris per centangan. Penggabungan hanya untuk jalur nama barang dan
		# pengguna — tipe lain tetap satu baris per baris PDO seperti sebelumnya.
		rows = gabung_per_item_barang(rows)

	if uang_muka_per_nama:
		# Nilai dibayar mengikuti dokumen uang muka, menggantikan plafon PDO —
		# perlakuan yang sama dengan jalur PPD lewat field ppd.
		for baris in rows:
			if baris["item_barang"] in uang_muka_per_nama:
				baris["total"] = flt(uang_muka_per_nama[baris["item_barang"]])

	if nama_terpilih and rincian_nama_barang:
		note = "\n".join(
			"{0}: {1}".format(nama, frappe.format_value(total, {"fieldtype": "Currency"}))
			for nama, total in rincian_nama_barang.items()
		)
	elif uang_muka_per_nama:
		note = "\n".join(
			"Uang muka {0}: {1}".format(
				nama, frappe.format_value(flt(total), {"fieldtype": "Currency"})
			)
			for nama, total in uang_muka_per_nama.items()
		)
	# Bahan Bakar tidak menulis apa pun ke Keterangan: nominalnya diisi manual dan
	# sisa plafon yang dulu ditulis di sini malah terbaca sebagai nilai tagihan.

	return {"rows": rows, "note": note, "paid_to": paid_to}


def hitung_uang_muka(source_name, pengguna_terpilih, uang_muka_terpilih):
	"""{nama pengguna: nilai uang muka} dari dokumen yang dicentang.

	Uang muka dicocokkan balik ke nama di List Perjalanan Dinas lewat Employee-nya,
	karena kolom Pengguna di PDO bertipe Data dan boleh diisi bebas.
	"""
	if not uang_muka_terpilih:
		return {}

	employee_ke_nama = {}
	for nama in pengguna_terpilih or []:
		employee = cari_employee(nama)
		if employee:
			employee_ke_nama[employee] = nama

	hasil = {}
	for pilihan in uang_muka_terpilih:
		doctype, _pemisah, docname = pilihan.partition(PEMISAH_UANG_MUKA)

		if doctype == "Pertanggungjawaban Perjalanan Dinas":
			# get_realisasi_ppd sekalian memvalidasi: sudah submit, milik PDO ini,
			# dan belum pernah direalisasi
			realisasi = get_realisasi_ppd(docname, source_name)
			amount = sum(flt(nilai) for nilai in realisasi.values())
			employee = frappe.db.get_value(doctype, docname, "employee")
		elif doctype == "Employee Advance":
			employee, amount = frappe.db.get_value(doctype, docname, ["employee", "advance_amount"])
		else:
			frappe.throw(_("Tipe dokumen uang muka tidak dikenal: {0}").format(doctype))

		nama = employee_ke_nama.get(employee)
		if not nama:
			frappe.throw(
				_("Uang muka {0} milik pegawai {1} yang tidak ada di Pengguna yang dicentang").format(
					docname, employee
				)
			)

		hasil[nama] = flt(hasil.get(nama)) + flt(amount)

	return hasil


@frappe.whitelist()
def get_perjalanan_dinas_pengguna(source_name):
	"""Pengguna di List Perjalanan Dinas yang belum direalisasi, beserta plafonnya."""
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	sudah_realisasi = get_realisasi_pdo_child_names(source_name, "Perjalanan Dinas")

	rincian = {}
	urutan = []

	for row in doc.pdo_perjalanan_dinas:
		if not row.employee or row.name in sudah_realisasi:
			continue

		amount = flt(row.revised_total) or flt(row.total)
		if amount <= 0:
			continue

		if row.employee not in rincian:
			rincian[row.employee] = 0
			urutan.append(row.employee)

		rincian[row.employee] += amount

	return [
		{
			"value": nama,
			"label": "{0} (plafon {1})".format(
				nama, frappe.format_value(rincian[nama], {"fieldtype": "Currency"})
			),
			"amount": rincian[nama]
		}
		for nama in urutan
	]


@frappe.whitelist()
def get_uang_muka_pengguna(source_name, pengguna):
	"""Dokumen uang muka milik nama-nama yang dicentang di List Perjalanan Dinas.

	Nama di PDO bertipe Data, jadi dicocokkan dulu ke Employee lewat cari_employee().
	Nama yang bukan pegawai — atau yang pegawainya belum punya uang muka — tidak
	muncul di sini; barisnya tetap bisa direalisasi sebesar plafon.
	"""
	nama_terpilih = parse_pilihan(pengguna) or []

	daftar = []
	for nama in nama_terpilih:
		employee = cari_employee(nama)
		if not employee:
			continue

		daftar.extend(_uang_muka_ppd(source_name, nama, employee))
		daftar.extend(_uang_muka_employee_advance(nama, employee))

	return daftar


def _opsi_uang_muka(doctype, docname, nama, amount, keterangan):
	return {
		"value": "{0}{1}{2}".format(doctype, PEMISAH_UANG_MUKA, docname),
		"label": "{0} — {1} {2} ({3})".format(
			nama, keterangan, docname, frappe.format_value(flt(amount), {"fieldtype": "Currency"})
		),
		"amount": flt(amount)
	}


def _uang_muka_ppd(source_name, nama, employee):
	"""PPD milik PDO ini yang sudah submit dan belum ditarik jadi realisasi."""
	opsi = []

	for ppd in frappe.get_all(
		"Pertanggungjawaban Perjalanan Dinas",
		filters={
			"no_pdo": source_name,
			"employee": employee,
			"docstatus": 1,
			"realisasi_payment_entry": ["is", "not set"]
		},
		pluck="name"
	):
		realisasi = frappe.get_all(
			"PPD Costing Detail",
			filters={"parent": ppd, "parenttype": "Pertanggungjawaban Perjalanan Dinas"},
			pluck="jumlah_verifikasi_hrd"
		)
		amount = sum(flt(nilai) for nilai in realisasi)

		if amount <= 0:
			continue

		opsi.append(_opsi_uang_muka(
			"Pertanggungjawaban Perjalanan Dinas", ppd, nama, amount, "PPD"
		))

	return opsi


def _uang_muka_employee_advance(nama, employee):
	"""Employee Advance yang sudah disubmit dan belum habis dipakai."""
	opsi = []

	for advance in frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "advance_amount", "claimed_amount", "return_amount"]
	):
		terpakai = flt(advance.claimed_amount) + flt(advance.return_amount)
		if terpakai >= flt(advance.advance_amount):
			continue

		opsi.append(_opsi_uang_muka(
			"Employee Advance", advance.name, nama, advance.advance_amount, "Employee Advance"
		))

	return opsi


def cari_employee(nama):
	"""ID Employee dari isi kolom Pengguna, atau None kalau bukan pegawai.

	Kolom Pengguna di List Bahan Bakar bertipe Data: untuk kategori Tunjangan
	isinya nama pegawai, untuk Biaya Umum / Operasional teks bebas (kendaraan,
	genset, dsb). `penerima` bertipe Link Employee, jadi teks bebas tidak boleh
	dipaksakan ke sana.
	"""
	if not nama:
		return None

	if frappe.db.exists("Employee", nama):
		return nama

	cocok = frappe.get_all("Employee", filters={"employee_name": nama}, pluck="name", limit=2)

	# Nama yang dipakai dua pegawai tidak bisa ditentukan siapa yang dimaksud
	return cocok[0] if len(cocok) == 1 else None


def hitung_plafon_bahan_bakar(source_doc):
	"""[{pengguna, plafon, terpakai, sisa}] dari List Bahan Bakar sebuah PDO.

	Bahan Bakar boleh dicairkan bertahap, jadi patokannya nilai yang sudah ditarik
	ke Payment Entry realisasi — bukan baris PDO mana yang sudah dipakai seperti
	pada tipe Kas.
	"""
	plafon = {}
	urutan = []

	for row in source_doc.pdo_bahan_bakar:
		if not row.employee:
			continue

		if row.employee not in plafon:
			plafon[row.employee] = 0
			urutan.append(row.employee)

		plafon[row.employee] += flt(row.revised_price_total) or flt(row.price_total)

	terpakai = {}
	realisasi = frappe.get_all(
		"Payment Voucher Kas PDO",
		filters={
			"no_pdo": source_doc.name,
			"tipe_pdo": "Bahan Bakar",
			"docstatus": ["<", 2]
		},
		fields=["item_barang", "penerima", "total"]
	)

	for row in realisasi:
		# Baris lama (sebelum ada pilihan pengguna) tidak mengisi item_barang
		kunci = row.item_barang or row.penerima
		if not kunci:
			continue
		terpakai[kunci] = flt(terpakai.get(kunci)) + flt(row.total)

	hasil = []
	for nama in urutan:
		sudah = flt(terpakai.get(nama))

		employee = cari_employee(nama)
		if employee and employee != nama:
			sudah += flt(terpakai.get(employee))

		hasil.append({
			"pengguna": nama,
			"plafon": flt(plafon[nama]),
			"terpakai": sudah,
			"sisa": flt(plafon[nama]) - sudah
		})

	return hasil


@frappe.whitelist()
def get_bahan_bakar_pengguna(source_name):
	"""Pengguna di List Bahan Bakar untuk dialog realisasi.

	Nilai rupiah sengaja tidak ditampilkan di label: nominal Bahan Bakar diisi
	manual saat realisasi, jadi angka plafon di sini cuma jadi acuan yang salah
	dibaca sebagai nilai yang akan dibayar. `amount` tetap dikirim untuk pemakai
	lain dari method ini.
	"""
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)

	daftar = []
	for baris in hitung_plafon_bahan_bakar(source_doc):
		label = baris["pengguna"]
		if baris["sisa"] <= 0:
			label = "{0} ({1})".format(label, _("sudah terpakai semua"))

		daftar.append({
			"value": baris["pengguna"],
			"label": label,
			"amount": baris["sisa"]
		})

	return daftar


@frappe.whitelist()
def get_baris_realisasi(source_name, tipe_pdo, ppd=None, nama_barang=None, pengguna=None, uang_muka=None, pdo_type=None):
	"""Baris realisasi untuk Payment Entry yang sudah tersimpan.

	PE yang belum tersimpan memakai `create_payment_voucher_alokasi` yang membuat
	dokumen baru; yang sudah tersimpan cuma perlu isi tabelnya.
	"""
	source_doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	hasil = build_baris_realisasi(source_doc, tipe_pdo, ppd, nama_barang, pengguna, uang_muka, pdo_type)
	hasil["total"] = flt(sum(flt(row["total"]) for row in hasil["rows"]))
	hasil["mode_of_payment"] = get_mode_of_payment_tunai(source_doc.company)

	return hasil


def get_mode_of_payment_tunai(company=None):
	"""Mode of Payment bertipe Cash untuk realisasi PDO.

	Realisasi PDO selalu dibayar tunai, tapi namanya tidak dipatok "Kas" supaya
	tiap company bebas menamai Mode of Payment-nya. Kalau ada lebih dari satu yang
	bertipe Cash, yang sudah punya akun untuk company ini didahulukan.
	"""
	modes = frappe.get_all(
		"Mode of Payment",
		filters={"type": "Cash", "enabled": 1},
		pluck="name",
		order_by="name",
	)

	if not modes:
		frappe.throw(
			_("Tidak ada Mode of Payment aktif yang bertipe Cash. "
			  "Buat atau aktifkan satu Mode of Payment bertipe Cash dulu."),
			title=_("Mode of Payment Tunai Tidak Ditemukan"),
		)

	if len(modes) > 1 and company:
		punya_akun = set(
			frappe.get_all(
				"Mode of Payment Account",
				filters={"parent": ["in", modes], "company": company},
				pluck="parent",
			)
		)

		for mode in modes:
			if mode in punya_akun:
				return mode

	return modes[0]


def get_akun_mode_of_payment(mode_of_payment, company):
	"""Default Account sebuah Mode of Payment untuk company tertentu."""
	akun = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": mode_of_payment, "company": company},
		"default_account",
	)

	if not akun:
		frappe.throw(
			_("Mode of Payment {0} belum punya Default Account untuk company {1}.").format(
				mode_of_payment, company
			),
			title=_("Akun Mode of Payment Tidak Ditemukan"),
		)

	return akun


@frappe.whitelist()
def create_payment_voucher_alokasi(source_name, tipe_pdo, target_doc=None, ppd=None, nama_barang=None, pengguna=None, uang_muka=None, pdo_type=None):
	"""Create Payment Voucher Kas from Permintaan Dana Operasional

	Bila `ppd` (Pertanggungjawaban Perjalanan Dinas) diisi, nilai tiap baris diambil dari
	realisasi PPD tersebut, bukan dari plafon PDO. Dengan begitu PPD berfungsi sebagai DP
	dan realisasi yang dibayarkan otomatis terpotong.

	Bila `pdo_type` diisi (khusus tipe Kas), hanya baris List Kas dengan PDO Type
	tersebut yang ikut — saringan pertama sebelum `nama_barang`.

	Bila `nama_barang` diisi (khusus tipe Kas), hanya baris List Kas dengan nama barang
	tersebut yang direalisasi, jadi satu baris Payment Entry per nama barang yang
	dicentang, dan rinciannya ditulis ke field Keterangan.

	Bila `pengguna` diisi (khusus tipe Bahan Bakar), satu baris Payment Entry per
	pengguna yang dicentang dengan nominal kosong — diketik manual.
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

		# Satu PPD yang dicentang lewat Uang Muka tetap dicatat di field yang sama,
		# supaya penelusuran dari Payment Entry ke PPD tidak putus
		ppd_terpilih = _ppd_dari_uang_muka(uang_muka)
		if len(ppd_terpilih) == 1:
			target.pertanggungjawaban_perjalanan_dinas = ppd_terpilih[0]

		mode_of_payment = get_mode_of_payment_tunai(source.company)
		target.mode_of_payment = mode_of_payment

		if tipe_pdo == "Kas":
			# Kas keluar dari akun kas Mode of Payment-nya, bukan rekening bank Unit:
			# realisasi Kas dibayar tunai dari kas yang dipegang unit, bukan transfer.
			target.paid_from = get_akun_mode_of_payment(mode_of_payment, source.company)
		else:
			unit_doc = frappe.get_doc("Unit", source.unit)
			if not unit_doc.bank_account:
				frappe.throw(_("Bank Account not set for Unit: {0}").format(source.unit))
			target.paid_from = unit_doc.bank_account

		hasil = build_baris_realisasi(source, tipe_pdo, ppd, nama_barang, pengguna, uang_muka, pdo_type)

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

def _ppd_dari_uang_muka(uang_muka):
	"""Nama-nama PPD di antara centangan uang muka."""
	prefix = "Pertanggungjawaban Perjalanan Dinas" + PEMISAH_UANG_MUKA

	return [
		pilihan[len(prefix):]
		for pilihan in (parse_pilihan(uang_muka) or [])
		if pilihan.startswith(prefix)
	]


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
def get_kas_pdo_type(source_name):
	"""PDO Type di List Kas yang masih punya baris belum direalisasi.

	Dipakai sebagai saringan pertama di dialog realisasi: Jenis-nya (Expense Claim
	Type) baru muncul setelah PDO Type dipilih, karena Jenis yang sama bisa dipakai
	oleh lebih dari satu PDO Type.
	"""
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	sudah_realisasi = get_realisasi_pdo_child_names(source_name, "Kas")

	urutan = []
	for row in doc.pdo_kas:
		if not row.type or row.name in sudah_realisasi:
			continue

		if flt(row.revised_total) or flt(row.total):
			# sub_detail berisi Jenis-nya, PDO Type yang menaunginya dibaca dari sana.
			# Baris tanpa Jenis tetap boleh ada, jadi jangan dibaca kalau kosong.
			pdo_type = row.sub_detail and frappe.get_cached_value(
				"Expense Claim Type", row.sub_detail, "pdo_type"
			)

			nilai = pdo_type or KAS_TANPA_PDO_TYPE
			if nilai not in urutan:
				urutan.append(nilai)

	return [
		{
			"value": nilai,
			"label": _("Tanpa PDO Type") if nilai == KAS_TANPA_PDO_TYPE else nilai
		}
		for nilai in urutan
	]


@frappe.whitelist()
def get_kas_nama_barang(source_name, pdo_type=None):
	"""Jenis di List Kas yang belum direalisasi, disaring per PDO Type.

	Nilai rupiah tidak ikut ditampilkan di label — yang dipilih di sini Jenis-nya,
	nominalnya sudah terbaca di List Kas.
	"""
	doc = frappe.get_doc("Permintaan Dana Operasional", source_name)
	sudah_realisasi = get_realisasi_pdo_child_names(source_name, "Kas")

	rincian = {}
	for row in doc.pdo_kas:
		if not row.type or row.name in sudah_realisasi:
			continue

		if not cocok_pdo_type(row, pdo_type):
			continue

		amount = flt(row.revised_total) or flt(row.total)
		if amount <= 0:
			continue

		rincian[row.type] = flt(rincian.get(row.type)) + amount

	return [
		{
			"value": nama,
			"label": nama,
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
			# Bahan Bakar tanpa nominal: nilainya diisi manual saat realisasi, jadi
			# outstanding di label cuma menyesatkan. Tipe lain tetap menampilkannya.
			label = tipe if tipe == 'Bahan Bakar' else \
				f'{tipe} (Outstanding: {frappe.format_value(outstanding, {"fieldtype": "Currency"})})'

			available_types.append({
				'value': tipe,
				'label': label
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