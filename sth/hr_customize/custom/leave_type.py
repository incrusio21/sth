# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

def clear_cache(self, method):
    from sth.overrides.salary_slip import LEAVE_CODE_MAP

    frappe.cache().delete_value(LEAVE_CODE_MAP)