import frappe
from frappe.utils import flt

DOCTYPE_LAMA = "Uang Muka Purchase Invoice"

CUSTOM_FIELD_LAMA = (
	"Purchase Invoice-uang_muka_po",
	"Purchase Invoice-total_uang_muka",
	"Purchase Invoice-section_break_uang_muka_po",
)


def execute():
	"""Pindahkan baris tabel uang_muka_po ke tabel advances bawaan.

	Uang muka Purchase Order sempat punya tabelnya sendiri di Purchase Invoice.
	Sekarang dia numpang tabel `advances` bawaan — yang tetap dilewati waktu
	rekonsiliasi supaya Payment Entry-nya tidak berpindah dari PO ke invoice.

	GL invoice lama tidak perlu diapa-apakan: jurnal uang mukanya sudah sama
	persis, cuma sumber barisnya yang pindah tabel. Yang perlu digeser hanya
	total_advance, karena rumus grand_total_setelah_dp tidak lagi mengurangi
	total_uang_muka secara terpisah. outstanding_amount juga tetap: dulu
	dikurangi dua kali lewat set_outstanding_setelah_uang_muka(), sekarang
	sekali lewat total_advance, dengan hasil yang sama.
	"""
	if frappe.db.table_exists(DOCTYPE_LAMA):
		pindahkan_baris()

	hapus_kustomisasi()


def pindahkan_baris():
	baris = frappe.db.sql(
		"""
		select um.parent, um.payment_entry, um.payment_entry_row, um.dipakai, um.docstatus
		from `tabUang Muka Purchase Invoice` um
		where um.parenttype = 'Purchase Invoice'
			and um.docstatus < 2
			and um.dipakai > 0
		order by um.parent, um.idx
		""",
		as_dict=True,
	)

	per_invoice = {}
	for row in baris:
		per_invoice.setdefault(row.parent, []).append(row)

	for invoice, rows in per_invoice.items():
		if not frappe.db.exists("Purchase Invoice", invoice):
			continue

		idx = (
			frappe.db.sql(
				"""
				select ifnull(max(idx), 0)
				from `tabPurchase Invoice Advance`
				where parent = %s and parentfield = 'advances'
				""",
				invoice,
			)[0][0]
			or 0
		)

		dipindah = 0
		for row in rows:
			if sudah_pindah(invoice, row.payment_entry_row):
				continue

			idx += 1
			advance = frappe.get_doc(
				{
					"doctype": "Purchase Invoice Advance",
					"parent": invoice,
					"parenttype": "Purchase Invoice",
					"parentfield": "advances",
					"idx": idx,
					"docstatus": row.docstatus,
					"reference_type": "Payment Entry",
					"reference_name": row.payment_entry,
					"reference_row": row.payment_entry_row,
					"advance_amount": flt(row.dipakai),
					"allocated_amount": flt(row.dipakai),
					"remarks": "Uang muka Purchase Order",
				}
			)
			advance.db_insert()
			dipindah += flt(row.dipakai)

		if dipindah:
			frappe.db.sql(
				"""
				update `tabPurchase Invoice`
				set total_advance = ifnull(total_advance, 0) + %s
				where name = %s
				""",
				(dipindah, invoice),
			)


def sudah_pindah(invoice, payment_entry_row):
	"""Jaga-jaga kalau patch ini terlanjur jalan sebagian."""
	return frappe.db.exists(
		"Purchase Invoice Advance",
		{
			"parent": invoice,
			"parenttype": "Purchase Invoice",
			"reference_type": "Payment Entry",
			"reference_row": payment_entry_row,
		},
	)


def hapus_kustomisasi():
	for nama in CUSTOM_FIELD_LAMA:
		frappe.delete_doc_if_exists("Custom Field", nama)

	frappe.delete_doc_if_exists("DocType", DOCTYPE_LAMA, force=1)
