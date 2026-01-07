from frappe import _


def get_data():
	return {
		"fieldname": "bapp_no",
		"non_standard_fieldnames": {
			"Purchase Invoice": "bapp",
			"Asset": "purchase_receipt",
			"Auto Repeat": "reference_document",
			"Quality Inspection": "reference_name",
		},
		"internal_links": {
			"Material Request": ["items", "material_request"],
			"Proposal": ["items", "proposal"],
			"Project": ["items", "project"],
		},
		"transactions": [
			{
				"label": _("Related"),
				"items": ["Purchase Invoice", "Asset"],
			},
			{
				"label": _("Reference"),
				"items": ["Material Request", "Proposal", "Quality Inspection", "Project"],
			},
			{"label": _("Subscription"), "items": ["Auto Repeat"]},
		],
	}
