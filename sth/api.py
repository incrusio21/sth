import frappe,json
from frappe.utils import now,flt,cint
from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
from erpnext.stock.get_item_details import get_item_details
from sth.utils import decrypt

@frappe.whitelist(allow_guest=True)
def create_sq():
    data = frappe.form_dict
    invalidMessage = validate_request(data)
    if invalidMessage: 
        frappe.local.response["http_status_code"] = 422
        return invalidMessage
    
    rfq_name = decrypt(data.get("rfq"))
    items_data = json.loads(data.get("items"))

    doc_sq = make_supplier_quotation_from_rfq(rfq_name,for_supplier=data.get("supplier"))
    doc_sq.custom_file_upload = f"/private/files/{data.file_url}"
    doc_sq.valid_till = data.get('valid_date')
    doc_sq.terms = data.get('terms')
    doc_sq.custom_required_by = data.get('estimated_date')

    doc_sq.custom_material_request = doc_sq.items[0].material_request
    doc_sq.items = []

    doc_sq.append("upload_file_penawaran",{
        "file_upload": f"/private/files/{data.file_url}"
    })


    for idx,item in enumerate(items_data.get("item_code")):
        item_details = get_item_details({"item_code":item,"company": doc_sq.company,"doctype": doc_sq.doctype,"conversion_rate":doc_sq.conversion_rate})

        child = doc_sq.append("items")
        child.update(item_details)
        child.description = items_data["desc"][idx]
        child.custom_country = items_data["country"][idx]
        child.custom_merk = items_data["merk"][idx]
        child.rate = items_data["rate"][idx]
        child.qty = items_data["qty"][idx]
        child.request_for_quotation = rfq_name
    
    doc_sq.taxes = []
    charges_and_discount = json.loads(data.get("charges_and_discount"))


    taxes_template = frappe.get_doc("Purchase Taxes and Charges Template",{"title":"STH TAX AND CHARGE", "company":doc_sq.company})
    list_tax = taxes_template.taxes
    for tax in list_tax:
        if "VAT" not in tax.account_head:
            child  = doc_sq.append("taxes")
            child.charge_type = tax.charge_type
            child.account_head = tax.account_head
            child.description = tax.description
            if "6511003" in tax.account_head:
                child.tax_amount = charges_and_discount.get('ongkos_angkut')

            elif "2132001" in tax.account_head:
                child.rate = charges_and_discount.get('ppn_ongkos_angkut')
                child.row_id = cint(tax.row_id) - 1
            elif "2139001" in tax.account_head:
                child.tax_amount = charges_and_discount.get('pbbkb')

            elif "2131002" in tax.account_head:
                child.tax_amount = charges_and_discount.get('pph_22')
        
    doc_sq.apply_discount_on = "Net Total"
    doc_sq.additional_discount_percentage = flt(charges_and_discount.get('discount'))

    doc_sq.insert()
    frappe.db.commit()
    return {
        "doctype": doc_sq.doctype,
        "docname": doc_sq.name,
    }


def debug_taxes():
    doc_sq = frappe.new_doc("Supplier Quotation")
    doc_sq.company = "PT. TRIMITRA LESTARI"
    taxes_template = frappe.get_doc("Purchase Taxes and Charges Template",{"title":"STH TAX AND CHARGE", "company":doc_sq.company})
    list_tax = taxes_template.taxes

    for tax in list_tax:
        if "VAT" not in tax.account_head:
            child  = doc_sq.append("taxes")
            child.charge_type = tax.charge_type
            child.account_head = tax.account_head
            if "6511003" in tax.account_head:
                child.tax_amount = ""

            elif "2132001" in tax.account_head:
                child.rate = ""
                child.row_id = tax.row_id
            elif "2139001" in tax.account_head:
                child.tax_amount = ""

            elif "2131002" in tax.account_head:
                child.tax_amount = ""

    return doc_sq

