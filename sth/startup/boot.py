# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt"

import frappe

from sth.accounting_sth.doctype.pengaturan_link_title.pengaturan_link_title import isi_boot

def boot_session(bootinfo):
	"""boot session - send website info if guest"""

	if frappe.session["user"] != "Guest":
		update_page_info(bootinfo)
		isi_boot(bootinfo)

	employee = frappe.db.get_value(
		"Employee",
		{"user_id": frappe.session.user},
		["name", "unit", "department"],  # sesuaikan field name unit di Employee doctype
		as_dict=True
	)


		
	frappe.session.data.unit = str(employee.unit) if employee else None
	frappe.session.data.department = str(employee.department) if employee else None

	if frappe.session.user == "Administrator":
		frappe.session.data.unit = "TJHO"
		frappe.session.data.department = "KANTOR - TML"

def update_page_info(bootinfo):
	bootinfo.page_info.update(
		{
			"Rencana Kegiatan": {"title": "Rencana Kegiatan", "route": "Tree/Kegiatan"},
		}
	)