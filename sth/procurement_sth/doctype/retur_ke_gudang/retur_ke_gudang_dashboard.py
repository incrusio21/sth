from frappe import _

def get_data():
	return {
		"fieldname": "retur_ke_gudang",
		"transactions": [
			{
				"label": _("Stock"),
				"items": [
					"Stock Entry"
				],
			}
		],
	}
