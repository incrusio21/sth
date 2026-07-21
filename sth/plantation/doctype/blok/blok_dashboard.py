from frappe import _


def get_data():
	return {
		"fieldname": "blok",
		"non_standard_fieldnames": {
			"Journal Entry": "blok"
		},
		
		"internal_and_external_links": {
			"Journal Entry": "naik_tm_journal_entry",
		},
		"transactions": [
			{
				"label": _("Accounting"),
				"items": [
					
					"Journal Entry",
				],
			},
			
		],
	}
