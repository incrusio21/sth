import frappe
import json

from frappe import _, qb
from frappe.utils import getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_orders_to_be_billed, split_invoices_based_on_payment_terms, get_negative_outstanding_invoices
from erpnext.controllers.accounts_controller import get_supplier_block_status
from erpnext.accounts.utils import get_account_currency, get_outstanding_invoices
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions
from erpnext.accounts.party import get_party_account
from erpnext.setup.utils import get_exchange_rate

from sth.finance_sth.doctype.cheque_number.cheque_number import update_cheque_number_pe
from sth.finance_sth.doctype.cheque_book.cheque_book import update_cheque_book_pe, delete_cheque_history
from sth.finance_sth.doctype.deposito.deposito import update_deposito_payment_entry
from sth.finance_sth.doctype.loan_bank.loan_bank import update_loan_bank_payment_entry
from sth.finance_sth.doctype.dividen.dividen import update_dividen_payment_entry

def cek_kriteria(self,method):
	if self.references:
		for row in self.references:
			doctype = row.reference_doctype
			docname = row.reference_name

			check = 0
			for row in self.detail_dokumen_finance:
				if row.type == doctype and row.name1 == docname:
					check = 1
			
			if check == 1:
				fill_kriteria(self, doctype, docname)

		# bersih-bersih kalau ada yang tidak di reference
		list_type = []
		list_name = []

		for row in self.references:
			list_type.append(row.reference_doctype)
			list_name.append(row.reference_name)

		self.detail_dokumen_finance = [baris for baris in self.detail_dokumen_finance if baris.type in list_type and baris.name1 in list_name]

def fill_kriteria(self,doctype, docname):
	# ambil dulu dari kriteria
	self.detail_dokumen_finance = []
	kriteria = frappe.db.sql(""" SELECT name FROM `tabKriteria Dokumen Finance` WHERE name = "{}" """.format(doctype))
	if len(kriteria) > 0:
		kriteria_doc = frappe.get_doc("Kriteria Dokumen Finance",kriteria[0][0])
		for row in kriteria_doc.kriteria_dokumen_finance:
			if row.aktif == 1:
				self.append("detail_dokumen_finance",{
					"rincian_dokumen_finance": row.rincian_dokumen_finance,
					"type": doctype,
					"name1": docname
				})

		

def update_check_book(self, method):
	if self.mode_of_payment != "Cheque" and not self.custom_cheque_number:
		return
	if method == "on_trash":
		delete_cheque_history(self.custom_cheque_number)
		return

	status = {
		"on_submit": "Used",
		"on_cancel": "Void"
	}
	data = frappe._dict({
		"reference_doc": self.doctype,
		"reference_name": self.name,
		"status": status.get(method, "Draft"),
		"cheque_amount": self.paid_amount,
		"issue_date": self.posting_date,
		"note": self.remarks,
		"upload_cheque_book": self.upload_cheque_book
	})
	
	cheque_number = update_cheque_number_pe(self.custom_cheque_number, data)
	update_cheque_book_pe(cheque_number)


def update_status_deposito(self, method):
	update_deposito_payment_entry(self, method)

def update_status_loan_bank(self, method):
	update_loan_bank_payment_entry(self, method)

def update_status_dividen(self, method):
	update_dividen_payment_entry(self, method)
	

