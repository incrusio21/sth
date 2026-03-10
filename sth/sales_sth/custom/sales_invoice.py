
import frappe
def validate_expense_account(self, method):
	if self.jenis_penagihan == "Uang Muka":
		default_account = frappe.db.get_value(
			"Company",
			self.company,
			"default_uang_muka_penjualan_account"
		)
		
		if default_account:
			for item in self.items:
				item.income_account = default_account