import frappe
from erpnext.stock.doctype.item.item import Item
from frappe import _

class Item(Item):    
	def autoname(self):
		if not self.item_code:
			self.name = self.generate_item_code()
		else:
			self.name = self.item_code
	
	def generate_item_code(self):
		if not self.item_group:
			frappe.throw("Item Group is required to generate Item Code")
		
		# Get item_group name/code
		item_group_code = self.item_group
		
		# Find last item with this item_group prefix
		last_item = frappe.db.sql("""
			SELECT name 
			FROM `tabItem` 
			WHERE name LIKE %s 
			ORDER BY name DESC 
			LIMIT 1
		""", (item_group_code + "%",))
		
		if last_item:
			last_code = last_item[0][0]
			# Extract the numeric part after the item_group code
			last_number = int(last_code.replace(item_group_code, ''))
			new_number = last_number + 1
		else:
			new_number = 1
		
		return f"{item_group_code}{new_number}"

@frappe.whitelist()
def get_next_item_code(item_group):
	"""Generate next item code based on item_group without saving"""
	if not item_group:
		return ""
	
	# Find last item with this item_group prefix
	last_item = frappe.db.sql("""
		SELECT name 
		FROM `tabItem` 
		WHERE name LIKE %s 
		ORDER BY name DESC 
		LIMIT 1
	""", (item_group + "%",))
	
	if last_item:
		last_code = last_item[0][0]
		# Extract the numeric part after the item_group code
		try:
			last_number = int(last_code.replace(item_group, ''))
			new_number = last_number + 1
		except ValueError:
			# If can't parse number, start from 1
			new_number = 1
	else:
		new_number = 1
	
	return f"{item_group}{new_number}"


def validate_item_name(doc, method):

	if not doc.item_name:
		return
	
	existing_items = frappe.db.sql("""
		SELECT name 
		FROM `tabItem` 
		WHERE LOWER(item_name) = LOWER(%s) 
		AND name != %s
	""", (doc.item_name, doc.name or ''))
	
	if existing_items:
		frappe.throw(
			_("Item with name '{0}' already exists: {1}").format(
				doc.item_name, 
				existing_items[0][0]
			),
			title=_("Duplicate Item Name")
		)
