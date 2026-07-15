# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "permintaan_dana_operasional",
		"transactions": [
			{
				"label": _("Payment"),
				"items": ["Payment Entry"],
			},
		],
	}