@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	if isinstance(args, str):
		args = json.loads(args)

	if args.get("party_type") == "Member":
		return

	if not args.get("get_outstanding_invoices") and not args.get("get_orders_to_be_billed"):
		args["get_outstanding_invoices"] = True

	ple = qb.DocType("Payment Ledger Entry")
	common_filter = []
	accounting_dimensions_filter = []
	posting_and_due_date = []

	# confirm that Supplier is not blocked
	if args.get("party_type") == "Supplier":
		supplier_status = get_supplier_block_status(args["party"])
		if supplier_status["on_hold"]:
			if supplier_status["hold_type"] == "All":
				return []
			elif supplier_status["hold_type"] == "Payments":
				if (
					not supplier_status["release_date"]
					or getdate(nowdate()) <= supplier_status["release_date"]
				):
					return []

	party_account_currency = get_account_currency(args.get("party_account"))
	company_currency = frappe.get_cached_value("Company", args.get("company"), "default_currency")

	# Get positive outstanding sales /purchase invoices
	condition = ""
	if args.get("voucher_type") and args.get("voucher_no"):
		condition = " and voucher_type={} and voucher_no={}".format(
			frappe.db.escape(args["voucher_type"]), frappe.db.escape(args["voucher_no"])
		)
		common_filter.append(ple.voucher_type == args["voucher_type"])
		common_filter.append(ple.voucher_no == args["voucher_no"])

	# Add cost center condition
	if args.get("cost_center"):
		condition += " and cost_center='%s'" % args.get("cost_center")
		accounting_dimensions_filter.append(ple.cost_center == args.get("cost_center"))

	# dynamic dimension filters
	active_dimensions = get_dimensions()[0]
	for dim in active_dimensions:
		if args.get(dim.fieldname):
			condition += f" and {dim.fieldname}='{args.get(dim.fieldname)}'"
			accounting_dimensions_filter.append(ple[dim.fieldname] == args.get(dim.fieldname))

	date_fields_dict = {
		"posting_date": ["from_posting_date", "to_posting_date"],
		"due_date": ["from_due_date", "to_due_date"],
	}

	for fieldname, date_fields in date_fields_dict.items():
		if args.get(date_fields[0]) and args.get(date_fields[1]):
			condition += " and {} between '{}' and '{}'".format(
				fieldname, args.get(date_fields[0]), args.get(date_fields[1])
			)
			posting_and_due_date.append(ple[fieldname][args.get(date_fields[0]) : args.get(date_fields[1])])
		elif args.get(date_fields[0]):
			# if only from date is supplied
			condition += f" and {fieldname} >= '{args.get(date_fields[0])}'"
			posting_and_due_date.append(ple[fieldname].gte(args.get(date_fields[0])))
		elif args.get(date_fields[1]):
			# if only to date is supplied
			condition += f" and {fieldname} <= '{args.get(date_fields[1])}'"
			posting_and_due_date.append(ple[fieldname].lte(args.get(date_fields[1])))

	if args.get("company"):
		condition += " and company = {}".format(frappe.db.escape(args.get("company")))
		common_filter.append(ple.company == args.get("company"))

	outstanding_invoices = []
	negative_outstanding_invoices = []

	party_account = args.get("party_account")

	# get party account if advance account is set.
	if args.get("book_advance_payments_in_separate_party_account"):
		accounts = get_party_account(
			args.get("party_type"), args.get("party"), args.get("company"), include_advance=True
		)
		advance_account = accounts[1] if len(accounts) > 1 else None

		if party_account == advance_account:
			party_account = accounts[0]

	if args.get("get_outstanding_invoices"):
		outstanding_invoices = get_outstanding_invoices(
			args.get("party_type"),
			args.get("party"),
			[party_account],
			common_filter=common_filter,
			posting_date=posting_and_due_date,
			min_outstanding=args.get("outstanding_amt_greater_than"),
			max_outstanding=args.get("outstanding_amt_less_than"),
			accounting_dimensions=accounting_dimensions_filter,
			vouchers=args.get("vouchers") or None,
		)

		outstanding_invoices = split_invoices_based_on_payment_terms(
			outstanding_invoices, args.get("company")
		)

		for d in outstanding_invoices:
			d["exchange_rate"] = 1
			if party_account_currency != company_currency:
				if d.voucher_type in frappe.get_hooks("invoice_doctypes"):
					d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
				elif d.voucher_type == "Journal Entry":
					d["exchange_rate"] = get_exchange_rate(
						party_account_currency, company_currency, d.posting_date
					)
			if d.voucher_type in ("Purchase Invoice"):
				d["bill_no"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "bill_no")

		# Get negative outstanding sales /purchase invoices
		if args.get("party_type") != "Employee":
			negative_outstanding_invoices = get_negative_outstanding_invoices(
				args.get("party_type"),
				args.get("party"),
				args.get("party_account"),
				party_account_currency,
				company_currency,
				condition=condition,
			)

	# Get all SO / PO which are not fully billed or against which full advance not paid
	orders_to_be_billed = []
	if args.get("get_orders_to_be_billed"):
		orders_to_be_billed = get_orders_to_be_billed(
			args.get("posting_date"),
			args.get("party_type"),
			args.get("party"),
			args.get("company"),
			party_account_currency,
			company_currency,
			filters=args,
		)

	data = negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed

	if not data:
		if args.get("get_outstanding_invoices") and args.get("get_orders_to_be_billed"):
			ref_document_type = "invoices or orders"
		elif args.get("get_outstanding_invoices"):
			ref_document_type = "invoices"
		elif args.get("get_orders_to_be_billed"):
			ref_document_type = "orders"

		if not validate:
			frappe.msgprint(
				_(
					"No outstanding {0} found for the {1} {2} which qualify the filters you have specified."
				).format(
					_(ref_document_type), _(args.get("party_type")).lower(), frappe.bold(args.get("party"))
				)
			)

	for i, row in enumerate(data):
		unit_trans = frappe.db.get_value(row.voucher_type, row.voucher_no, "unit")
		if not unit_trans or unit_trans != args.get("unit"):
			del data[i]

	return data

