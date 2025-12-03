import frappe

def update_ba_reference(doc,method):
    if doc.berita_acara:
        if method == "on_submit":
            frappe.db.set_value("Berita Acara",doc.berita_acara,"material_request",doc.name,update_modified=False)
        elif method == "on_cancel":
            frappe.db.set_value("Berita Acara",doc.berita_acara,"material_request","",update_modified=False)