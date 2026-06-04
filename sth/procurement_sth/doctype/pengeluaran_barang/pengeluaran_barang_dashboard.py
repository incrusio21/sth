from frappe import _

def get_data():
	return {
		"fieldname": "pengeluaran_barang",
		"transactions": [
			{
				"label": _("Stock"),
				"items": [
					"Stock Entry"
				],
			}
		],
	}
