from frappe import _


def get_data(data):
	return {
		"fieldname": "asset",
		"non_standard_fieldnames": {
			"Asset Maintenance": "asset_name",
			"Journal Entry": "reference_name"
		},
		"transactions": [
			{
				"label": _("Movement"), 
				"items": ["Asset Movement"]
			},
			{
				"label": _("Maintenance"), 
				"items": ["Asset Maintenance"]
			},
			{
				"label": _("Repair"), 
				"items": ["Asset Repair"]
			},
			{
				"label": _("Value"), 
				"items": ["Asset Value Adjustment"]
			},
			{
				"label": _("Depreciation"), 
				"items": ["Asset Depreciation Schedule","Asset Depreciation Fiscal"]
			},
			{
				"label": _("Journal Entry"), 
				"items": ["Journal Entry"]
			},
			{
				"label": _("Asset Capitalization"), 
				"items": ["Asset Capitalization"]
			},
		],
	}
