import frappe,json
from frappe.utils import now,flt,cint,today
from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
from erpnext.stock.get_item_details import get_item_details
from sth.utils import decrypt
from sth.custom.supplier_quotation import get_taxes_template

@frappe.whitelist(allow_guest=True)
def create_sq():
	data = frappe.form_dict
	invalidMessage = validate_request(data)
	if invalidMessage: 
		frappe.local.response["http_status_code"] = 422
		return invalidMessage
	
	map_tax = {
		"Ongkos Angkut":"ongkos_angkut",
		"PPH 22":"pph_22",
		"PBBKB":"pbbkb"
	}

	charges_and_discount = json.loads(data.get("charges_and_discount"))

	rfq_name = decrypt(data.get("rfq"))
	items_data = json.loads(data.get("items"))

	doc_sq = make_supplier_quotation_from_rfq(rfq_name,for_supplier=data.get("supplier"))
	doc_sq.custom_file_upload = f"/private/files/{data.file_url}"
	doc_sq.valid_till = data.get('valid_date')
	doc_sq.terms = data.get('terms')
	doc_sq.keterangan = data.get('keterangan')
	doc_sq.custom_required_by = data.get('estimated_date')
	doc_sq.alamat = frappe.db.get_value("Unit",doc_sq.lokasi_pengiriman,"address")

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

	doc_sq.biaya_ongkos = charges_and_discount.get('ongkos_angkut')
	doc_sq.ppn_biaya_ongkos = charges_and_discount.get('ppn_ongkos_angkut')
	doc_sq.is_ppn_ongkos = True if doc_sq.ppn_biaya_ongkos > 0 else False
	doc_sq.total_biaya_ongkos_angkut = doc_sq.biaya_ongkos + (doc_sq.biaya_ongkos * doc_sq.ppn_biaya_ongkos/100 )
	doc_sq.is_pph_22 = True
	doc_sq.pph_22 = charges_and_discount.get('pph_22')
	doc_sq.pbbkb = charges_and_discount.get('pbbkb')

	doc_sq.taxes = []
	tax_template = get_taxes_template(doc_sq.company)
	for row in tax_template:
		field_name = map_tax[row.type]

		taxes  = doc_sq.append("taxes")
		taxes.account_head = row.account
		taxes.add_deduct_tax = "Add"
		taxes.charge_type = "Actual"
		taxes.description = frappe.get_cached_value("Account", row.account, "account_name")
		if field_name != "ongkos_angkut":
			taxes.tax_amount = charges_and_discount.get(field_name)
		else:
			taxes.tax_amount = doc_sq.biaya_ongkos + (doc_sq.biaya_ongkos * doc_sq.ppn_biaya_ongkos/100 )

	doc_sq.biaya_ongkos = charges_and_discount.get('ongkos_angkut')
	doc_sq.ppn_biaya_ongkos = charges_and_discount.get('ppn_ongkos_angkut')
	doc_sq.is_ppn_ongkos = True if doc_sq.ppn_biaya_ongkos > 0 else False
	doc_sq.total_biaya_ongkos_angkut = doc_sq.biaya_ongkos + (doc_sq.biaya_ongkos * doc_sq.ppn_biaya_ongkos/100 )
	doc_sq.is_pph_22 = True
	doc_sq.pph_22 = charges_and_discount.get('pph_22')
	doc_sq.pbbkb = charges_and_discount.get('pbbkb')

	doc_sq.apply_discount_on = "Net Total"
	doc_sq.additional_discount_percentage = flt(charges_and_discount.get('discount'))
	
	doc_sq.insert()
	frappe.db.commit()
	return {
		"doctype": doc_sq.doctype,
		"docname": doc_sq.name,
	}


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

# Method for komparasi penawaran harga
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

	if args.list_sq:
		where_clause += " AND sq.name IN %(supplier_quotation)s"
		filters["supplier_quotation"] = args.list_sq

	query = frappe.db.sql(f"""
		SELECT DENSE_RANK() OVER (ORDER BY sqi.item_code) AS idx, sq.name AS doc_no, sqi.name as item_id ,sqi.item_code as kode_barang, sqi.item_name nama_barang, i.`last_purchase_rate` AS harga_terakhir,i.`stock_uom` as satuan, sqi.`custom_merk` as merk, sqi.`custom_country` as country,sqi.`description` as spesifikasi,sqi.`qty` as jumlah, sqi.`rate` as harga, sqi.`amount` as sub_total, sq.`supplier`,sqi.name as child_name
		FROM `tabSupplier Quotation` sq
		JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		JOIN `tabItem` i ON i.`name` = sqi.`item_code`
		{where_clause}
		ORDER BY sqi.`item_code`,sq.`supplier`,sq.`name`;
	""",filters,as_dict=True)

	static_fields = ["idx","kode_barang","nama_barang","satuan","harga_terakhir"]
	supplier_fields = ["merk","country","spesifikasi","jumlah","harga","sub_total","doc_no","child_name"]
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
def get_sq_item_details(names):
	names = json.loads(names)

	if not names:
		return []

	return frappe.db.sql("""
		select sqi.item_code, sqi.item_name,sqi.custom_merk as merek,sqi.custom_country as country, sqi.description, sqi.qty, sqi.rate, sqi.amount, sq.name as doc_no
		from `tabSupplier Quotation Item` sqi
		join `tabSupplier Quotation` sq on sq.name = sqi.parent
		where sqi.name in %(names)s
	""",{"names":names},as_dict=True)

@frappe.whitelist()
def submit_sq(name):
	doc = get_doc_ignore_perm("Supplier Quotation",name)
	doc.submit()

# create sq from comparasion
@frappe.whitelist()
def comparasion_create_sq(items):
	items = json.loads(items)
	doc_sq = frappe.get_doc('Supplier Quotation',items[0]["doc_no"])
	warehouse = doc_sq.items[0].warehouse

	copy_doc = frappe.copy_doc(doc_sq)
	copy_doc.transaction_date = today()
	copy_doc.valid_till = today()
	copy_doc.status = "Draft"
	copy_doc.items = []
	for item in items:
		item_details = get_item_details({"item_code":item['item_code'],"company": copy_doc.company,"doctype": copy_doc.doctype,"conversion_rate":copy_doc.conversion_rate})

		child = copy_doc.append("items")
		child.update(item_details)
		child.description = item["description"]
		child.custom_country = item["country"]
		child.custom_merk = item["merek"]
		child.rate = item["rate"]
		child.qty = item["qty"]
		child.warehouse = warehouse
		child.material_request = copy_doc.custom_material_request

	copy_doc.insert()
	return copy_doc.name
# End

@frappe.whitelist()
def return_status_absensi():
	status_attendance = [
		{"name": "Present", "status_code": "H"},
		{"name": "Absent", "status_code": "M"},
		{"name": "Work From Home", "status_code": "WFH"},
		{"name": "7th Day Off", "status_code": "L"}
	]
	
	lis = frappe.db.sql(""" SELECT name, status_code FROM `tabLeave Type` """, as_dict=True)
	
	for row in lis:
		status_attendance.append({
			"name": row.name,
			"status_code": row.status_code
		})
	
	return status_attendance
