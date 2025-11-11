import frappe

@frappe.whitelist()
def test_buat_gl():
	doc = frappe.get_doc("Pengajuan Panen Kontanan","PPK-00195")
	master_pembuatan_gl_dan_pl(doc,"validate")


@frappe.whitelist()
def master_pembuatan_gl_dan_pl(doc,method):
	# menentukan pembuatan gl
	akun_debit = ""
	akun_credit = ""
	nilai_debit = ""
	nilai_credit = ""

	if doc.doctype == "Pengajuan Panen Kontanan":
		akun_debit = doc.get("salary_account")
		akun_credit = doc.get("paid_account")
		nilai_debit = doc.get("grand_total")
		nilai_credit = doc.get("grand_total")

	pembuatan_gl_entry(doc,akun_debit, akun_credit, nilai_debit, nilai_credit)

@frappe.whitelist()
def pembuatan_gl_entry(self,akun_debit, akun_credit, nilai_debit, nilai_credit):
	from erpnext.accounts.general_ledger import make_gl_entries, make_reverse_gl_entries
	gl_entries = []
	gl_entries.append(
		self.get_gl_dict(
			{
				"account": akun_debit,
				"against": akun_credit,
				"debit": nilai_debit,
				"debit_in_account_currency": nilai_debit			
			},
			item=self,
		)
	)

	gl_entries.append(
		self.get_gl_dict(
			{
				"account": akun_credit,
				"against": akun_debit,
				"credit": nilai_debit,
				"credit_in_account_currency": nilai_debit			
			},
			item=self,
		)
	)

	if self.docstatus == 1:
		make_gl_entries(
			gl_entries,
			merge_entries=False,
		)
	elif self.docstatus == 2:
		make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

@frappe.whitelist()
def pembuatan_pl_entry(doc,method):
	pass