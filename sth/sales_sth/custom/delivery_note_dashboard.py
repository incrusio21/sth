from frappe import _


def get_data(data):
	"""Connections Delivery Note: Stock Entry disambungkan lewat gudang transit.

	Dua perubahan dari bawaan ERPNext:

	- Stock Entry tidak lagi dicari lewat 'delivery_note_no' tapi lewat
	  'delivery_note_transit', field yang diisi sth/mill/gudang_transit.py waktu
	  Delivery Note disubmit dan membuat Stock Entry masuk gudang transit.
	- Grup Returns dibuang. Isinya cuma Stock Entry, dan dengan field yang sudah
	  diganti, yang muncul di situ bukan retur.

	Stock Entry keluar transit tidak ikut tampil: dokumen itu dibuat Sales
	Invoice dan nomor Delivery Note-nya cuma ada per baris item, bukan di
	header, karena satu invoice bisa menagih beberapa Delivery Note sekaligus.
	"""
	return {
		"fieldname": "delivery_note",
		"non_standard_fieldnames": {
			"Stock Entry": "delivery_note_transit",
			"Quality Inspection": "reference_name",
			"Auto Repeat": "reference_document",
			"Purchase Receipt": "inter_company_reference",
		},
		"internal_links": {
			"Sales Order": ["items", "against_sales_order"],
			"Material Request": ["items", "material_request"],
			"Purchase Order": ["items", "purchase_order"],
		},
		"internal_and_external_links": {
			"Sales Invoice": ["items", "against_sales_invoice"],
		},
		"transactions": [
			{"label": _("Related"), "items": ["Sales Invoice", "Packing Slip", "Delivery Trip"]},
			{"label": _("Reference"), "items": ["Sales Order", "Shipment", "Quality Inspection"]},
			{"label": _("Transit"), "items": ["Stock Entry"]},
			{"label": _("Subscription"), "items": ["Auto Repeat"]},
			{
				"label": _("Internal Transfer"),
				"items": ["Material Request", "Purchase Order", "Purchase Receipt"],
			},
		],
	}
