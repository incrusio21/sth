import frappe
from erpnext.setup.doctype.item_group.item_group import ItemGroup

class ItemGroup(ItemGroup):    
	def autoname(self):
		if not self.custom_item_group_code:
			self.custom_item_group_code = self.generate_group_code()
		self.name = self.item_group_name
	
	def generate_group_code(self):
		last_group = frappe.db.sql("""
			SELECT custom_item_group_code 
			FROM `tabItem Group` 
			WHERE custom_item_group_code IS NOT NULL
			AND custom_item_group_code != ''
			ORDER BY custom_item_group_code DESC 
			LIMIT 1
		""")
		
		if last_group and last_group[0][0]:
			last_code = last_group[0][0]
			try:
				last_number = int(last_code)
				new_number = last_number + 1
			except ValueError:
				new_number = 1
		else:
			new_number = 1
		
		return f"{new_number:06d}"

@frappe.whitelist()
def get_next_group_code():
	
	last_group = frappe.db.sql("""
		SELECT custom_item_group_code 
		FROM `tabItem Group` 
		WHERE custom_item_group_code IS NOT NULL
		AND custom_item_group_code != ''
		ORDER BY custom_item_group_code DESC 
		LIMIT 1
	""")
	
	if last_group and last_group[0][0]:
		last_code = last_group[0][0]
		try:
			last_number = int(last_code)
			new_number = last_number + 1
		except ValueError:
			new_number = 1
	else:
		new_number = 1
	
	return f"{new_number:06d}"