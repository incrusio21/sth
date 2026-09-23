"""Purchase Invoice ongkos angkut transportir yang ditarik dari nomor Delivery Order.

Aturan yang disepakati user (23 Sep 2026):
- KG yang ditagih berbasis qty DO, bukan netto timbangan atau qty Delivery Note.
- Kalau DO punya lebih dari satu transportir, qty DO dibagi rata per supplier
  transportir. Baris tabel Delivery Order Transporter itu per armada, jadi satu
  transportir dengan tujuh truk tetap dihitung satu.
- Tarif diisi manual di Purchase Invoice.
- Penagihan boleh bertahap: tiap invoice mengambil sisa bagian transportir itu
  yang belum masuk invoice lain yang sudah submit.
"""

import frappe
from frappe import _
from frappe.utils import flt

INVOICE_TYPE = "Ongkos Angkut Transportir"

# Presisi qty item; bagian per transportir dan sisanya dibulatkan ke sini.
PRESISI_KG = 3


def transportir_do(delivery_order):
	"""Supplier transportir yang berbeda di satu DO, urut sesuai baris pertamanya."""
	baris = frappe.get_all(
		"Delivery Order Transporter",
		filters={"parenttype": "Delivery Order", "parent": delivery_order},
		fields=["transporter"],
		order_by="idx",
	)
	return list(dict.fromkeys(row.transporter for row in baris if row.transporter))


def data_do(delivery_order, company=None):
	do = frappe.db.get_value(
		"Delivery Order",
		delivery_order,
		["name", "docstatus", "is_return", "company", "unit"],
		as_dict=True,
	)
	if not do:
		frappe.throw(_("Delivery Order {0} tidak ditemukan.").format(delivery_order))
	if do.docstatus != 1 or do.is_return:
		frappe.throw(_("Delivery Order {0} belum submit atau berupa retur.").format(frappe.bold(do.name)))
	if company and do.company != company:
		frappe.throw(
			_("Delivery Order {0} milik company {1}, bukan {2}.").format(
				frappe.bold(do.name), do.company, company
			)
		)

	qty = frappe.db.sql(
		"""
		SELECT SUM(stock_qty), GROUP_CONCAT(DISTINCT stock_uom)
		FROM `tabDelivery Order Item`
		WHERE parenttype = 'Delivery Order' AND parent = %s
		""",
		do.name,
	)[0]
	do.qty_do = flt(qty[0], PRESISI_KG)
	do.uom = qty[1]
	return do


def sudah_ditagih(delivery_order, supplier, kecuali_invoice=None):
	"""KG DO ini yang sudah masuk invoice ongkos angkut supplier yang sudah submit."""
	hasil = frappe.db.sql(
		"""
		SELECT SUM(pii.stock_qty)
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1
		  AND pi.invoice_type = %(invoice_type)s
		  AND pi.document_no = %(delivery_order)s
		  AND pi.supplier = %(supplier)s
		  AND pi.name != %(kecuali)s
		""",
		{
			"invoice_type": INVOICE_TYPE,
			"delivery_order": delivery_order,
			"supplier": supplier,
			"kecuali": kecuali_invoice or "",
		},
	)[0][0]
	return flt(hasil, PRESISI_KG)


def hitung_kg_do(do, supplier, kecuali_invoice=None):
	transportir = transportir_do(do.name)
	if not transportir:
		frappe.throw(
			_("Delivery Order {0} belum punya transportir di tab Transporter Info.").format(frappe.bold(do.name))
		)
	if supplier not in transportir:
		frappe.throw(
			_("{0} bukan transportir di Delivery Order {1}. Transportir DO ini: {2}.").format(
				frappe.bold(supplier), frappe.bold(do.name), ", ".join(transportir)
			)
		)

	bagian = flt(do.qty_do / len(transportir), PRESISI_KG)
	ditagih = sudah_ditagih(do.name, supplier, kecuali_invoice)
	return frappe._dict(
		delivery_order=do.name,
		supplier=supplier,
		qty_do=do.qty_do,
		uom=do.uom,
		transportir=transportir,
		jumlah_transportir=len(transportir),
		bagian=bagian,
		sudah_ditagih=ditagih,
		sisa=flt(bagian - ditagih, PRESISI_KG),
	)


