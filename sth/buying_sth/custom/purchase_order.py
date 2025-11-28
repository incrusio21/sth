# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def get_order_type_configure_column(order_type):
    return frappe.db.sql(
        """
        select fieldname, columns from `tabOrder Type Item Column`
        where `parent`=%s
        order by idx """,
        (order_type), as_dict=1
    )