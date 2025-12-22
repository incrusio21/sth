
import frappe
from erpnext.buying.doctype.supplier.supplier import Supplier

class Supplier(Supplier):    
	def autoname(self):
		if not self.kode_supplier:
			self.kode_supplier = self.generate_supplier_code()
			self.name = self.kode_supplier
		else:
			self.name = self.kode_supplier
	
	def generate_supplier_code(self):
		from datetime import datetime
		
		year_month = datetime.now().strftime("%Y%m")
		prefix = f"SUPP-{year_month}-"
		
		last_item = frappe.db.sql("""
			SELECT name 
			FROM `tabSupplier` 
			WHERE name LIKE %s 
			ORDER BY name DESC 
			LIMIT 1
		""", (prefix + "%",))
		
		if last_item:
			last_code = last_item[0][0]
			last_number = int(last_code.split('-')[-1])
			new_number = last_number + 1
		else:
			new_number = 1
		
		return f"{prefix}{new_number:05d}"

@frappe.whitelist()
def get_next_supplier():
	from datetime import datetime
		
	year_month = datetime.now().strftime("%Y%m")
	prefix = f"SUPP-{year_month}-"
	
	last_item = frappe.db.sql("""
		SELECT name 
		FROM `tabSupplier` 
		WHERE name LIKE %s 
		ORDER BY name DESC 
		LIMIT 1
	""", (prefix + "%",))
	
	if last_item:
		last_code = last_item[0][0]
		last_number = int(last_code.split('-')[-1])
		new_number = last_number + 1
	else:
		new_number = 1
	
	return f"{prefix}{new_number:05d}"