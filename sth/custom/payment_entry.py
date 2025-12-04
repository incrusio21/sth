import frappe

from sth.finance_sth.doctype.cheque_number.cheque_number import update_cheque_number_pe
from sth.finance_sth.doctype.cheque_book.cheque_book import update_cheque_book_pe, delete_cheque_history

def cek_kriteria(self,method):
	if self.references:
		for row in self.references:
			doctype = row.reference_doctype
			docname = row.reference_name

			check = 0
			for row in self.detail_dokumen_finance:
				if row.type == doctype and row.name1 == docname:
					check = 1
			
			if check == 0:
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
			self.append("detail_dokumen_finance",{
				"rincian_dokumen_finance": row.rincian_dokumen_finance
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