def item_ongkos_angkut():
	"""Boleh kosong: baris item tetap dibuat dengan qty KG, item-nya dipilih user sendiri."""
	return frappe.db.get_single_value("Procurement Settings", "item_ongkos_angkut_transportir")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def query_do_transportir(doctype, txt, searchfield, start, page_len, filters):
	"""Pilihan Document No: DO submit milik company, kalau supplier sudah diisi
	hanya DO yang memuat supplier itu sebagai transportir.

	Tidak lewat filter tabel anak bawaan: itu men-join baris armada sehingga satu
	DO muncul sekali per truk di dropdown.
	"""
	kondisi = ""
	if filters.get("supplier"):
		kondisi = """AND EXISTS (
			SELECT 1 FROM `tabDelivery Order Transporter` t
			WHERE t.parenttype = 'Delivery Order' AND t.parent = d.name
			  AND t.transporter = %(supplier)s)"""

	return frappe.db.sql(
		f"""
		SELECT d.name, d.customer_name, d.posting_date
		FROM `tabDelivery Order` d
		WHERE d.docstatus = 1
		  AND d.is_return = 0
		  AND d.company = %(company)s
		  AND (d.name LIKE %(txt)s OR d.customer_name LIKE %(txt)s)
		  {kondisi}
		ORDER BY d.posting_date DESC, d.name DESC
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"company": filters.get("company"),
			"supplier": filters.get("supplier"),
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)


@frappe.whitelist()
def ambil_kg_do(delivery_order, company, supplier=None, purchase_invoice=None):
	"""Dipanggil form Purchase Invoice begitu nomor DO dipilih."""
	frappe.has_permission("Delivery Order", "read", delivery_order, throw=True)

	do = data_do(delivery_order, company)

	# Supplier PI ditimpa transportir DO. Kalau DO punya beberapa transportir,
	# supplier PI dipakai selama termasuk salah satunya; selain itu form diminta
	# menanyakan transportir mana yang ditagih.
	transportir = transportir_do(do.name)
	if len(transportir) == 1:
		supplier = transportir[0]
	elif len(transportir) > 1 and supplier not in transportir:
		return frappe._dict(delivery_order=do.name, pilih_transportir=transportir)

	kg = hitung_kg_do(do, supplier, purchase_invoice)
	kg.item_code = item_ongkos_angkut()
	kg.unit = do.unit
	return kg


def validate_ongkos_angkut_transportir(doc, method=None):
	"""Hook validate Purchase Invoice: KG yang ditagih tidak boleh melewati sisa bagian transportir."""
	if doc.invoice_type != INVOICE_TYPE:
		return

	if not doc.document_no:
		frappe.throw(_("Pilih nomor Delivery Order di field Document No."))

	do = data_do(doc.document_no, doc.company)
	kg = hitung_kg_do(do, doc.supplier, doc.name)

	for row in doc.items:
		if row.stock_uom != do.uom:
			frappe.throw(
				_("Baris {0}: satuan stok item {1} adalah {2}, sedangkan qty DO dalam {3}.").format(
					row.idx, frappe.bold(row.item_code), row.stock_uom, do.uom
				)
			)

	total = flt(sum(flt(row.stock_qty) for row in doc.items), PRESISI_KG)
	if total <= 0:
		frappe.throw(_("Qty yang ditagih harus lebih dari 0."))

	if total > kg.sisa:
		frappe.throw(
			_(
				"Qty yang ditagih {0} {1} melebihi sisa DO {2} untuk {3}: {4} {1}.<br><br>"
				"Qty DO {5} dibagi {6} transportir = {7}, sudah ditagih di invoice lain {8}."
			).format(
				frappe.bold(total),
				do.uom,
				frappe.bold(do.name),
				frappe.bold(doc.supplier),
				frappe.bold(kg.sisa),
				kg.qty_do,
				kg.jumlah_transportir,
				kg.bagian,
				kg.sudah_ditagih,
			),
			title=_("Melebihi Sisa DO"),
		)
