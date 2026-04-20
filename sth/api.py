import frappe,json
from frappe.utils import now,flt,cint,today
from erpnext.buying.doctype.request_for_quotation.request_for_quotation import make_supplier_quotation_from_rfq
from erpnext.stock.get_item_details import get_item_details
from sth.utils import decrypt
from sth.custom.supplier_quotation import get_taxes_template,close_status_another_sq,close_rfq

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
		"PBBKB":"pbbkb",
		"Cost": "cost"
	}

	charges_and_discount = json.loads(data.get("charges_and_discount"))

	rfq_name = decrypt(data.get("rfq"))
	items_data = json.loads(data.get("items"))

	doc_sq = make_supplier_quotation_from_rfq(rfq_name,for_supplier=data.get("supplier"))
	doc_sq.custom_file_upload = f"/private/files/{data.file_url}"
	doc_sq.valid_till = data.get('valid_date')
	doc_sq.syarat_pembayaran = data.get("syarat_pembayaran")
	# doc_sq.custom_required_by = data.get('estimated_date')
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


	doc_sq.biaya_ongkos = flt(charges_and_discount.get('ongkos_angkut'))
	doc_sq.ppn_biaya_ongkos = flt(charges_and_discount.get('ppn_ongkos_angkut'))
	doc_sq.is_ppn_ongkos = True if doc_sq.ppn_biaya_ongkos > 0.0 else False
	doc_sq.total_biaya_ongkos_angkut = flt(doc_sq.biaya_ongkos) + (doc_sq.biaya_ongkos * doc_sq.ppn_biaya_ongkos/100 )
	doc_sq.is_pph_22 = True
	doc_sq.pph_22 = flt(charges_and_discount.get('pph_22'))
	doc_sq.pbbkb = flt(charges_and_discount.get('pbbkb'))

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

	doc_sq.apply_discount_on = "Net Total"
	doc_sq.additional_discount_percentage = flt(charges_and_discount.get('discount'))
	
	doc_sq.insert(ignore_mandatory=True)
	frappe.db.set_value(doc_sq.doctype,doc_sq.name,"workflow_state","Need To Compare")
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
	
	if not json.loads(data.get("items")):
		message.append("Items is required")

	if flt(data.get("gt_value")) == 0:
		message.append("Grand total harus lebih besar dari 0")

	items_data = json.loads(data.get("items"))

	for idx,item in enumerate(items_data.get("item_code")):
		if flt(items_data["rate"][idx]) == 0.0:
			message.append("Harga {} harus lebih besar dari 0".format(items_data["item_name"][idx]))
			break
	
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

	where_clause = "WHERE sq.workflow_state NOT IN ('Approved','Closed') AND sq.custom_material_request = %(pr_sr)s "
	filters = {"pr_sr":args.pr_sr}
	
	if args.item_name:
		where_clause += " AND sqi.item_name LIKE %(item_name)s"
		filters["item_name"] = f"%{args.item_name}%"

	if args.list_sq:
		where_clause += " AND sq.name IN %(supplier_quotation)s"
		filters["supplier_quotation"] = args.list_sq

	query = frappe.db.sql(f"""
		SELECT DENSE_RANK() OVER (ORDER BY sqi.item_code) AS idx, sq.name AS doc_no, sq.status, sq.workflow_state ,sqi.name as item_id ,sqi.item_code as kode_barang, sqi.item_name nama_barang, i.`last_purchase_rate` AS harga_terakhir,i.`stock_uom` as satuan, sqi.notes as notes_sq,sqi.`custom_merk` as merk, sqi.`custom_country` as country,sqi.`description` as spesifikasi,sqi.`qty` as jumlah, sqi.`rate` as harga, sqi.`amount` as sub_total, s.supplier_name as supplier ,sqi.name as child_name
		FROM `tabSupplier Quotation` sq
		JOIN `tabSupplier Quotation Item` sqi ON sqi.parent = sq.name
		JOIN `tabSupplier` s on s.name = sq.supplier
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
				
				result[index][f"{title}_status"] = data.status
				result[index][f"{title}_workflow_state"] = data.workflow_state
			else:
				for st_field in static_fields:
					dict_data[st_field] = ""
			
				# field mapping untuk colgroup supplier
				for sup_field in supplier_fields:
					dict_data[f"{title}_{sup_field}"] = data[sup_field]                
				
				dict_data.notes_pr_sr, asset = frappe.get_value("Material Request Item",{"parent":args.pr_sr,"item_code":data.kode_barang},["notes","kendaraan as asset"])
				dict_data.asset = frappe.get_value("Alat Berat Dan Kendaraan",asset,"no_pol")
				dict_data[f"{title}_status"] = data.status
				dict_data[f"{title}_workflow_state"] = data.workflow_state

				dict_data.notes_sq = data.notes_sq
				dict_data.mark = data.kode_barang
				result.append(dict_data)
		else:
			for st_field in static_fields:
				dict_data[st_field] = data[st_field]
			
			# field mapping untuk colgroup supplier
			for sup_field in supplier_fields:
				dict_data[f"{title}_{sup_field}"] = data[sup_field]

			dict_data.notes_pr_sr, asset = frappe.get_value("Material Request Item",{"parent":args.pr_sr,"item_code":data.kode_barang},["notes","kendaraan as asset"])
			dict_data.asset = frappe.get_value("Alat Berat Dan Kendaraan",asset,"no_pol")
			dict_data.notes_sq = data.notes_sq
			dict_data[f"{title}_status"] = data.status
			dict_data[f"{title}_workflow_state"] = data.workflow_state

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
		select sqi.item_code, sqi.item_name,sqi.custom_merk as merek,sqi.custom_country as country, 
		sqi.description, sqi.qty, sqi.rate, sqi.amount, sq.name as doc_no,sq.supplier
		from `tabSupplier Quotation Item` sqi
		join `tabSupplier Quotation` sq on sq.name = sqi.parent
		where sqi.name in %(names)s
	""",{"names":names},as_dict=True)

