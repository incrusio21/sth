import frappe

def track_insurance_changes(doc, method):
	insurance_fields = [
		'policy_number',
		'insurer', 
		'insured_value',
		'insurance_start_date',
		'insurance_end_date',
		'comprehensive_insurance'
	]
	
	should_create_history = False
	if doc.is_new():
		has_insurance_data = any(doc.get(field) for field in insurance_fields)
		if has_insurance_data:
			should_create_history = True
	else:
		old_doc = doc.get_doc_before_save()
		
		if old_doc:
			has_changes = any(
				doc.get(field) != old_doc.get(field) 
				for field in insurance_fields
			)
			
			if has_changes:
				should_create_history = True
	
	if should_create_history:
		doc.append('insurance_history', {
			'policy_number': doc.policy_number,
			'insurer': doc.insurer,
			'insured_value': doc.insured_value,
			'insurance_start_date': doc.insurance_start_date,
			'insurance_end_date': doc.insurance_end_date,
			'comprehensive_insurance': doc.comprehensive_insurance,
			'changed_on': frappe.utils.now(),
			'changed_by': frappe.session.user
		})

		for row in doc.insurance_history:
			row.db_update()