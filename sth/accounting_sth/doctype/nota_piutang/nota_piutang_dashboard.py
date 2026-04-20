from frappe import _

def get_data():
	return {
		"fieldname": "nota_piutang",
		"non_standard_fieldnames": {
			"Journal Entry": "nota_piutang",
			"Payment Entry": "nota_piutang_pemenuhan_kontrak",
		},
		"internal_links": {
			
		},
		"transactions": [
			{"label": _("Reference"), "items": ["Payment Entry", "Journal Entry"]}
		],
	}