import frappe
from frappe import _
from frappe.utils import today, flt

def validate_overreceipt(doc, method):
	# Ambil settings overreceipt
	settings = frappe.get_single("Procurement Settings")
	overreceipt_map = {
		row.item: row.percent
		for row in settings.get("item_overreceipt_procurement_settings", [])
	}

	for item in doc.items:
		item_code = item.item_code
		po_item = item.purchase_order_item  # nama field link ke PO detail

		if not po_item:
			continue

		# Ambil qty dari PO
		po_qty, po_uom = frappe.db.get_value(
			"Purchase Order Item",
			po_item,
			["qty", "uom"]
		)

		# Hitung total qty yang sudah diterima di PREC lain (submit, bukan doc ini)
		already_received = frappe.db.sql("""
			SELECT COALESCE(SUM(pri.qty), 0)
			FROM `tabPurchase Receipt Item` pri
			JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
			WHERE pri.purchase_order_item = %s
			  AND pr.docstatus = 1
			  AND pr.name != %s
		""", (po_item, doc.name))[0][0]

		total_after = already_received + item.qty

		if item_code in overreceipt_map:
			percent = overreceipt_map[item_code]
			max_qty = po_qty * (1 + percent / 100)
			if total_after > max_qty:
				frappe.throw(
					f"Item <b>{item_code}</b>: Total qty diterima ({total_after}) "
					f"melebihi batas overreceipt {percent}% dari PO qty {po_qty} "
					f"(maks: {max_qty}). Sudah diterima sebelumnya: {already_received}."
				)
		else:
			# Tidak ada overreceipt → normal, tidak boleh melebihi PO qty
			if total_after > po_qty:
				frappe.throw(
					f"Item <b>{item_code}</b>: Total qty diterima ({total_after}) "
					f"melebihi PO qty {po_qty}. "
					f"Sudah diterima sebelumnya: {already_received}."
				)
				
@frappe.whitelist()
def set_purchase_order_if_exist(doc,method):
	if not doc.purchase_order:
		if doc.items[0].purchase_order:
			doc.purchase_order = doc.items[0].purchase_order

	# for row in doc.items:
	# 	if row.purchase_order_item:
	# 		row.po_qty = frappe.get_doc("Purchase Order Item",purchase_order_item).qty

