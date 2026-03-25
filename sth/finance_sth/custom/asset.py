import frappe
from frappe.model.document import Document
from frappe.utils.safe_exec import safe_eval
from frappe import _

@frappe.whitelist()	
def calculate_penyusutan_fiscal(self, method):
	# if self.rumus_tml_penyusutan_fiscal and self.gross_purchase_amount:
	# 	try:
	# 		eval_context = {
	# 			'nilai_perolehan': self.gross_purchase_amount,
	# 		}
			
	# 		result = safe_eval(self.rumus_tml_penyusutan_fiscal, eval_context)
	# 		self.penyusutan_fiscal_tahun_ini = result
			
	# 	except Exception as e:
	# 		frappe.throw(f'Error dalam formula penyusutan fiskal: {str(e)}')
	# else:
	# 	self.penyusutan_fiscal_tahun_ini = 0.0

	if not self.gross_purchase_amount or not self.total_depreciation_fiscal:
		return

	regenerate_for_asset(self.name, self.total_depreciation_fiscal, self.purchase_date)

def regenerate_for_asset(asset_name: str, total_depreciation_fiscal: int, purchase_date):
	existing = frappe.db.get_value(
		"Asset Depreciation Fiscal", {"asset": asset_name}, "name"
	)
	if existing:
		doc = frappe.get_doc("Asset Depreciation Fiscal", existing)
		doc.total_depreciation_fiscal = total_depreciation_fiscal
		doc.purchase_date = purchase_date
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.new_doc("Asset Depreciation Fiscal")
		doc.asset = asset_name
		doc.total_depreciation_fiscal = total_depreciation_fiscal
		doc.purchase_date = purchase_date
		doc.insert(ignore_permissions=True)