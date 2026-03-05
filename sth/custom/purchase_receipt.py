import frappe
from frappe import _

@frappe.whitelist()
def set_purchase_order_if_exist(doc,method):
	if not doc.purchase_order:
		if doc.items[0].purchase_order:
			doc.purchase_order = doc.items[0].purchase_order


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
	"""
	Core logic:

	1.  Check whether doc.company is enabled in Procurement Valuation Rate Settings.
		If not → do nothing.

	2.  Collect all unique Purchase Orders referenced in the items table.

	3.  For each PO, fetch total_biaya_ongkos_angkut + pph_22 + cost.

	4.  Distribute those extra costs pro-rata by qty among the items
		that belong to that PO, then ADD to each item's valuation_rate.

		Formula (per item):
			item_share  = item.qty / total_qty_for_po
			extra_value = item_share * (ongkos + pph22 + cost)   [total Rp]
			addition    = extra_value / item.qty                  [Rp per unit]
			item.valuation_rate += addition
	"""
	enabled_companies = get_enabled_companies()

	if doc.company not in enabled_companies:
		return 

	po_items_map: dict[str, list] = {}

	for item in doc.items:
		po_name = item.get("purchase_order")
		if not po_name:
			continue
		po_items_map.setdefault(po_name, []).append(item)

	if not po_items_map:
		return

	for po_name, items in po_items_map.items():
		fields = get_po_valuation_fields(po_name)

		total_extra = (
			fields["total_biaya_ongkos_angkut"]
			+ fields["pph_22"]
			+ fields["cost"]
		)

		if total_extra == 0:
			continue

		total_qty = sum(item.qty for item in items if item.qty)

		if not total_qty:
			
			continue

		for item in items:
			if not item.qty:
				continue

			item_share   = item.qty / total_qty          # fraction of this PO's qty
			extra_value  = item_share * total_extra       # Rp total extra for this row
			addition     = extra_value / item.qty         # Rp per unit

			current_rate         = item.valuation_rate or 0
			item.valuation_rate  = current_rate + addition

	frappe.msgprint(
		_("Valuation rate updated with Ongkos Angkut + PPH22 + Cost from Purchase Order."),
		indicator="green",
		alert=True,
	)

def validate_val_proc(doc, method):
    calculate_valuation_rate_additions(doc)