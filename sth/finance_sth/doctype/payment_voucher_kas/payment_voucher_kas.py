# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from sth.controllers.accounts_controller import AccountsController
from frappe.model.mapper import get_mapped_doc
from frappe import _
from frappe.utils import flt, getdate, nowdate

class PaymentVoucherKas(AccountsController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._expense_account = "account"
		
	def validate(self):
		if self.transaction_type == "Masuk":
			self._party_type = "Customer"
			self._expense_account = "account"
			self._party_account_field = "debit_to"
			self.customer = frappe.db.get_single_value("Payment Settings", "receivable_customer")
			self.payment_term = None
		else:
			self.set_missing_value()

		total=0
		for row in self.payment_voucher_kas_pdo:
			total = total + row.total

		self.payment_amount = total
		self.grand_total = self.payment_amount
		self.outstanding_amount = self.payment_amount

	def on_submit(self):

		self.make_gl_entry()
		if len(self.payment_voucher_kas_pdo) == 0:
			self.make_payment_entry()

		else:
			self.update_pdo_outstanding()
			self.update_pdo_non_pdo_table()
			self.check_plafon_and_split_excess()

	def check_plafon_and_split_excess(self):
		current_date = getdate(self.posting_date if hasattr(self, 'posting_date') else nowdate())
		current_month = current_date.month
		current_year = current_date.year
		unit = self.unit if hasattr(self, 'unit') else None
		pdo_groups = {}

		for row in self.get('payment_voucher_kas_pdo', []):
			no_pdo = row.no_pdo if hasattr(row, 'no_pdo') else None
			
			if not no_pdo:
				continue
			
			if not row.penerima:
				continue
			
			try:
				employee_doc = frappe.get_doc('Employee', row.penerima)
				designation = employee_doc.designation
			except:
				continue
			
			if not designation:
				continue
			
			plafon_info = self.get_plafon_for_designation(designation)
			
			print(plafon_info)
			if not plafon_info:
				continue
			
			plafon_amount = flt(plafon_info.get('nilai', 0))
			
			if plafon_amount <= 0:
				continue
			
			total_used = self.calculate_total_usage(
				designation=designation,
				unit=unit,
				month=current_month,
				year=current_year,
				exclude_realisasi=self.name
			)
			


			current_amount = flt(row.total)
			new_total = total_used + current_amount
			
			if new_total > plafon_amount:
				excess_amount = new_total - plafon_amount
				allowed_amount = current_amount - excess_amount
				
				if allowed_amount < 0:
					allowed_amount = 0
					excess_amount = current_amount
				
				if allowed_amount > 0:
					row.total = allowed_amount
					if hasattr(row, 'amount'):
						row.amount = allowed_amount
				else:
					row.total = 0
					if hasattr(row, 'amount'):
						row.amount = 0
				
				if no_pdo not in pdo_groups:
					pdo_groups[no_pdo] = []
				
				pdo_groups[no_pdo].append({
					'employee': row.penerima,
					'jabatan': designation,
					'debit_to': row.debit_to,
					'amount': excess_amount,
				})

				frappe.msgprint(
					msg=f'Employee {row.penerima} ({designation}) exceeded plafon by {excess_amount}. '
						f'Moved to Non-PDO table in {no_pdo}.',
					title='Plafon Exceeded',
					indicator='orange'
				)

		for no_pdo, excess_items in pdo_groups.items():
			try:
				pdo_doc = frappe.get_doc('Permintaan Dana Operasional', no_pdo)
				
				for item in excess_items:
					self.add_to_non_pdo(
						pdo_doc=pdo_doc,
						employee=item['employee'],
						jabatan=item['jabatan'],
						debit_to=item['debit_to'],
						amount=item['amount']
					)
				
				# Save the PDO document once after all additions
				pdo_doc.flags.ignore_permissions = True
				pdo_doc.flags.ignore_validate = True
				pdo_doc.save()
				
			except frappe.DoesNotExistError:
				frappe.msgprint(
					msg=f'Permintaan Dana Operasional {no_pdo} not found',
					title='Error',
					indicator='red'
				)

	def get_plafon_for_designation(self, designation):
		try:
			plafon_pdo = frappe.get_doc('Plafon PDO', 'UANG PEMBANTU')
		except:
			return None
		
		for plafon_row in plafon_pdo.get('plafon_pdo_table', []):
			
			if plafon_row.jenis_plafon == designation and plafon_row.tipe == "Designation":
				return {
					'nilai': plafon_row.nilai,
					'jenis_plafon': plafon_row.get('jenis_plafon'),
				}
		
		return None
	
	def calculate_total_usage(self, designation, unit, month, year, exclude_realisasi=None):
		"""
		Calculate total usage for a designation in a specific unit and month
		"""
		# Build filters
		filters = {
			'docstatus': ['in', [0, 1]],  # Draft and Submitted
		}
		
		if exclude_realisasi:
			filters['name'] = ['!=', exclude_realisasi]
		
		# Get all Realisasi PDO for the month
		realisasi_list = frappe.get_all(
			'Payment Voucher Kas',
			filters=filters,
			fields=['name', 'posting_date', 'unit'] if hasattr(self, 'unit') else ['name', 'posting_date']
		)
		
		total = 0
		
		for realisasi in realisasi_list:
			# Check if same month and year
			r_date = getdate(realisasi.posting_date)
			if r_date.month != month or r_date.year != year:
				continue
			
			# Check if same unit (if unit filtering is needed)
			if unit and hasattr(realisasi, 'unit') and realisasi.unit != unit:
				continue
			
			# Get child table entries
			child_entries = frappe.get_all(
				'Payment Voucher Kas PDO',  # Child table doctype name
				filters={
					'parent': realisasi.name,
					'parenttype': 'Realisasi PDO'
				},
				fields=['penerima', 'total']
			)
			
			for entry in child_entries:
				if not entry.penerima:
					continue
				
				# Get employee designation
				try:
					emp = frappe.get_doc('Employee', entry.penerima)
					if emp.designation == designation:
						total += flt(entry.total)
				except:
					continue
		
		return total
	
	def add_to_non_pdo(self, pdo_doc, employee, jabatan, debit_to, amount, reason=None):
		"""
		Add entry to pdo_non_pdo table in Permintaan Dana Operasional
		"""
		# Check if similar entry already exists
		existing = False
		for pdo_row in pdo_doc.get('pdo_non_pdo', []):
			if (pdo_row.employee == employee and 
				pdo_row.debit_to == debit_to and 
				abs(flt(pdo_row.total) - flt(amount)) < 0.01):  # Allow small rounding differences
				existing = True
				break
		
		if not existing:
			new_row = pdo_doc.append('pdo_non_pdo', {
				'employee': employee,
				'jabatan': jabatan,
				'debit_to': debit_to,
				'price': amount,
				'qty': 1,
				'total': amount,

				'revised_qty': 1,
				'revised_price': amount,
				'revised_total': amount

			})
			
			# Add remark if field exists
			if reason and hasattr(new_row, 'remarks'):
				new_row.remarks = reason
			elif reason and hasattr(new_row, 'remark'):
				new_row.remark = reason
	
	def update_pdo_non_pdo_table(self):
		"""
		Add rows without pdo_child_name to pdo_non_pdo table
		Loop through each row and add to respective PDO
		"""
		# Group rows by no_pdo
		pdo_groups = {}
		
		for row in self.get('payment_voucher_kas_pdo', []):
			# Skip rows that already have pdo_child_name
			if row.pdo_child_name:
				continue
			
			# Get no_pdo from the row
			no_pdo = row.no_pdo if hasattr(row, 'no_pdo') else None
			
			if not no_pdo:
				continue
			
			if no_pdo not in pdo_groups:
				pdo_groups[no_pdo] = []
			
			pdo_groups[no_pdo].append(row)
		
		# Process each PDO group
		for no_pdo, rows in pdo_groups.items():
			try:
				pdo_doc = frappe.get_doc('Permintaan Dana Operasional', no_pdo)
				
				for row in rows:
					# Get employee details
					jabatan = None
					if row.penerima:
						try:
							employee_doc = frappe.get_doc('Employee', row.penerima)
							jabatan = employee_doc.designation
						except:
							pass
					
					self.add_to_non_pdo(
						pdo_doc=pdo_doc,
						employee=row.penerima,
						jabatan=jabatan,
						debit_to=row.debit_to,
						amount=row.total
					)
				
				# Save the PDO document once after all additions
				pdo_doc.flags.ignore_permissions = True
				pdo_doc.flags.ignore_validate = True
				pdo_doc.save()
				
				frappe.msgprint(
					msg=f'Successfully added {len(rows)} non-PDO entries to {no_pdo}',
					title='PDO Updated',
					indicator='green'
				)
				
			except frappe.DoesNotExistError:
				frappe.msgprint(
					msg=f'Permintaan Dana Operasional {no_pdo} not found',
					title='Error',
					indicator='red'
				)
				

	def update_pdo_non_pdo_table(self):

		new_rows = []
		for row in self.get('payment_voucher_kas_pdo', []):
			if not row.pdo_child_name:
				new_rows.append(row)
		
		if not new_rows:
			return
			
		for row in new_rows:

			pdo_doc = frappe.get_doc('Permintaan Dana Operasional', row.no_pdo)
			employee_doc = frappe.get_doc('Employee', row.penerima) if row.penerima else None
			jabatan = employee_doc.designation if employee_doc else None
			
			existing = False
			for pdo_row in pdo_doc.get('pdo_non_pdo', []):
				if (pdo_row.employee == row.penerima and 
					pdo_row.debit_to == row.debit_to and 
					pdo_row.total == row.total):
					existing = True
					break
			
			if not existing:
				pdo_doc.append('pdo_non_pdo', {
					'employee': row.penerima,
					'jabatan': jabatan,
					'debit_to': row.debit_to,
					'price': row.total,
					'qty': 1,
					'total': row.total,
					'revised_qty': 1,
					'revised_price': row.total,
					'revised_total': row.total

				})
		
			pdo_doc.flags.ignore_permissions = True
			pdo_doc.save()
		
			frappe.msgprint(
				msg=f'Successfully added {len(new_rows)} non-PDO entries to {row.no_pdo}',
				title='PDO Updated',
				indicator='green'
			)
	def on_cancel(self):
		super().on_cancel()
		self.make_gl_entry()
		if len(self.payment_voucher_kas_pdo) > 0:
			self.restore_pdo_outstanding()

	def make_payment_entry(self):
		account_type = "debit_to" if self.transaction_type == "Masuk" else "credit_to"
		paid_type = "paid_from" if self.transaction_type == "Masuk" else "paid_to"
		
		def post_process(source, target):
			party_type = "Customer" if self.transaction_type == "Masuk" else "Employee"
			payment_type = "Receive" if self.transaction_type == "Masuk" else "Pay"
			field_default_party_type = "receivable_customer" if party_type == "Customer" else "internal_employee"
			default_party = frappe.db.get_single_value("Payment Settings", field_default_party_type)
			field_party_name = "customer_name" if party_type == "Customer" else "employee_name"

			party_name = frappe.db.get_value(party_type, default_party, field_party_name)
			company = frappe.db.get_value("Company", source.company, "*")
			account_currency = frappe.db.get_value("Account", source.debit_to, "account_currency")
			mode_of_payment = frappe.db.get_value("Mode of Payment Account", {"parent": "Cash", "company": self.company}, "*")
			
			target.payment_type = payment_type
			target.party_type = party_type
			target.party = default_party
			target.party_name = party_name
			target.paid_amount = source.outstanding_amount
			target.received_amount = source.outstanding_amount
			target.paid_from_account_currency = account_currency
			target.paid_to_account_currency = company.default_currency
			target.internal_employee = 1 if party_type == "Employee" else 0
			target.paid_from = source.debit_to if party_type == "Customer" else mode_of_payment.default_account
			target.paid_to = source.credit_to if party_type == "Employee" else mode_of_payment.default_account
			target.cost_center = company.cost_center

			target.append("references", {
				"reference_doctype": "Payment Voucher Kas",
				"reference_name": source.name,
				"total_amount": source.outstanding_amount,
				"outstanding_amount": source.outstanding_amount,
				"allocated_amount": source.outstanding_amount,
			})

		doclist = get_mapped_doc(
			"Payment Voucher Kas",
			self.name,
			{
				"Payment Voucher Kas": {
					"doctype": "Payment Entry",
				}
			},
			None,
			post_process,
		)
		doclist.save()
		doclist.submit()

	@frappe.whitelist()
	def set_exchange_rate(self):
		currency_exchange = frappe.db.get_all("Currency Exchange", filters={
			"from_currency": self.currency,
			"to_currency": "IDR"
		}, order_by="date DESC",page_length=1, fields=["exchange_rate"])
		if not currency_exchange:
			return
		self.exchange_rate = currency_exchange[0].exchange_rate

	def update_pdo_outstanding(self):
		"""Deduct paid amount from PDO outstanding"""
		if not self.payment_voucher_kas_pdo:
			return
		
		# Group by PDO and tipe
		pdo_payments = {}
		for row in self.payment_voucher_kas_pdo:
			key = (row.no_pdo, row.tipe_pdo)
			if key not in pdo_payments:
				pdo_payments[key] = 0
			pdo_payments[key] += row.total or 0
		
		# Update each PDO
		for (pdo_name, tipe_pdo), total_paid in pdo_payments.items():
			self.update_outstanding_amount(pdo_name, tipe_pdo, total_paid, operation='subtract')
	
	def restore_pdo_outstanding(self):
		"""Add back paid amount to PDO outstanding when cancelled"""
		if not self.payment_voucher_kas_pdo:
			return
		
		# Group by PDO and tipe
		pdo_payments = {}
		for row in self.payment_voucher_kas_pdo:
			key = (row.no_pdo, row.tipe_pdo)
			if key not in pdo_payments:
				pdo_payments[key] = 0
			pdo_payments[key] += row.total or 0
		
		# Restore each PDO
		for (pdo_name, tipe_pdo), total_paid in pdo_payments.items():
			self.update_outstanding_amount(pdo_name, tipe_pdo, total_paid, operation='add')
	
	def update_outstanding_amount(self, pdo_name, tipe_pdo, amount, operation='subtract'):
		"""Update outstanding amount for specific tipe in PDO"""
		
		tipe_mapping = {
			'Bahan Bakar': 'outstanding_amount_bahan_bakar',
			'Perjalanan Dinas': 'outstanding_amount_perjalanan_dinas',
			'Kas': 'outstanding_amount_kas',
			'Dana Cadangan': 'outstanding_amount_dana_cadangan'
		}
		
		if tipe_pdo not in tipe_mapping:
			frappe.log_error(f"Unknown tipe_pdo: {tipe_pdo}", "Payment Voucher Kas Outstanding Update")
			return
		
		outstanding_field = tipe_mapping[tipe_pdo]
		
		try:
			pdo = frappe.get_doc("Permintaan Dana Operasional", pdo_name)
			current_outstanding = getattr(pdo, outstanding_field, 0) or 0
			
			if operation == 'subtract':
				new_outstanding = current_outstanding - amount
			else:  # add
				new_outstanding = current_outstanding + amount
			
			# Ensure outstanding doesn't go negative
			new_outstanding = max(0, new_outstanding)
			
			pdo.db_set(outstanding_field, new_outstanding)
			
			# frappe.msgprint(_(
			# 	"Updated {0} outstanding for PDO {1}: {2} → {3}"
			# ).format(
			# 	tipe_pdo,
			# 	pdo_name,
			# 	frappe.format_value(current_outstanding, {'fieldtype': 'Currency'}),
			# 	frappe.format_value(new_outstanding, {'fieldtype': 'Currency'})
			# ))
			
		except Exception as e:
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Error updating PDO {pdo_name} outstanding"
			)
			frappe.throw(_("Failed to update outstanding amount: {0}").format(str(e)))