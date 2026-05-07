from frappe import _


def get_data():
	return {
		"fieldname": "transaksi_berulang",
		"transactions": [
			{
				"label": _("Journal"),
				"items": [
					"Journal Entry"
				],
			}
		],
	}