def payment_entry_notification(doc, method):

	for ref in doc.references:

		if not ref.reference_doctype or not ref.reference_name:
			continue

		owner = frappe.db.get_value(
			ref.reference_doctype,
			ref.reference_name,
			"owner"
		)

		if not owner:
			continue

		notification = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"{ref.reference_doctype} {ref.reference_name} telah dibayarkan melalui {doc.name}",
			"for_user": owner,
			"type": "Alert",
			"document_type": ref.reference_doctype,
			"document_name": ref.reference_name
		}).insert(ignore_permissions=True)

		notification.notify_update()

		frappe.publish_realtime(
			event="notification",
			message={"type": "Alert"},
			user=owner
		)


def check_payment_notification(doc, method):

	print("=== CHECK PAYMENT NOTIFICATION ===")
	print("DocType:", doc.doctype)
	print("DocName:", doc.name)

	settings = frappe.get_all(
		"Payment Notification Settings",
		filters={"document_name": doc.doctype},
		pluck="name"
	)

	print("Settings ditemukan:", settings)

	if not settings:
		print("STOP: Tidak ada setting")
		return

	meta = frappe.get_meta(doc.doctype)

	print("Cek field outstanding_amount")

	if not meta.has_field("outstanding_amount"):
		print("STOP: Tidak ada field outstanding_amount di doctype")
		return

	outstanding = doc.get("outstanding_amount")

	print("Outstanding Amount:", outstanding)

	if not outstanding or outstanding <= 0:
		print("STOP: Outstanding kosong atau <= 0")
		return

	roles = frappe.get_all(
		"Payment Notification Roles",
		filters={"parent": ["in", settings]},
		pluck="role"
	)

	print("Roles ditemukan:", roles)

	if not roles:
		print("STOP: Tidak ada role")
		return

	users = frappe.get_all(
		"Has Role",
		filters={
			"role": ["in", roles],
			"parenttype": "User"
		},
		pluck="parent"
	)

	print("Users dari role:", users)

	if not users:
		print("STOP: Tidak ada user")
		return

	users = list(set(users))

	print("Users final:", users)

	for user in users:

		enabled = frappe.db.get_value("User", user, "enabled")

		print(f"User {user} enabled:", enabled)

		if not enabled:
			continue

		exists = frappe.db.exists(
			"Notification Log",
			{
				"for_user": user,
				"document_type": doc.doctype,
				"document_name": doc.name
			}
		)

		if exists:
			print("Notif sudah ada untuk:", user)
			continue

		print("Membuat notification untuk:", user)

		notification = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": f"{doc.doctype} {doc.name} memiliki outstanding belum di bayar",
			"for_user": user,
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name
		}).insert(ignore_permissions=True)

		print("Notification dibuat:", notification.name)

		notification.notify_update()

		frappe.publish_realtime(
			event="notification",
			message={"type": "Alert"},
			user=user
		)



def test_check_payment_notification():
	pass
	# doc = frappe.get_doc("Purchase Invoice", "ACC-PINV-2026-00040")

	# check_payment_notification(doc, "on_submit")

	# print("TEST SELESAI")

