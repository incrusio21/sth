from frappe import _


def get_data():
	return {
		"fieldname": "surat_jalan",
		"transactions": [
			{
				"label": _("Stock"),
				"items": [
					"Stock Entry"
				],
			}
		],
	}
