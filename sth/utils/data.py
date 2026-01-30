# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def tax_rate(company, tax_name=None, type=""):
    tax_account, tax = "", {}
    if tax_name:
        tax = frappe.get_cached_doc("Tax Rate", tax_name)
        
        # Mencari account yang sesuai
        tax_account = next(
            (a.account for a in tax.tax_rate_account 
            if a.company == company and a.tipe == type),
            None
        )
    
    return {
        "rate": tax.get("rate") or 0,
        "account": tax_account
    }