@frappe.whitelist()
def submit_sq(name):
	doc = get_doc_ignore_perm("Supplier Quotation",name)
	doc.submit()

@frappe.whitelist()
def comparasion_create_sq(pr_sr,items):
	items = json.loads(items)
	if not items:
		return
	
	except_name = []

	def init_new_doc(name):
		doc_sq = frappe.get_doc('Supplier Quotation',name)
		warehouse = doc_sq.items[0].warehouse
		copy_doc = frappe.copy_doc(doc_sq)
		copy_doc.transaction_date = today()
		copy_doc.valid_till = today()
		copy_doc.status = "Draft"
		copy_doc.items = []
		copy_doc.workflow_state = "Draft"
		
		return copy_doc,warehouse,name

	new_doc,warehouse,ref_name = init_new_doc(items[0]["doc_no"])
	for idx,item in enumerate(items):
		if ref_name != item['doc_no'] :
			new_doc.insert()
			new_doc.submit()
			frappe.db.set_value(new_doc.doctype,new_doc.name,"workflow_state","Approved")
			except_name.append(new_doc.name)
			new_doc,warehouse,ref_name = init_new_doc(item['doc_no'])

		item_details = get_item_details({"item_code":item['item_code'],"company": new_doc.company,"doctype": new_doc.doctype,"conversion_rate":new_doc.conversion_rate})
		
		child = new_doc.append("items")
		child.update(item_details)
		child.description = item["description"]
		child.custom_country = item["country"]
		child.custom_merk = item["merek"]
		child.rate = item["rate"]
		child.qty = item["qty"]
		child.warehouse = warehouse
		child.material_request = new_doc.custom_material_request

	new_doc.insert(ignore_mandatory=True)
	new_doc.submit()
	except_name.append(new_doc.name)

	close_status_another_sq([pr_sr],except_name)

	rfq = frappe.db.get_all("Request for Quotation Item",{"material_request": pr_sr},["parent"],group_by='parent',pluck='parent')
	for row in rfq :
		close_rfq(row)
		
	return new_doc.name

def debug_create_po():
	pr_sr = "MAT-MR-2025-00006"
	items = [
		{
			"amount": 300000,
			"country": "Indonesia",
			"description": "KUNCI PAS",
			"doc_no": "PUR-SQTN-2025-00005",
			"idx": 1,
			"item_code": "KUNCI PAS",
			"item_name": "KUNCI PAS",
			"merek": "ABC",
			"qty": 200,
			"rate": 1500,
			"supplier": "PT. Bibit Sawit Indonesia"
		},
		{
			"amount": 5000000,
			"country": "Indonesia",
			"description": "Grease",
			"doc_no": "PUR-SQTN-2025-00007",
			"idx": 2,
			"item_code": "Grease",
			"item_name": "Grease",
			"merek": "aswww",
			"qty": 2000,
			"rate": 2500,
			"supplier": "PT. Spindo Steel"
		}
	]

	comparasion_create_sq(pr_sr,json.dumps(items))

# End Method for komparasi