def get_enabled_companies():
	try:
		settings = frappe.get_single("Procurement Valuation Rate Settings")
		return {
			row.company
			for row in settings.get("enabled_companies", [])
			if row.enabled
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Procurement Valuation Rate Settings – fetch error")
		return set()


def get_po_valuation_fields(po_name):
	if not po_name:
		return {"total_biaya_ongkos_angkut": 0, "pph_22": 0, "cost": 0}

	result = frappe.db.get_value(
		"Purchase Order",
		po_name,
		["total_biaya_ongkos_angkut", "pph_22", "cost"],
		as_dict=True,
	)

	if not result:
		return {"total_biaya_ongkos_angkut": 0, "pph_22": 0, "cost": 0}

	return {
		"total_biaya_ongkos_angkut": result.get("total_biaya_ongkos_angkut") or 0,
		"pph_22": result.get("pph_22") or 0,
		"cost": result.get("cost") or 0,
	}


def calculate_valuation_rate_additions(doc):

	enabled_companies = get_enabled_companies()
	if doc.company in enabled_companies:
		return

	total_qty = 0

	for row in doc.items:
		total_qty += row.qty

	
	for row in doc.items:
		row.valuation_rate -= doc.pph_22 / total_qty
	
	# po_items_map: dict[str, list] = {}

	# for item in doc.items:
	# 	po_name = item.get("purchase_order")
	# 	if not po_name:
	# 		continue
	# 	po_items_map.setdefault(po_name, []).append(item)

	# if not po_items_map:
	# 	return

	# for po_name, items in po_items_map.items():
	# 	fields = get_po_valuation_fields(po_name)

	# 	if doc.company not in enabled_companies:
	# 		total_extra = (
	# 			fields["total_biaya_ongkos_angkut"]
	# 			+ fields["cost"]
	# 		)
	# 	else:
	# 		total_extra = (
	# 			fields["total_biaya_ongkos_angkut"]
	# 			+ fields["pph_22"]
	# 			+ fields["cost"]
	# 		)

	# 	if total_extra == 0:
	# 		continue

	# 	total_qty = sum(item.qty for item in items if item.qty)

	# 	if not total_qty:
			
	# 		continue

	# 	for item in items:
	# 		if not item.qty:
	# 			continue

	# 		item_share   = item.qty / total_qty          # fraction of this PO's qty
	# 		extra_value  = item_share * total_extra       # Rp total extra for this row
	# 		addition     = extra_value / item.qty         # Rp per unit

	# 		current_rate         = item.valuation_rate or 0
	# 		item.valuation_rate  = current_rate + addition
	# 		print(current_rate)
	# 		print(addition)
	# 		print(item.valuation_rate)

	# frappe.msgprint(
	# 	_("Valuation rate updated with Ongkos Angkut + PPH22 + Cost from Purchase Order."),
	# 	indicator="green",
	# 	alert=True,
	# )

def validate_val_proc(doc, method):
	calculate_valuation_rate_additions(doc)


def auto_create_assets_from_pr(doc, method=None):

	assets_created = []
	errors = []

	for row in doc.items:
		asset_category = row.get("asset_category")

		# Skip baris yang tidak punya asset_category
		if not asset_category:
			continue

		qty = int(row.get("qty") or 1)

		for idx in range(qty):
			try:
				asset_name = _create_asset_draft(
					pr_doc=doc,
					item_row=row,
					asset_category=asset_category,
					sequence=idx + 1,
					total_qty=qty,
				)
				assets_created.append(asset_name)

			except Exception as exc:
				errors.append(
					f"Item {row.item_code} (baris {row.idx}, unit {idx+1}): {exc}"
				)
				frappe.log_error(
					title="Auto Create Asset Error",
					message=frappe.get_traceback(),
				)

				print(str(errors))

	# -----------------------------------------------------------------------
	# Notifikasi hasil
	# -----------------------------------------------------------------------
	if assets_created:
		frappe.msgprint(
			msg=_(
				"{count} Asset Draft berhasil dibuat:<br>{names}"
			).format(
				count=len(assets_created),
				names="<br>".join(
					f'<a href="/app/asset/{n}">{n}</a>' for n in assets_created
				),
			),
			title=_("Asset Draft Dibuat"),
			indicator="green",
		)

	if errors:
		frappe.msgprint(
			msg=_("Beberapa Asset gagal dibuat:<br>") + "<br>".join(errors),
			title=_("Peringatan"),
			indicator="orange",
		)

	return assets_created

def _create_asset_draft(pr_doc, item_row, asset_category, sequence, total_qty):
	asset = frappe.new_doc("Asset")

	asset.item_code          = item_row.item_code
	asset.item_name          = item_row.item_name
	asset.asset_category     = asset_category
	asset.company            = pr_doc.company
	asset.purchase_date      = pr_doc.posting_date or today()
	asset.total_depreciation_fiscal = 12

	asset.gross_purchase_amount = flt(item_row.get("base_rate") or 0)

	asset.purchase_receipt   = pr_doc.name
	asset.supplier           = pr_doc.supplier
	asset.purchase_receipt_item = item_row.name

	asset.location = item_row.get("asset_location") or ""
	asset.cost_center = item_row.get("cost_center") or pr_doc.get("cost_center") or ""

	if total_qty > 1:
		asset.asset_name = f"{item_row.item_name} ({sequence}/{total_qty})"
	else:
		asset.asset_name = item_row.item_name

	asset.docstatus = 0
	asset.insert(ignore_permissions=True)
	return asset.name

def check_receipt_notification(doc, method):

    # Ambil settings dari single doctype Procurement Settings
    try:
        settings = frappe.get_single("Procurement Settings")
    except Exception as e:
        print("STOP: Gagal ambil Procurement Settings:", e)
        return

    roles = [
        row.role
        for row in settings.get("receipt_notification_procurement_settings", [])
        if row.role
    ]
    print("Roles ditemukan:", roles)

    if not roles:
        print("STOP: Tidak ada role di Receipt Notification Procurement Settings")
        return

    # Ambil users yang punya role tersebut
    users = frappe.get_all(
        "Has Role",
        filters={
            "role": ["in", roles],
            "parenttype": "User"
        },
        pluck="parent"
    )
    print("Users dari role:", users)

    if not users:
        print("STOP: Tidak ada user dengan role tersebut")
        return

    users = list(set(users))
    print("Users final:", users)

    for user in users:
        enabled = frappe.db.get_value("User", user, "enabled")
        print(f"User {user} enabled:", enabled)
        if not enabled:
            continue

        exists = frappe.db.exists(
            "Notification Log",
            {
                "for_user": user,
                "document_type": doc.doctype,
                "document_name": doc.name
            }
        )
        if exists:
            print("Notif sudah ada untuk:", user)
            continue

        print("Membuat notification untuk:", user)
        notification = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"{doc.doctype} {doc.name} telah diterima dan perlu diperhatikan",
            "for_user": user,
            "type": "Alert",
            "document_type": doc.doctype,
            "document_name": doc.name
        }).insert(ignore_permissions=True)
        print("Notification dibuat:", notification.name)
        notification.notify_update()
        frappe.publish_realtime(
            event="notification",
            message={"type": "Alert"},
            user=user
        )