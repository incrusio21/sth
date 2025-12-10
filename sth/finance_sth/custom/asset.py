import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_eval

@frappe.whitelist()	
def calculate_penyusutan_fiscal(self, method):
	if self.rumus_tml_penyusutan_fiscal and self.gross_purchase_amount:
		try:
			eval_context = {
				'nilai_perolehan': self.gross_purchase_amount,
			}
			
			result = safe_eval(self.rumus_tml_penyusutan_fiscal, eval_context)
			self.penyusutan_fiscal_tahun_ini = result
			
		except Exception as e:
			frappe.throw(f'Error dalam formula penyusutan fiskal: {str(e)}')
	else:
		self.penyusutan_fiscal_tahun_ini = 0.0