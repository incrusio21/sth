
import frappe
from erpnext.selling.doctype.customer.customer import Customer

from sth.overrides.rename_kode import RenameKodeMixin

class Customer(RenameKodeMixin, Customer):
	kode_field = "kode_pelanggan"

	def autoname(self):
		if not self.kode_pelanggan:
			self.kode_pelanggan = self.generate_customer_code()
			self.name = self.kode_pelanggan
		else:
			self.name = self.kode_pelanggan

	def validate(self):
		super().validate()
		self.validate_kode_baru()

	def on_update(self):
		super().on_update()
		self.rename_ke_kode()

	def generate_customer_code(self):
		from datetime import datetime
		
		year_month = datetime.now().strftime("%Y%m")
		prefix = f"CUST-{year_month}-"
		
		last_item = frappe.db.sql("""
			SELECT name 
			FROM `tabCustomer` 
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
def get_next_customer():
	from datetime import datetime
		
	year_month = datetime.now().strftime("%Y%m")
	prefix = f"CUST-{year_month}-"
	
	last_item = frappe.db.sql("""
		SELECT name 
		FROM `tabCustomer` 
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