@frappe.whitelist()
def return_status_absensi():
	status_attendance = [
		{"name": "Present", "status_code": "H", "deskripsi": "Present", "jenis": "DIBAYAR", "jumlah_hk": 1, "is_penalty": 0, "status": "Aktif", "owner" : "Administrator", "creation": "01-01-2026 00:00:00", "modified_by" : "Administrator", "modified": "01-01-2026 00:00:00"},
		{"name": "Absent", "status_code": "M", "deskripsi": "Absent", "jenis": "TIDAK_DIBAYAR", "jumlah_hk": 0, "is_penalty": 1, "status": "Aktif", "owner" : "Administrator", "creation": "01-01-2026 00:00:00", "modified_by" : "Administrator", "modified": "01-01-2026 00:00:00"},
		{"name": "Work From Home", "status_code": "WFH", "deskripsi": "Work From Home", "jenis": "DIBAYAR", "jumlah_hk": 1, "is_penalty": 0, "status": "Aktif", "owner" : "Administrator", "creation": "01-01-2026 00:00:00", "modified_by" : "Administrator", "modified": "01-01-2026 00:00:00"},
		{"name": "7th Day Off", "status_code": "L", "deskripsi": "7th Day Off", "jenis": "TIDAK_DIBAYAR", "jumlah_hk": 0, "is_penalty": 1, "status": "Aktif", "owner" : "Administrator", "creation": "01-01-2026 00:00:00", "modified_by" : "Administrator", "modified": "01-01-2026 00:00:00"}
	]
	
	lis = frappe.db.sql(""" SELECT name, status_code, deskripsi, is_lwp, owner, creation, modified_by, modified FROM `tabLeave Type` """, as_dict=True)
	
	for row in lis:
		status_attendance.append({
			"name": row.name,
			"status_code": row.status_code,
			"deskripsi": row.deskripsi,
			"jenis": "TIDAK_DIBAYAR" if row.is_lwp == 1 else "DIBAYAR",
			"jumlah_hk": 0,
			"is_penalty": 1 if row.is_lwp == 1 else 0,
			"status": "Aktif",
			"owner": row.owner,
			"creation": row.creation,
			"modified_by": row.modified_by,
			"modified": row.modified
		})
	
	return status_attendance


@frappe.whitelist()
def get_stock_item(item_code,warehouse):
	return frappe.db.get_value("Bin",{"warehouse":warehouse,"item_code":item_code},"actual_qty")

@frappe.whitelist()
def get_pdo_detail_dana_cadangan(pdo_name):
	return frappe.db.sql("""
		SELECT
			pdo.name,
			pdo.posting_date,
			pdct.jenis,
			pdct.amount as estimate_unit,
			pdct.revised_amount as estimate_revise
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Dana Cadangan Table` pdct ON pdct.parent = pdo.name
		JOIN `tabPermintaan Dana Operasional` ref 
			ON ref.name = %s

		WHERE pdo.posting_date BETWEEN 
				DATE_SUB(ref.posting_date, INTERVAL 5 MONTH)
				AND ref.posting_date
				AND pdo.unit = ref.unit
		ORDER BY pdo.name, pdo.posting_date;
	""", (pdo_name,), as_dict=1)

@frappe.whitelist()
def get_pdo_detail_kas(pdo_name):
	return frappe.db.sql("""
		SELECT
				pdo.name,
				pdo.posting_date,
				ect.custom_pdo_type as jenis_kas,
				e.employee_name as pengguna,
				d.designation_name as jabatan,
				pkt.type as item_barang,
				pkt.uom as satuan,
				pkt.qty as qty,
				pkt.price as harga,
				pkt.revised_qty as qty_revisi,
				pkt.revised_price as harga_revisi,
				pkt.needs as kebutuhan,
				pkt.total as estimate_unit,
				pkt.revised_total as estimate_revise
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Kas Table` pkt ON pkt.parent = pdo.name
		JOIN `tabExpense Claim Type` ect ON ect.name = pkt.`type`
		LEFT JOIN `tabEmployee` e ON e.name = pkt.employee 
		LEFT JOIN `tabDesignation` d ON d.name = e.designation 
		JOIN `tabPermintaan Dana Operasional` ref 
			ON ref.name = %s

		WHERE pdo.posting_date BETWEEN 
				DATE_SUB(ref.posting_date, INTERVAL 5 MONTH)
				AND ref.posting_date
				AND pdo.unit = ref.unit
		ORDER BY pdo.name, pdo.posting_date;
	""", (pdo_name,), as_dict=1)

