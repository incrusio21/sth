# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_dashboard_data(data):
	data["non_standard_fieldnames"]["Contract"] = "document_name"
	data.transactions.append(
		{"label": _("Reference"), "items": ["Contract"]
    })
	
	return data