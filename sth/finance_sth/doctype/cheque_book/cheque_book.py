# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ChequeBook(Document):
	def validate(self):
		self.validate_numbers()
		self.validate_cheque_number()

	def on_submit(self):
		self.make_cheque_number()
	
	def before_update_after_submit(self):
		self.validate_cheque_number_updated()

	def on_update_after_submit(self):
		self.update_cheque_number()

	def before_cancel(self):
		cheque_numbers = get_cheque_numbers(self.cheque_start_no, self.cheque_end_no)
		check_usage_cheque_number(self.cheque_code, cheque_numbers.start_no, cheque_numbers.end_no)

	def on_cancel(self):
		cheque_numbers = get_cheque_numbers(self.cheque_start_no, self.cheque_end_no)
		delete_cheque_number(self.cheque_code, cheque_numbers.start_no, cheque_numbers.end_no)
		self.update_total_remaining()

	def make_cheque_number(self):
		cheque_numbers = get_cheque_numbers(self.cheque_start_no, self.cheque_end_no)
		create_cheque_number(self.name, self.cheque_code, cheque_numbers.start_no, cheque_numbers.end_no, self.bank_account)

		self.update_total_remaining()

	def validate_cheque_number(self, is_update=False):
		cheque_numbers = get_cheque_numbers(self.cheque_start_no, self.cheque_end_no)
		code = list(set(f"{self.cheque_code}{row}" for row in range(cheque_numbers.start_no, cheque_numbers.end_no)))

		if is_update:
			old_doc = self.get_doc_before_save()
			old_end_no = int(old_doc.cheque_end_no)
			end_no = int(self.cheque_end_no)+1
			code = list(set(f"{self.cheque_code}{row}" for row in range(old_end_no, end_no)))

		cheque_number = frappe.qb.DocType("Cheque Number")
		query = (frappe.qb.from_(cheque_number)
			.select(cheque_number.name)
			.where(cheque_number.name.isin(code))
		)

		res = query.run(as_dict=True)
		if not res:
			return True

		cheque_exist = list(set(row.name for row in res))
		str_cheque = ", ".join(cheque_exist)
		frappe.throw(f"Cheque Number <b>{str_cheque}</b> sudah pernah dibuat di Cheque Book lain")

	def validate_cheque_number_updated(self):
		old_doc = self.get_doc_before_save()
		old_end_no = int(old_doc.cheque_end_no) + 1
		end_no = int(self.cheque_end_no)

		if end_no < old_end_no:
			check_usage_cheque_number(self.cheque_code, end_no, old_end_no)
		if end_no > old_end_no:
			self.validate_cheque_number(is_update=True)

	def update_cheque_number(self):
		old_doc = self.get_doc_before_save()
		old_end_no = int(old_doc.cheque_end_no)
		end_no = int(self.cheque_end_no)

		if end_no < old_end_no:
			old_end_no += 1
			delete_cheque_number(self.cheque_code, end_no, old_end_no)
		if end_no > old_end_no:
			end_no += 1
			create_cheque_number(self.name, self.cheque_code, old_end_no, end_no, self.bank_account)
	
		self.update_total_remaining()

	def update_total_remaining(self):
		total_cheque_number = frappe.db.count("Cheque Number", {
											"cheque_book": self.name
										})
		used_cheque_number = frappe.db.count("Cheque Number", {
											"cheque_book": self.name,
											"reference_doc": ["is", "set"],
											"reference_name": ["is", "set"]
										})

		self.cheques_total = total_cheque_number
		self.remaining_cheques = total_cheque_number - used_cheque_number
		self.db_update_all()

		if self.remaining_cheque_warning == self.remaining_cheques:
			frappe.msgprint(f"Sisa Cheque Number saat ini {self.remaining_cheques} di Check Book {self.name}")

	def validate_numbers(self):
		start_no = int(self.cheque_start_no)
		end_no = int(self.cheque_end_no)

		if start_no > end_no:
			frappe.throw("<b>Cheque Start Number </b> tidak boleh lebih besar dari <b>Cheque End Number</b>")


def get_cheque_numbers(cheque_start_no, cheque_end_no):
	start_no = int(cheque_start_no)
	end_no = int(cheque_end_no) + 1

	return frappe._dict({
		"start_no": start_no,
		"end_no": end_no
	})

