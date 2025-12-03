import frappe
from frappe import _

def calculate_ongkos_angkut(doc, method):
	"""Add Ongkos Angkut to taxes and charges table"""
	
	if not doc.ongkos_angkut or doc.ongkos_angkut == 0:
		remove_ongkos_angkut_line(doc)
		return
	
	ongkos_account = frappe.db.get_value('Company', doc.company, 'default_ongkos_angkut_account')
	
	if not ongkos_account:
		frappe.throw(_("Please set Default Ongkos Angkut Account in Company: {0}").format(doc.company))
	
	total_qty = sum([item.qty for item in doc.items])
	
	if total_qty == 0:
		frappe.msgprint(_("Total quantity is zero, Ongkos Angkut not added"))
		return
	
	ongkos_amount = doc.ongkos_angkut * total_qty
	
	# Find existing ongkos angkut line - check if description contains "Ongkos Angkut"
	ongkos_line = None
	for tax in doc.taxes:
		if tax.account_head == ongkos_account and tax.description and "Ongkos Angkut" in tax.description:
			ongkos_line = tax
			break
	
	if ongkos_line:
		# Update existing line
		ongkos_line.charge_type = "Actual"
		ongkos_line.tax_amount = ongkos_amount
		ongkos_line.description = f"Ongkos Angkut ({doc.ongkos_angkut} x {total_qty} qty)"
	else:
		# Add new line only if it doesn't exist
		doc.append('taxes', {
			'charge_type': 'Actual',
			'account_head': ongkos_account,
			'description': f"Ongkos Angkut ({doc.ongkos_angkut} x {total_qty} qty)",
			'tax_amount': ongkos_amount
		})

	doc.calculate_taxes_and_totals()
		
def remove_ongkos_angkut_line(doc):
	"""Remove Ongkos Angkut line from taxes if it exists"""
	ongkos_account = frappe.db.get_value('Company', doc.company, 'default_ongkos_angkut_account')
	
	if not ongkos_account:
		return
	
	taxes_to_remove = []
	for idx, tax in enumerate(doc.taxes):
		if tax.account_head == ongkos_account and tax.description and "Ongkos Angkut" in tax.description:
			taxes_to_remove.append(idx)
	
	# Remove in reverse order to maintain indices
	for idx in reversed(taxes_to_remove):
		doc.taxes.pop(idx)