def update_pesangon_from_payment(doc, method):

	if doc.tipe_transfer != "Salary Slip":
		return

	for row in doc.payment_voucher_salary_slip:
		slip_name = row.salary_slip
		slip = frappe.get_doc("Salary Slip", slip_name)

		if slip.tipe_salary != "Pesangon" or not slip.pesangon_doc:
			continue

		slip.update_pesangon_payment_status()

def pasang_nota_piutang(doc, method):
	if doc.get("nota_piutang_pemenuhan_kontrak"):
		nota_piutang = doc.nota_piutang_pemenuhan_kontrak

		# Ambil semua Payment Entry yang sudah submit dan terhubung ke nota yang sama
		payment_entries = frappe.get_all(
			"Payment Entry",
			filters={
				"nota_piutang_pemenuhan_kontrak": nota_piutang,
				"docstatus": 1  # submitted
			},
			fields=["name"]
		)

		# Ambil dokumen Nota Piutang
		nota_doc = frappe.get_doc("Nota Piutang", nota_piutang)

		# Kosongkan dulu list_payment_voucher sebelum diisi ulang
		nota_doc.set("list_payment_voucher", [])

		# Tambahkan setiap Payment Entry ke child table
		for pe in payment_entries:
			nota_doc.append("list_payment_voucher", {
				"payment_voucher": pe["name"]
			})

		nota_doc.save(ignore_permissions=True)
	
def buat_nota_piutang(doc, method):
	if doc.get("apakah_dp_kontrak") == 1 and doc.get("no_kontrak_penjualan"):
		if doc.payment_type != "Receive":
			return

		if not doc.no_kontrak_penjualan:
			return

		if doc.reference_no and frappe.db.exists("Nota Piutang", doc.reference_no):
			return

		# Cegah duplikat
		existing = frappe.db.exists("Nota Piutang", {"payment_entry": doc.name})

		ppn_total = sum(abs(d.amount) for d in doc.get("deductions") or [])
		nilai_dp  = doc.paid_amount - ppn_total

		np = frappe.new_doc("Nota Piutang")
		np.tipe           = "Nota DP"
		np.date           = doc.posting_date
		np.no_kontrak     = doc.no_kontrak_penjualan
		np.company        = doc.company
		np.akun_uang_muka = doc.paid_from
		np.akun_kas_bank  = doc.paid_to
		np.nilai_dp       = nilai_dp
		np.payment_entry  = doc.name
		np.dibuat_dari_payment_voucher = 1

		np.insert(ignore_permissions=True)
		np.submit()

	
		
def set_no_rekening(doc, method):

	bank_account = frappe.db.get_value(
		"Bank Account",
		{
			"account": doc.paid_from
		},
		["bank_account_no", "bank"],
		as_dict=True
	)

	if bank_account:
		doc.no_rekening_asal = (
			bank_account.bank_account_no
		)

	result = get_no_rekening(
		party_type=doc.party_type,
		party=doc.party,
		paid_to=doc.paid_to,
		tipe_transfer=doc.tipe_transfer,
		permintaan_dana_operasional=doc.permintaan_dana_operasional,
		payment_type=doc.payment_type
	)

	doc.no_rekening = None
	doc.nama_bank = None

	# special handling internal employee
	if (
		doc.party_type == "Employee"
		and doc.internal_employee
	):

		reference = None

		if doc.references:
			reference = doc.references[0]

		if (
			reference
			and reference.reference_doctype
			and reference.reference_name
		):

			no_rekening_tujuan = ""

			if frappe.get_meta(reference.reference_doctype).has_field("no_rekening_tujuan"):
				no_rekening_tujuan = frappe.db.get_value(
					reference.reference_doctype,
					reference.reference_name,
					"no_rekening_tujuan"
				) or ""

			if no_rekening_tujuan:

				bank_account = frappe.db.get_value(
					"Bank Account",
					no_rekening_tujuan,
					[
						"bank_account_no",
						"bank"
					],
					as_dict=True
				)

				if bank_account:

					doc.no_rekening_tujuan = (
						bank_account.bank_account_no
					)

					doc.bank_tujuan = (
						bank_account.bank
					)

				if not doc.bill_no: 
					doc.bill_no = (
						no_rekening_tujuan
					)

	else:

		if result.get("no_rekening"):
			doc.no_rekening = (
				result["no_rekening"]
			)

		if result.get("nama_bank"):
			doc.nama_bank = (
				result["nama_bank"]
			)

	if result.get("no_rekening_tujuan"):
		doc.no_rekening_tujuan = (
			result["no_rekening_tujuan"]
		)

		if not doc.bill_no: 
			doc.bill_no = (
				result["no_rekening_tujuan"]
			)

	if result.get("bank_tujuan"):
		doc.bank_tujuan = (
			result["bank_tujuan"]
		)

	doc.beneficary_account = (doc.no_rekening) or (doc.no_rekening_tujuan)

	doc.beneficary_bank = (doc.nama_bank) or (doc.bank_tujuan)

