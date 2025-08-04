# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt"

import frappe

def boot_session(bootinfo):
    """boot session - send website info if guest"""

    if frappe.session["user"] != "Guest":
        update_page_info(bootinfo)

def update_page_info(bootinfo):
	bootinfo.page_info.update(
		{
			"Rencana Kegiatan": {"title": "Rencana Kegiatan", "route": "Tree/Kegiatan"},
		}
	)