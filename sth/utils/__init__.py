# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import formatdate, get_link_to_form
from frappe.query_builder import DocType
from cryptography.fernet import Fernet

def generate_duplicate_key(self, fieldname, key=None, cancel=0):
    self.set(fieldname, None if cancel else "|".join(key))

def validate_overlap(doc, from_date, to_date, from_date_field="from_date", to_date_field="to_date", company=None, for_field=None):
    doctype = DocType(doc.doctype)

    query = (
        frappe.qb.from_(doctype)
        .select(doctype.name)
        .where(
			(doctype.name != doc.name) & (	
                doctype[from_date_field].between(from_date, to_date) |
                doctype[to_date_field].between(from_date, to_date) | 
				((doctype[from_date_field] < from_date) & (doctype[to_date_field] > to_date))
            )
		)
    )

    if company:
        query = query.where(doctype.company == company)
	
    if for_field:
        query = query.where(doctype[for_field] == doc.get(for_field))

    overlap_doc = query.run(as_dict=1)
    if overlap_doc:
        if for_field:
            exists_for = doc.get(for_field)
        if company:
            exists_for = company

        msg = (
            _("A {0} exists between {1} and {2} (").format(
                doc.doctype, formatdate(from_date), formatdate(to_date)
            )
            + f""" <b>{get_link_to_form(doc.doctype, overlap_doc[0].name)}</b>"""
            + _(") for {0}").format(exists_for)
        )
        frappe.throw(msg)

def encrypt(text = "") -> str:
    cipher = Fernet(frappe.conf.salt)
    return cipher.encrypt(text.encode()).decode()

def decrypt(token = "") -> str:
    cipher = Fernet(frappe.conf.salt)
    return cipher.decrypt(token.encode()).decode()