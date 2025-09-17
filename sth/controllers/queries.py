# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def get_rencana_kerja_harian(kode_kegiatan, divisi, blok, posting_date):
	rkh = frappe.get_value("Rencana Kerja Harian", {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, "blok": blok, "posting_date": posting_date,
		"docstatus": 1
	}, ["name as rencana_kerja_harian", "voucher_type", "voucher_no"], as_dict=1)

	if not rkh:
		frappe.throw(""" Rencana Kerja Harian not Found for Filters <br> 
			Kegiatan : {} <br> 
			Divisi : {} <br> 
			Blok : {} <br>
			Date : {} """.format(kode_kegiatan, divisi, blok, posting_date))

	# no rencana kerja harian
	ress = { 
		**rkh,
		"material": frappe.db.get_all("Detail RKH Material", 
			filters={"parent": rkh}, fields=["item", "uom"]
		) 
	}

	return ress