def check_usage_cheque_number(cheque_code, start_no, end_no):
	code = list(set(f"{cheque_code}{row}" for row in range(start_no, end_no)))

	cheque_number = frappe.qb.DocType("Cheque Number")
	query = (frappe.qb.from_(cheque_number)
		.select(cheque_number.name)
		.where((cheque_number.name.isin(code)) & 
			(cheque_number.reference_doc.notnull()) & 
			(cheque_number.reference_name.notnull()))
	)
	res = query.run(as_dict=True)
	if not res:
		return True
	
	cheque_is_used = list(set(row.name for row in res))
	str_cheque = ", ".join(cheque_is_used)
	frappe.throw(f"Cheque Number <b>{str_cheque}</b> sudah digunakan, mohon periksa kembali")

def create_cheque_number(cheque_book, cheque_code, start_no, end_no, bank_account):
	for i in range(start_no, end_no):
		doc = frappe.get_doc({
			'doctype': 'Cheque Number',
			'number': i,
			'code': cheque_code,
			'cheque_book': cheque_book,
			'bank_account': bank_account
		})
		doc.insert()

def delete_cheque_number(cheque_code, start_no, end_no):
	code = list(set(f"{cheque_code}{row}" for row in range(start_no, end_no)))
	cheque_number = frappe.qb.DocType("Cheque Number")
	query = (frappe.qb.from_(cheque_number)
		.delete()
		.where(cheque_number.name.isin(code))
	)

	query.run()

def update_cheque_book_pe(cheque_number):
	cheque_usage_history = frappe.db.get_value("Cheque Usage History", {
		"parent": cheque_number.cheque_book,
		"parenttype": "Cheque Book",
		"reference_document": cheque_number.reference_doc,
		"reference_name": cheque_number.reference_name,
	}, "*")
	
	if cheque_usage_history:
		change_cheque_number(cheque_usage_history, cheque_number)
	else:
		append_cheque_history(cheque_number)
	cheque_book_doc = frappe.get_doc("Cheque Book", cheque_number.cheque_book)
	cheque_book_doc.update_total_remaining()

def change_cheque_number(cheque_usage_history, cheque_number):
	values = {
		"status": cheque_number.status,
		"cheque_amount": cheque_number.cheque_amount,
		"note": cheque_number.note,
		"issue_date": cheque_number.issue_date
	}
	if cheque_usage_history.cheque_no != cheque_number.name:
		old_cheque_number = frappe.get_doc("Cheque Number", cheque_usage_history.cheque_no)
		old_cheque_number.reference_doc= None
		old_cheque_number.reference_name= None
		old_cheque_number.status= None
		old_cheque_number.note= None
		old_cheque_number.issue_date= None
		old_cheque_number.cheque_amount= 0
		old_cheque_number.db_update()
		values.update({"cheque_no": cheque_number.name})

	frappe.db.set_value("Cheque Usage History", cheque_usage_history.name, values)

def append_cheque_history(cheque_number):
	cheque_book = frappe.get_doc("Cheque Book", cheque_number.cheque_book)
	cheque_book.append("table_ezdi", {
		"cheque_no": cheque_number.name,
		"reference_document": cheque_number.reference_doc,
		"reference_name": cheque_number.reference_name,
		"status": cheque_number.status,
		"cheque_amount": cheque_number.cheque_amount,
		"note": cheque_number.note,
		"issue_date": cheque_number.issue_date,
	})
	cheque_book.db_update_all()

def delete_cheque_history(cheque_number): 
	cn_doc = frappe.get_doc("Cheque Number", cheque_number) 
	cb_doc = frappe.get_doc("Cheque Book", cn_doc.cheque_book) 
	for row in cb_doc.table_ezdi: 
		if row.cheque_no != cheque_number: 
			continue 
		row.docstatus = 0 
		row.db_update_all() 
		row.delete() 
	
	idx = 0
	
	cn_doc.note= None,
	cn_doc.cheque_amount= 0,
	cn_doc.issue_date= None,
	cn_doc.reference_doc= None,
	cn_doc.reference_name= None,
	cn_doc.status= None
	cn_doc.db_update_all()
	
	
	cb_doc.update_total_remaining()	
	for row in cb_doc.table_ezdi: 
		idx+=1 
		row.idx = idx 
		row.db_update_all() 
		cb_doc.db_update_all()