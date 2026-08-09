import frappe

from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import BULAN_ROMAWI


def execute():
	"""Tulis ulang label bulan di Master Harga SHU jadi angka romawi.

	Baris penetapan dibuat sekali saat bulannya ditetapkan, jadi dokumen lama
	tetap menyimpan nama bulan sampai barisnya ditulis ulang di sini."""
	for bulan_no, romawi in BULAN_ROMAWI.items():
		frappe.db.sql(
			"""
			UPDATE `tabMaster Harga SHU Penetapan`
			SET bulan = %(romawi)s
			WHERE bulan_no = %(bulan_no)s
			  AND (bulan IS NULL OR bulan != %(romawi)s)
			""",
			{"romawi": romawi, "bulan_no": bulan_no},
		)
