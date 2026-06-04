import frappe

def ambil_ap_in_transit_procurement(tipe, company):
	proc_settings = frappe.get_single("Procurement Settings")
	
	table = ""

	if tipe == "proposal":
		table = "ap_in_transit_proposal"

	elif tipe == "jasa":
		table = "ap_in_transit_po_jasa"

	elif tipe == "barang":
		table = "ap_in_transit_po_barang"

	akun_expense = ""
	for row in proc_settings.get(table):
		if row.company == company:
			akun_expense = row.account

	if not akun_expense:
		frappe.throw(
			_("Account AP in Transit untuk company <b>{0}</b> tidak ditemukan. "
			  "Pastikan akun tersebut sudah dipasang di Procurement Settings").format(self.company)
		)

	return akun_expense

def ambil_uang_muka_procurement():

	proc_settings = frappe.get_single("Procurement Settings")
	
	table = ""

	if tipe == "proposal":
		table = "uang_muka_proposal"

	elif tipe == "jasa":
		table = "uang_muka_po_jasa"

	elif tipe == "barang":
		table = "uang_muka_po_barang"

	akun_expense = ""
	for row in proc_settings.get(table):
		if row.company == company:
			akun_expense = row.account

	if not akun_expense:
		frappe.throw(
			_("Account Uang Muka untuk company <b>{0}</b> tidak ditemukan. "
			  "Pastikan akun tersebut sudah dipasang di Procurement Settings").format(self.company)
		)

	return akun_expense

def ambil_hutang_invoice_procurement():

	proc_settings = frappe.get_single("Procurement Settings")
	
	table = ""

	if tipe == "proposal":
		table = "hutang_invoice_proposal"

	elif tipe == "jasa":
		table = "hutang_invoice_po_jasa"

	elif tipe == "barang":
		table = "hutang_invoice_po_barang"

	akun_expense = ""
	for row in proc_settings.get(table):
		if row.company == company:
			akun_expense = row.account

	if not akun_expense:
		frappe.throw(
			_("Account Hutang Invoice untuk company <b>{0}</b> tidak ditemukan. "
			  "Pastikan akun tersebut sudah dipasang di Procurement Settings").format(self.company)
		)

	return akun_expense