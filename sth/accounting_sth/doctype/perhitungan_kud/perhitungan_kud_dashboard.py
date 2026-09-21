from frappe import _


def get_data():
	return {
		"fieldname": "perhitungan_kud",
		"transactions": [
			{"label": _("Penagihan"), "items": ["Nota Piutang", "Purchase Invoice"]},
		],
	}
