import frappe
from frappe import _

def calculate_ongkos_angkut(doc, method):
	# Handle Ongkos Angkut Transportir
	handle_ongkos_angkut_transportir(doc)
	
	# Handle Ongkos Angkut Bongkar
	handle_ongkos_angkut_bongkar(doc)
	
	doc.calculate_taxes_and_totals()

def handle_ongkos_angkut_transportir(doc):
	if not doc.ongkos_angkut or doc.ongkos_angkut == 0:
		remove_ongkos_angkut_line(doc, 'default_ongkos_angkut_account', 'Ongkos Angkut Transportir')
		return
	
	ongkos_account = frappe.db.get_value('Company', doc.company, 'default_ongkos_angkut_account')
	
	if not ongkos_account:
		frappe.throw(_("Please set Default Ongkos Angkut Account in Company: {0}").format(doc.company))
	
	total_qty = sum([item.qty for item in doc.items])
	
	if total_qty == 0:
		frappe.msgprint(_("Total quantity is zero, Ongkos Angkut Transportir not added"))
		return
	
	ongkos_amount = doc.ongkos_angkut * total_qty
	ongkos_line = None
	
	for tax in doc.taxes:
		if tax.account_head == ongkos_account and tax.description and "Ongkos Angkut Transportir" in tax.description:
			ongkos_line = tax
			break
	
	if ongkos_line:
		ongkos_line.charge_type = "Actual"
		ongkos_line.tax_amount = ongkos_amount
		ongkos_line.description = f"Ongkos Angkut Transportir ({doc.ongkos_angkut} x {total_qty} qty)"
	else:
		doc.append('taxes', {
			'charge_type': 'Actual',
			'account_head': ongkos_account,
			'description': f"Ongkos Angkut Transportir ({doc.ongkos_angkut} x {total_qty} qty)",
			'tax_amount': ongkos_amount
		})

def handle_ongkos_angkut_bongkar(doc):
	if not doc.ongkos_angkut_bongkar or doc.ongkos_angkut_bongkar == 0:
		remove_ongkos_angkut_line(doc, 'default_ongkos_angkut_bongkar_account', 'Ongkos Angkut Bongkar')
		return
	
	ongkos_account = frappe.db.get_value('Company', doc.company, 'default_ongkos_angkut_bongkar_account')
	
	if not ongkos_account:
		frappe.throw(_("Please set Default Ongkos Angkut Bongkar Account in Company: {0}").format(doc.company))
	
	total_qty = sum([item.qty for item in doc.items])
	
	if total_qty == 0:
		frappe.msgprint(_("Total quantity is zero, Ongkos Angkut Bongkar not added"))
		return
	
	ongkos_amount = doc.ongkos_angkut_bongkar * total_qty
	ongkos_line = None
	
	for tax in doc.taxes:
		if tax.account_head == ongkos_account and tax.description and "Ongkos Angkut Bongkar" in tax.description:
			ongkos_line = tax
			break
	
	if ongkos_line:
		ongkos_line.charge_type = "Actual"
		ongkos_line.tax_amount = ongkos_amount
		ongkos_line.description = f"Ongkos Angkut Bongkar ({doc.ongkos_angkut_bongkar} x {total_qty} qty)"
	else:
		doc.append('taxes', {
			'charge_type': 'Actual',
			'account_head': ongkos_account,
			'description': f"Ongkos Angkut Bongkar ({doc.ongkos_angkut_bongkar} x {total_qty} qty)",
			'tax_amount': ongkos_amount
		})

def remove_ongkos_angkut_line(doc, account_field, description_keyword):
	ongkos_account = frappe.db.get_value('Company', doc.company, account_field)
	
	if not ongkos_account:
		return
	
	taxes_to_remove = []
	for idx, tax in enumerate(doc.taxes):
		if tax.account_head == ongkos_account and tax.description and description_keyword in tax.description:
			taxes_to_remove.append(idx)
	
	for idx in reversed(taxes_to_remove):
		doc.taxes.pop(idx)