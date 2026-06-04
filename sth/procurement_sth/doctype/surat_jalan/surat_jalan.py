# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class SuratJalan(Document):
    def on_submit(self):
        self.create_ste_issue()
        self.db_set("status", "Terkirim")

    def on_cancel(self):
        # Cancel semua STE terkait (Issue maupun Receipt)
        stes = frappe.get_all(
            "Stock Entry",
            filters={"surat_jalan": self.name, "docstatus": 1},
            pluck="name"
        )
        for ste_name in stes:
            ste = frappe.get_doc("Stock Entry", ste_name)
            ste.cancel()
        self.db_set("status", "Draft")

    # ------------------------------------------------------------------ #
    #  SUBMIT → Material Issue (barang keluar dari gudang_asal)           #
    # ------------------------------------------------------------------ #
    def create_ste_issue(self):

        def postprocess(source, target):
            target.stock_entry_type = "Material Issue"

            update_fields = (
                "item_name", "stock_uom", "description",
                "expense_account", "cost_center",
                "conversion_factor", "barcode", "basic_rate",
            )
            for item in target.items:
                item_details = target.get_item_details(
                    frappe._dict({
                        "item_code": item.item_code,
                        "company": target.company,
                        "project": target.project,
                        "uom": item.uom,
                    }),
                    for_update=True,
                )
                for field in update_fields:
                    if not item.get(field):
                        item.set(field, item_details.get(field))
                    if field == "conversion_factor" and item.uom == item_details.get("stock_uom"):
                        item.set(field, item_details.get(field))

            target.run_method("set_missing_values")

        def update_item(source, target, source_parent):
            # Material Issue → hanya s_warehouse (barang keluar)
            target.s_warehouse = source_parent.gudang_asal
            target.t_warehouse = None

        mapper = {
            "Surat Jalan": {
                "doctype": "Stock Entry",
                "field_map": {
                    "name": "surat_jalan",
                    "tanggal_kirim": "posting_date",
                },
            },
            "Surat Jalan Item": {
                "doctype": "Stock Entry Detail",
                "field_map": {
                    "kode_barang": "item_code",
                    "jumlah": "qty",
                    "satuan": "uom",
                },
                "postprocess": update_item,
            },
        }

        doc = get_mapped_doc("Surat Jalan", self.name, mapper, None, postprocess, True)
        proc_settings = frappe.get_single("Procurement Settings")
        expense_account = ""

        for row in proc_settings.persediaan_dalam_perjalanan_procurement_settings:
            if row.company == self.company:
                expense_account = row.account

        for row in doc.items:
            if expense_account:
                row.expense_account = expense_account

        doc.insert()
        doc.submit()

    # ------------------------------------------------------------------ #
    #  TOMBOL "Diterima" → Material Receipt (barang masuk ke gudang_tujuan)
    # ------------------------------------------------------------------ #
    @frappe.whitelist()
    def create_ste_receipt(self, tanggal_terima):
        # Ambil STE Issue yang terkait
        issue_name = frappe.db.get_value(
            "Stock Entry",
            {"surat_jalan": self.name, "stock_entry_type": "Material Issue", "docstatus": 1},
            "name",
        )
        if not issue_name:
            frappe.throw("Stock Entry Issue untuk Surat Jalan ini tidak ditemukan.")

        issue = frappe.get_doc("Stock Entry", issue_name)

        receipt = frappe.new_doc("Stock Entry")
        receipt.stock_entry_type  = "Material Receipt"
        receipt.surat_jalan       = self.name
        receipt.posting_date      = tanggal_terima
        receipt.company           = issue.company
        receipt.project           = issue.project

        for issue_item in issue.items:
            receipt.append("items", {
                "item_code":          issue_item.item_code,
                "item_name":          issue_item.item_name,
                "description":        issue_item.description,
                "qty":                issue_item.qty,
                "uom":                issue_item.uom,
                "stock_uom":          issue_item.stock_uom,
                "conversion_factor":  issue_item.conversion_factor,
                "t_warehouse":        self.gudang_tujuan,
                "s_warehouse":        None,
                # Pakai valuation_rate dari issue agar nilai konsisten
                "basic_rate":         issue_item.valuation_rate,
                "allow_zero_valuation_rate": 0,
            })

        receipt.run_method("set_missing_values")
        
        proc_settings = frappe.get_single("Procurement Settings")
        expense_account = ""

        for row in proc_settings.persediaan_dalam_perjalanan_procurement_settings:
            if row.company == self.company:
                expense_account = row.account

        for row in receipt.items:
            if expense_account:
                row.expense_account = expense_account

        receipt.insert()
        receipt.submit()

        # Update status & simpan tanggal terima di Surat Jalan
        self.db_set("status", "Diterima")
        self.db_set("tanggal_diterima", tanggal_terima)

        return receipt.name

@frappe.whitelist()
def get_items_from_po(doctype):
	pass


@frappe.whitelist()
def get_stock_item(item_code,warehouse):
	return frappe.db.sql("""
		SELECT
			i.item_code,
			i.item_name,
			COALESCE(b.actual_qty, 0) AS stock,
			i.stock_uom AS uom
		FROM `tabItem` i
		LEFT JOIN `tabBin` b
			ON b.item_code = i.item_code
		AND b.warehouse = %s
		WHERE i.item_code = %s;
	""",[warehouse,item_code],as_dict=True, debug=True)

@frappe.whitelist()
def map_from_po(source_name, target_doc=None, args=None):

	def select_item(d):
		filtered_items = args.get("filtered_children",[])
		return d.name in filtered_items

	def postprocess(source,target):
		pass
	
	def update_item(source,target,source_parent):
		target.no_po = source_parent.name
		target.no_penerimaan = frappe.db.get_value("Purchase Receipt",{"purchase_order": source_parent.name})

	doclist = get_mapped_doc(
		"Purchase Order",
		source_name,
		{
			"Purchase Order": {
				"doctype": "Surat Jalan",
			},
			"Purchase Order Item": {
				"doctype": "Surat Jalan Item",
				"field_map": [
					["item_code", "kode_barang"],
					["item_name", "nama_barang"],
					["qty", "jumlah"],
					["uom", "satuan"],
					["material_request","no_purchase_request"]
				],
				"condition": select_item,
				"postprocess": update_item
			},
		},
		target_doc,postprocess=postprocess
	)

	return doclist