@frappe.whitelist()
def get_pdo_detail_perjalanan_dinas(pdo_name):
	return frappe.db.sql("""
		SELECT
			pdo.name,
			pdo.posting_date,
			ppdt.employee as pengguna,
			ppdt.license_plate_number as no_polisi,
			ppdt.`type` as jenis,
			ppdt.hari_dinas as hari_dinas,
			ppdt.plafon as plafon,
			ppdt.revised_duty_day as hari_dinas_revisi,
			ppdt.revised_plafon as plafon_revisi,
			ppdt.needs as keperluan,
			ppdt.total as estimate_unit,
			ppdt.revised_total as estimate_revise
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Perjalanan Dinas Table` ppdt ON ppdt.parent = pdo.name
		JOIN `tabPermintaan Dana Operasional` ref 
			ON ref.name = %s

		WHERE pdo.posting_date BETWEEN 
				DATE_SUB(ref.posting_date, INTERVAL 5 MONTH)
				AND ref.posting_date
				AND pdo.unit = ref.unit
		ORDER BY pdo.name, pdo.posting_date;
	""", (pdo_name,), as_dict=1)

@frappe.whitelist()
def get_pdo_detail_bahan_bakar(pdo_name):
	return frappe.db.sql("""
		SELECT
			pdo.name,
			pdo.posting_date,
			pbbt.employee as pengguna,
			d.designation_name as jabatan,
			pbbt.plafon as plafon,
			pbbt.unit_price as harga,
			pbbt.revised_plafon as plafon_revisi,
			pbbt.revised_unit_price as harga_revisi,
			pbbt.needs as keperluan,
			pbbt.price_total as estimate_unit,
			pbbt.revised_price_total as estimate_revise
		FROM `tabPermintaan Dana Operasional` pdo
		JOIN `tabPDO Bahan Bakar Table` pbbt ON pbbt.parent = pdo.name
		LEFT JOIN `tabEmployee` e ON e.employee_name = pbbt.employee
		LEFT JOIN `tabDesignation` d ON d.name = e.designation
		JOIN `tabPermintaan Dana Operasional` ref 
			ON ref.name = %s

		WHERE pdo.posting_date BETWEEN 
				DATE_SUB(ref.posting_date, INTERVAL 5 MONTH)
				AND ref.posting_date
				AND pdo.unit = ref.unit
		ORDER BY pdo.name, pdo.posting_date;
	""", (pdo_name,), as_dict=1)

