import frappe

from sth.mill.doctype.timbangan.timbangan import perbarui_sisa_do_timbangan

def update_ke_stock_in_transit_account(self,method):
	doc = frappe.get_single('STH Stock Settings')
	expense_accoun = ''
	for company_baris in doc.sth_stock_settings_table:
		if company_baris.company == self.company:
			expense_accoun = company_baris.stock_in_transit_account

	for row in self.items:
		row.expense_account = expense_accoun

def update_kontrak_penjualan(self,method):
	doi = ""
	for row in self.items:
		if doi == "":
			doi = row.delivery_order_item

	if not doi:
		return

	do = frappe.db.get_value("Delivery Order Item",doi,'parent')
	do_doc = frappe.get_doc("Delivery Order",do)

	sales_order = do_doc.sales_order
	no_kontrak_external = frappe.db.get_value("Sales Order", sales_order, "no_kontrak_external") or ""

	self.sales_order = sales_order
	self.no_kontrak_external = no_kontrak_external

def debug():
	sel = frappe.get_doc("Delivery Note","MAT-DN-2026-00023")
	update_kontrak_penjualan(sel,"validate")
	sel.db_update()


def update_delivered_do(self,method):
	for item in self.items:
		# Baris yang tidak berasal dari Delivery Order tidak punya acuan yang mau
		# ditambah, mis. DN yang dibuat manual tanpa DO.
		if not item.delivery_order_item:
			continue

		delivered_qty = frappe.db.get_value("Delivery Order Item",item.delivery_order_item,'delivered_qty') or 0
		if method == "before_submit":
			qty_final = delivered_qty + item.qty
		elif method == "before_cancel":
			qty_final = delivered_qty - item.qty
		
		frappe.db.set_value("Delivery Order Item",item.delivery_order_item,"delivered_qty",qty_final)

		# Sisa DO yang tampil di Timbangan ikut ditulis ulang. Field itu Data read
		# only yang dulu cuma diisi JS waktu timbangannya dibuat, jadi tiap DN
		# berikutnya membuat angkanya makin jauh dari delivered_qty yang barusan
		# berubah di atas.
		do_no, item_code = frappe.db.get_value(
			"Delivery Order Item", item.delivery_order_item, ["parent", "item_code"]
		)
		perbarui_sisa_do_timbangan(do_no, item_code)


def create_kriteria_upload_document(doc, method):

    if not doc.timbangan_ref:
        return

    if frappe.db.exists("Kriteria Upload Document", {
        "voucher_type": "Delivery Note",
        "voucher_no": doc.name
    }):
        return

    kud_name = frappe.db.get_value(
        "Kriteria Upload Document",
        {"voucher_type": "Timbangan", "voucher_no": doc.timbangan_ref},
        "name"
    )

    if not kud_name:
        return

    sumber_kud = frappe.get_doc("Kriteria Upload Document", kud_name)

    kud = frappe.new_doc("Kriteria Upload Document")
    kud.voucher_type = "Delivery Note"
    kud.voucher_no = doc.name

    for row in sumber_kud.file_upload:
        kud.append("file_upload", {
            "rincian_dokumen_finance": row.rincian_dokumen_finance,
            "upload_file": row.upload_file
        })

    kud.insert(ignore_permissions=True)