def validate_request(data):
    message = []
    req_data = ["rfq","supplier","file_url"]
    title_alias = {"file_url": "File upload"}

    for row in req_data:
        if not data.get(row):
            message.append("{} is required".format(title_alias[row] or row.replace('_'," ").capitalize()))    

    # if not data.get("rfq"):
    #     message.append("RFQ is required")

    # if not data.get("supplier"):
    #     message.append("Supplier is required")
        
    
    if not json.loads(data.get("items")):
        message.append("Items is required")
    
    # if not data.get("file_url"):
    #     message.append("File upload is required")
    
    return message

@frappe.whitelist()
def get_doc_ignore_perm(doctype, name):
    return frappe.get_doc(doctype, name, ignore_permissions=True)

@frappe.whitelist()
def get_table_data(args):
    args = frappe._dict(json.loads(args) or '{}')
    if not args.pr_sr:
        return {
            "suppliers": [],
            "data": [],
        }

    where_clause = "WHERE sq.workflow_state = 'Open' AND (sqi.`request_for_quotation` = %(pr_sr)s OR sq.custom_material_request = %(pr_sr)s) "
    filters = {"pr_sr":args.pr_sr}
    
    if args.item_name:
        where_clause += " AND sqi.item_name LIKE %(item_name)s"
        filters["item_name"] = f"%{args.item_name}%"

    query = frappe.db.sql(f"""
        SELECT DENSE_RANK() OVER (ORDER BY sqi.item_code) AS idx, sq.name AS doc_no, sqi.name as item_id ,sqi.item_code as kode_barang, sqi.item_name nama_barang, i.`last_purchase_rate` AS harga_terakhir,i.`stock_uom` as satuan, sqi.`custom_merk` as merk, sqi.`custom_country` as country,sqi.`description` as spesifikasi,sqi.`qty` as jumlah, sqi.`rate` as harga, sqi.`amount` as sub_total, sq.`supplier`
        FROM `tabSupplier Quotation` sq
        JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
        JOIN `tabItem` i ON i.`name` = sqi.`item_code`
        {where_clause}
        ORDER BY sqi.`item_code`,sq.`supplier`,sq.`name`;
    """,filters,as_dict=True)

    static_fields = ["idx","kode_barang","nama_barang","satuan","harga_terakhir"]
    supplier_fields = ["merk","country","spesifikasi","jumlah","harga","sub_total","doc_no"]
    result = []
    item_code = ""
    for data in query:
        title = "".join(kata[0].lower() for kata in data.supplier.split())
        dict_data = frappe._dict({})
        if item_code == data.kode_barang:
            index = None
            for idx,d in enumerate(result):
                if not getattr(d,f"{title}_spesifikasi",None) and d.mark == data.kode_barang:
                    index = idx
                    break
            if index is not None:
                for sup_field in supplier_fields:
                    result[index][f"{title}_{sup_field}"] = data[sup_field]
            else:
                for st_field in static_fields:
                    dict_data[st_field] = ""
            
                # field mapping untuk colgroup supplier
                for sup_field in supplier_fields:
                    dict_data[f"{title}_{sup_field}"] = data[sup_field]                
                
                dict_data.mark = data.kode_barang
                result.append(dict_data)
        else:
            for st_field in static_fields:
                dict_data[st_field] = data[st_field]
            
            # field mapping untuk colgroup supplier
            for sup_field in supplier_fields:
                dict_data[f"{title}_{sup_field}"] = data[sup_field]

            dict_data.mark = data.kode_barang

            result.append(dict_data)
        item_code = data.kode_barang
        # print(result)
        # print("==========================================================================")
        # print("==========================================================================")

    return {
        "suppliers": set([r.supplier for r in query]),
        "data": result,
    }

@frappe.whitelist()
def submit_sq(name):
    doc = get_doc_ignore_perm("Supplier Quotation",name)
    doc.submit()

@frappe.whitelist()
def return_status_absensi():

    status_attendance = ["Present", "Absent", "Work From Home", "7th Day Off"]

    lis = frappe.db.sql(""" SELECT name FROM `tabLeave Type` """)
    for row in lis:
        status_attendance.append(row[0])

    return status_attendance