@frappe.whitelist()
def get_previous_kriteria_documents(doctype, docname):

	DOC_LABEL = {
		"Sales Order": "Kontrak Penjualan",
		"Delivery Order": "Delivery Order",
		"Delivery Note": "Delivery Note",
		"Sales Invoice": "Pengakuan Penjualan",
		
		"Material Request": "PR/SR",
		"Supplier Quotation": "Supplier Quotation",
		"Purchase Order": "Purchase Order",
		"Purchase Receipt": "Purchase Receipt",
		"Purchase Invoice": "Purchase Invoice"
	}

	chain = []

	if doctype == "Material Request":
		doc = frappe.get_doc(doctype, docname)
		chain.append({
			"voucher_type": "Berita Acara",
			"voucher_no": doc.berita_acara
		})

	elif doctype == "Supplier Quotation":
		doc = frappe.get_doc(doctype, docname)
		
		berita_acaras = list({row.material_request for row in doc.items if row.material_request})
		for prev_1_name in berita_acaras:

			chain.append({
				"voucher_type": "Material Request",
				"voucher_no": prev_1_name
			})

			prev_1_doc = frappe.get_doc("Material Request", prev_1_name)

			chain.append({
				"voucher_type": "Berita Acara",
				"voucher_no": prev_1_doc.berita_acara
			})

	elif doctype == "Purchase Order":
		doc = frappe.get_doc(doctype, docname)
		
		supplier_quotations = list({row.supplier_quotation for row in doc.items if row.supplier_quotation})
		for prev_2_name in supplier_quotations:
			chain.append({
				"voucher_type": "Supplier Quotation",
				"voucher_no": prev_2_name
			})

			prev_2_doc = frappe.get_doc("Supplier Quotation", prev_2_name)

			berita_acaras = list({row.material_request for row in prev_2_doc.items if row.material_request})
			for prev_1_name in berita_acaras:

				chain.append({
					"voucher_type": "Material Request",
					"voucher_no": prev_1_name
				})

				prev_1_doc = frappe.get_doc("Material Request", prev_1_name)

				chain.append({
					"voucher_type": "Berita Acara",
					"voucher_no": prev_1_doc.berita_acara
				})

	elif doctype == "Purchase Receipt":

		doc = frappe.get_doc(doctype, docname)
		purchase_orders = list({row.purchase_order for row in doc.items if row.purchase_order})

		for prev_3_name in purchase_orders:
			chain.append({
				"voucher_type": "Purchase Order",
				"voucher_no": prev_3_name
			})
			prev_3_doc = frappe.get_doc("Purchase Order", prev_3_name)

			supplier_quotations = list({row.supplier_quotation for row in prev_3_doc.items if row.supplier_quotation})
			for prev_2_name in supplier_quotations:
				chain.append({
					"voucher_type": "Supplier Quotation",
					"voucher_no": prev_2_name
				})

				prev_2_doc = frappe.get_doc("Supplier Quotation", prev_2_name)

				berita_acaras = list({row.material_request for row in prev_2_doc.items if row.material_request})
				for prev_1_name in berita_acaras:

					chain.append({
						"voucher_type": "Material Request",
						"voucher_no": prev_1_name
					})

					prev_1_doc = frappe.get_doc("Material Request", prev_1_name)

					chain.append({
						"voucher_type": "Berita Acara",
						"voucher_no": prev_1_doc.berita_acara
					})

	elif doctype == "Purchase Invoice":

		doc = frappe.get_doc(doctype, docname)
		purchase_receipts = list({row.purchase_receipt for row in doc.items if row.purchase_receipt})
		for prev_4_name in purchase_receipts:
			chain.append({
				"voucher_type": "Purchase Receipt",
				"voucher_no": prev_4_name
			})
			prev_4_doc = frappe.get_doc("Purchase Receipt", prev_4_name)

			purchase_orders = list({row.purchase_order for row in prev_4_doc.items if row.purchase_order})

			for prev_3_name in purchase_orders:
				chain.append({
					"voucher_type": "Purchase Order",
					"voucher_no": prev_3_name
				})
				prev_3_doc = frappe.get_doc("Purchase Order", prev_3_name)

				supplier_quotations = list({row.supplier_quotation for row in prev_3_doc.items if row.supplier_quotation})
				for prev_2_name in supplier_quotations:
					chain.append({
						"voucher_type": "Supplier Quotation",
						"voucher_no": prev_2_name
					})

					prev_2_doc = frappe.get_doc("Supplier Quotation", prev_2_name)

					berita_acaras = list({row.material_request for row in prev_2_doc.items if row.material_request})
					for prev_1_name in berita_acaras:

						chain.append({
							"voucher_type": "Material Request",
							"voucher_no": prev_1_name
						})

						prev_1_doc = frappe.get_doc("Material Request", prev_1_name)

						chain.append({
							"voucher_type": "Berita Acara",
							"voucher_no": prev_1_doc.berita_acara
						})


	elif doctype == "Sales Invoice":

		doc = frappe.get_doc("Sales Invoice", docname)
		delivery_notes = list({row.delivery_note for row in doc.items if row.delivery_note})
		for dn_name in delivery_notes:

			chain.append({
				"voucher_type": "Delivery Note",
				"voucher_no": dn_name
			})

			dn = frappe.get_doc("Delivery Note", dn_name)

			if dn.delivery_order:

				chain.append({
					"voucher_type": "Delivery Order",
					"voucher_no": dn.delivery_order
				})

				do = frappe.get_doc("Delivery Order", dn.delivery_order)

				if do.sales_order:

					chain.append({
						"voucher_type": "Sales Order",
						"voucher_no": do.sales_order
					})

	elif doctype == "Delivery Note":

		doc = frappe.get_doc("Delivery Note", docname)

		if doc.delivery_order:

			chain.append({
				"voucher_type": "Delivery Order",
				"voucher_no": doc.delivery_order
			})

			do = frappe.get_doc("Delivery Order", doc.delivery_order)

			if do.sales_order:

				chain.append({
					"voucher_type": "Sales Order",
					"voucher_no": do.sales_order
				})

	elif doctype == "Delivery Order":

		doc = frappe.get_doc("Delivery Order", docname)

		if doc.sales_order:

			chain.append({
				"voucher_type": "Sales Order",
				"voucher_no": doc.sales_order
			})


	results = []

	for row in chain:

		docs = frappe.get_all(
			"Kriteria Upload Document",
			filters={
				"voucher_type": row["voucher_type"],
				"voucher_no": row["voucher_no"]
			},
			fields=["name"]
		)

		for d in docs:

			doc = frappe.get_doc("Kriteria Upload Document", d.name)

			for f in doc.file_upload:

				results.append({
					"voucher_type": DOC_LABEL.get(row["voucher_type"], row["voucher_type"]),
					"voucher_no": row["voucher_no"],
					"rincian": f.rincian_dokumen_finance,
					"file": f.upload_file
				})

	return results