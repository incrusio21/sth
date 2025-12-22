
import frappe
from erpnext.stock.doctype.item.item import Item

class Item(Item):    
	def autoname(self):
		if not self.item_code:
			self.name = self.generate_item_code()
		else:
			self.name = self.item_code
	
	def generate_item_code(self):
		from datetime import datetime
		
		year_month = datetime.now().strftime("%Y%m")
		prefix = f"ITEM-{year_month}-"
		
		last_item = frappe.db.sql("""
			SELECT name 
			FROM `tabItem` 
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
def get_next_item_code():
	"""Generate next item code without saving"""
	from datetime import datetime
	
	year_month = datetime.now().strftime("%Y%m")
	prefix = f"ITEM-{year_month}-"
	
	last_item = frappe.db.sql("""
		SELECT name 
		FROM `tabItem` 
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