@frappe.whitelist()
def get_no_rekening(party_type=None, party=None, 
					paid_to=None, tipe_transfer=None, 
					permintaan_dana_operasional=None, payment_type=None):

	result = {
		"no_rekening": None,
		"nama_bank": None,
		"no_rekening_tujuan": None,
		"bank_tujuan": None
	}

	if (
		payment_type == "Internal Transfer"
		and tipe_transfer == "PDO"
		and permintaan_dana_operasional
	):

		unit = frappe.db.get_value(
			"Permintaan Dana Operasional",
			permintaan_dana_operasional,
			"unit"
		)

		if unit:

			default_bank_account = frappe.db.get_value(
				"Unit",
				unit,
				"default_bank_account"
			)

			if default_bank_account:

				bank_account = frappe.db.get_value(
					"Bank Account",
					default_bank_account,
					["bank_account_no", "bank"],
					as_dict=True
				)

				if bank_account:

					result["no_rekening_tujuan"] = (
						bank_account.bank_account_no
					)

					result["bank_tujuan"] = (
						bank_account.bank
					)

	elif paid_to:

		bank_account = frappe.db.get_value(
			"Bank Account",
			{
				"account": paid_to
			},
			["bank_account_no", "bank"],
			as_dict=True
		)

		if bank_account:

			result["no_rekening_tujuan"] = (
				bank_account.bank_account_no
			)

			result["bank_tujuan"] = (
				bank_account.bank
			)

	if party_type and party:

		if party_type == "Employee":

			employee = frappe.db.get_value(
				"Employee",
				party,
				["bank_ac_no", "nama_bank"],
				as_dict=True
			)

			if employee:

				result["no_rekening"] = (
					employee.bank_ac_no
				)

				result["nama_bank"] = (
					employee.nama_bank
				)

		elif party_type == "Supplier":

			supplier_bank = frappe.db.get_value(
				"Data Bank Supplier",
				{
					"parent": party,
					"status_bank": "Aktif"
				},
				["no_rekening", "nama_bank"],
				as_dict=True
			)

			if supplier_bank:

				result["no_rekening"] = (
					supplier_bank.no_rekening
				)

				result["nama_bank"] = (
					supplier_bank.nama_bank
				)

	return result

