import frappe
from erpnext.setup.doctype.item_group.item_group import ItemGroup

class ItemGroup(ItemGroup):    
	def autoname(self):
		if not self.custom_item_group_code:
			self.custom_item_group_code = self.generate_group_code()
		self.name = self.item_group_name
	
	def generate_group_code(self):
		if self.parent_item_group == "All Item Groups":
			return ""
		
		if self.parent_item_group:
			return self.get_next_code_by_parent(self.parent_item_group)
		
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
	
	def get_next_code_by_parent(self, parent_group):
		parent_code = frappe.db.get_value("Item Group", parent_group, "custom_item_group_code")
		
		if not parent_code:
			frappe.throw(f"Parent Item Group '{parent_group}' does not have a code")
		
		last_child = frappe.db.sql("""
			SELECT custom_item_group_code 
			FROM `tabItem Group` 
			WHERE custom_item_group_code LIKE %s
			AND custom_item_group_code IS NOT NULL
			AND custom_item_group_code != ''
			ORDER BY custom_item_group_code DESC 
			LIMIT 1
		""", (f"{parent_code}%",))
		
		if last_child and last_child[0][0]:
			last_code = last_child[0][0]
			suffix = last_code[len(parent_code):]
			try:
				last_number = int(suffix) if suffix else 0
				new_number = last_number + 1
			except ValueError:
				new_number = 1
		else:
			new_number = 1
		
		return f"{parent_code}{new_number:02d}"

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

@frappe.whitelist()
def get_next_group_code_by_parent(parent_group):

	if parent_group == "All Item Groups":
		return None
	
	parent_code = frappe.db.get_value("Item Group", parent_group, "custom_item_group_code")
	
	if not parent_code:
		frappe.msgprint(f"Parent Item Group '{parent_group}' does not have a code")
		return None
	
	last_child = frappe.db.sql("""
		SELECT custom_item_group_code 
		FROM `tabItem Group` 
		WHERE custom_item_group_code LIKE %s
		AND custom_item_group_code IS NOT NULL
		AND custom_item_group_code != ''
		ORDER BY custom_item_group_code DESC 
		LIMIT 1
	""", (f"{parent_code}%",))
	
	if last_child and last_child[0][0]:
		last_code = last_child[0][0]
		suffix = last_code[len(parent_code):]
		try:
			last_number = int(suffix) if suffix else 0
			new_number = last_number + 1
		except ValueError:
			new_number = 1
	else:
		new_number = 1
	
	return f"{parent_code}{new_number:02d}"