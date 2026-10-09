import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils import flt

def validate_qty_against_purchase_receipt(doc, method=None):
	"""
	Validasi: total qty yang diinvoice (lintas semua PINV) tidak boleh
	melebihi qty yang sudah diterima di Purchase Receipt Item (pr_detail).

	Pasang di hooks.py:
		doc_events = {
			"Purchase Invoice": {
				"validate": "custom_app.utils.validate_pinv_qty.validate_qty_against_purchase_receipt"
			}
		}
	"""

	# Kumpulkan semua pr_detail dari item di dokumen ini
	# agar bisa query sekali (efisien)
	pr_detail_rows = {}

	for item in doc.items:
		if not item.pr_detail:
			continue

		row = pr_detail_rows.setdefault(item.pr_detail, {
			"current_qty": 0.0,
			"current_pecah_amount": 0.0,
			"item_code": item.item_code,
			"item_name": item.item_name or item.item_code,
			"row_name": item.idx,
		})
		# Baris hasil Pecah Item qty tetap membawa qty penuh baris asal, jadi yang
		# dihitung amount-nya; nanti dikonversi ke qty setara lewat rate PR.
		if item.get("pecah_amount"):
			row["current_pecah_amount"] += flt(item.amount)
		else:
			row["current_qty"] += flt(item.qty)

	if not pr_detail_rows:
		return

	pr_detail_list = list(pr_detail_rows.keys())

	# -----------------------------------------------------------
	# 1. Ambil received qty dari Purchase Receipt Item
	# -----------------------------------------------------------
	received_data = frappe.get_all(
		"Purchase Receipt Item",
		filters={"name": ["in", pr_detail_list]},
		fields=["name", "qty", "rate", "parent as purchase_receipt"],
	)
	received_map = {r["name"]: r for r in received_data}

	# -----------------------------------------------------------
	# 2. Hitung qty yang sudah diinvoice di PINV lain
	#    (status submitted atau draft, kecuali cancelled & dokumen ini)
	# -----------------------------------------------------------
	# Kolom pecah_amount baru ada sesudah migrate.
	if frappe.db.has_column("Purchase Invoice Item", "pecah_amount"):
		invoiced_qty = "SUM(IF(pii.pecah_amount, 0, pii.qty)) AS invoiced_qty, SUM(IF(pii.pecah_amount, pii.amount, 0)) AS pecah_amount"
	else:
		invoiced_qty = "SUM(pii.qty) AS invoiced_qty, 0 AS pecah_amount"

	already_invoiced_data = frappe.db.sql(
		f"""
		SELECT
			pii.pr_detail,
			{invoiced_qty}
		FROM
			`tabPurchase Invoice Item` pii
		INNER JOIN
			`tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE
			pii.pr_detail IN %(pr_detail_list)s
			AND pi.docstatus != 2          -- bukan cancelled
			AND pii.parent != %(current_doc)s  -- bukan dokumen ini sendiri
		GROUP BY
			pii.pr_detail
		""",
		{
			"pr_detail_list": pr_detail_list,
			"current_doc": doc.name,
		},
		as_dict=True,
	)
	already_invoiced_map = {row["pr_detail"]: row for row in already_invoiced_data}

	def qty_setara(qty, pecah_amount, rate):
		return flt(qty) + (flt(pecah_amount) / flt(rate) if flt(rate) else 0.0)

	# -----------------------------------------------------------
	# 3. Bandingkan dan lempar error jika melebihi
	# -----------------------------------------------------------
	errors = []

	for pr_detail, info in pr_detail_rows.items():
		received_info = received_map.get(pr_detail)
		if not received_info:
			# pr_detail tidak ditemukan — lewati atau bisa di-raise
			continue

		received_qty = flt(received_info["qty"])
		invoiced = already_invoiced_map.get(pr_detail) or {}
		already_invoiced_qty = flt(
			qty_setara(invoiced.get("invoiced_qty"), invoiced.get("pecah_amount"), received_info["rate"]), 9
		)
		total_invoiced = flt(
			already_invoiced_qty
			+ qty_setara(info["current_qty"], info["current_pecah_amount"], received_info["rate"]),
			9,
		)

		if total_invoiced > received_qty:
			errors.append(
				_(
					"Row {row}: Item <b>{item}</b> — Qty yang diinvoice (<b>{total}</b>) "
					"melebihi qty yang diterima di Purchase Receipt "
					"<b>{pr}</b> (<b>{received}</b>). "
					"Sudah diinvoice sebelumnya: <b>{prev}</b>."
				).format(
					row=info["row_name"],
					item=info["item_name"],
					total=total_invoiced,
					pr=received_info["purchase_receipt"],
					received=received_qty,
					prev=already_invoiced_qty,
				)
			)

	if errors:
		frappe.throw(
			"<br><br>".join(errors),
			title=_("Qty Invoice Melebihi Qty Penerimaan"),
		)

def set_training_event_purchase_invoice(self, method):
	if self.custom_reference_doctype == "Training Event" and self.custom_reference_name:
		training_event = frappe.get_doc("Training Event", self.custom_reference_name)
		training_event.db_set("custom_purchase_invoice", self.name)


@frappe.whitelist()
def get_default_coa(type,company):
	return frappe.get_value("Procurement Settings Account",{"company":company,"type":type},["account"])

def check_tanggal_kirim(self,method):
	for item in self.items:
		if not item.purchase_receipt:
			continue

		# Get Purchase Receipt posting date
		pr_posting_date = frappe.db.get_value(
			'Purchase Receipt', 
			item.purchase_receipt, 
			'posting_date'
		)
		
		if pr_posting_date:
			pi_posting_date = getdate(self.posting_date)
			pr_posting_date = getdate(pr_posting_date)
			
			if pi_posting_date < pr_posting_date:
				frappe.throw(
					_("Row {0}: Purchase Invoice posting date ({1}) cannot be before Purchase Receipt {2} posting date ({3})")
					.format(
						item.idx,
						frappe.format(pi_posting_date, {'fieldtype': 'Date'}),
						item.purchase_receipt,
						frappe.format(pr_posting_date, {'fieldtype': 'Date'})
					),
					title=_("Invalid Posting Date")
				)


def update_keterangan(doc, method):
	values = [doc.supplier_name]

	if doc.document_no:
		if doc.invoice_type == "Purchase Order":
			pr = frappe.get_doc("Purchase Receipt", doc.document_no)
			values.append(pr.purchase_order)

		elif doc.invoice_type == "SPK":
			bapp = frappe.get_doc("BAPP", doc.document_no)
			values.append(bapp.project)
			values.append(bapp.name)

		else:
			values.append(doc.document_no)

	values.append(doc.name)

	doc.keterangan = ", ".join([str(v) for v in values if v])