def validate_payment_voucher_kas_pdo(doc, method=None):

	TABLE_TOTAL_FIELDS = {
		"pdo_bahan_bakar": {
			"revised": "revised_price_total",
			"normal": "price_total"
		},
		"pdo_perjalanan_dinas": {
			"revised": "revised_total",
			"normal": "total"
		},
		"pdo_kas": {
			"revised": "revised_total",
			"normal": "total"
		}
	}

	for row in doc.payment_voucher_kas_pdo:
		if row.tipe_pdo.lower() != "dana cadangan":
			no_pdo = row.no_pdo
			tipe_pdo = row.tipe_pdo
			penerima = row.penerima

			# Ambil nama table dari tipe_pdo
			# Contoh: "Bahan Bakar" -> "pdo_bahan_bakar"
			table_name = "pdo_" + tipe_pdo.lower().replace(" ", "_")

			# Ambil total harga dari PDO untuk penerima ini
			pdo_doc = frappe.get_doc("Permintaan Dana Operasional", no_pdo)
			
			table_name = "pdo_" + tipe_pdo.lower().replace(" ", "_")

			# Ambil field names untuk table ini
			field_config = TABLE_TOTAL_FIELDS.get(table_name)
			if not field_config:
				frappe.throw(f"Tipe PDO <b>{tipe_pdo}</b> tidak dikenali.")

			revised_field = field_config["revised"]
			normal_field = field_config["normal"]

			total_harga_pdo = 0
			for pdo_row in pdo_doc.get(table_name):
				if pdo_row.employee == penerima:
					total_harga_pdo += (
						getattr(pdo_row, revised_field) or getattr(pdo_row, normal_field) or 0
					)

			# if total_harga_pdo == 0:
			# 	frappe.throw(
			# 		f"Penerima <b>{penerima}</b> tidak ditemukan di tabel <b>{table_name}</b> "
			# 		f"pada PDO <b>{no_pdo}</b>."
			# 	)

			# Hitung total Payment Entry yang sudah ada (diluar doc ini)
			existing_entries = frappe.db.sql("""
				SELECT SUM(pe.paid_amount) as total_dibayar
				FROM `tabPayment Entry` pe
				INNER JOIN `tabPayment Voucher Kas PDO` pvkp ON pvkp.parent = pe.name
				WHERE pvkp.no_pdo = %s
				  AND pvkp.tipe_pdo = %s
				  AND pvkp.penerima = %s
				  AND pe.docstatus = 1
				  AND pe.name != %s
			""", (no_pdo, tipe_pdo, penerima, doc.name), as_dict=True)

			total_sudah_dibayar = existing_entries[0].total_dibayar or 0

			# Tambah total dari doc saat ini (semua row yang cocok)
			total_doc_ini = doc.paid_amount

			total_keseluruhan = total_sudah_dibayar + total_doc_ini

			if total_keseluruhan > total_harga_pdo:
				frappe.msgprint(
					f"Total pembayaran untuk penerima <b>{penerima}</b> "
					f"pada PDO <b>{no_pdo}</b> ({tipe_pdo}) "
					f"melebihi batas yang ditentukan.<br>"
					f"Total PDO: <b>Rp {frappe.format(total_harga_pdo, 'Currency')}</b><br>"
					f"Sudah dibayar: <b>Rp {frappe.format(total_sudah_dibayar, 'Currency')}</b><br>"
					f"Akan dibayar sekarang: <b>Rp {frappe.format(total_doc_ini, 'Currency')}</b><br>"
					f"Akan masuk ke non PDO sejumlah: <b>Rp {frappe.format(total_sudah_dibayar + total_doc_ini - total_harga_pdo, 'Currency')}</b><br>"

				)

def update_payment_voucher_ppd(doc, method=None):
	if not doc.references:
		return

	for ref in doc.references:
		if ref.reference_doctype == "Pertanggungjawaban Perjalanan Dinas":
			try:
				frappe.db.set_value(
						"Pertanggungjawaban Perjalanan Dinas",
						ref.reference_name,
						"payment_voucher",
						doc.name
				)

				frappe.msgprint(f"Updated PPD: {ref.reference_name}")

			except Exception as e:
				frappe.log_error(
					f"Gagal update PPD {ref.reference_name}: {str(e)}",
					"Update Payment Voucher PPD"
				)


@frappe.whitelist()
def is_mandiri_kcm(account):

	if not account:
		return False

	bank = frappe.db.get_value(
		"Bank Account",
		{
			"account": account
		},
		"bank"
	)

	if not bank:
		return False

	return bool(
		frappe.db.get_value(
			"Bank",
			bank,
			"is_mandiri_kca"
		)
	)


@frappe.whitelist()
def update_payment_reference(
	payment_entry,
	nomor_referensi_bayar,
	tanggal_bayar,
	bukti_pembayaran=None
):

	doc = frappe.get_doc(
		"Payment Entry",
		payment_entry
	)


	# allow update submitted document
	if doc.docstatus == 1:
		doc.flags.ignore_validate_update_after_submit = True


	doc.nomor_referensi_bayar = nomor_referensi_bayar
	doc.tanggal_bayar = tanggal_bayar


	if bukti_pembayaran:
		doc.bukti_pembayaran = bukti_pembayaran


	doc.save()


	return {
		"name": doc.name,
		"status": "updated"
	}


def set_reference_no(doc, method):

	if doc.docstatus < 1:
		if ((not doc.reference_no) or (doc.reference_no=="-")) :
			doc.reference_no = doc.name
			