import json
import os
import re

import frappe

PKWT = ("PKWTT", "PKWT")
FIELD_HARI = "attendance_tidak_present_include_gaji_pokok"
KONDISI_BUKAN_PKWT = 'employment_type not in ("PKWTT", "PKWT")'
KONDISI_PKWT = 'employment_type in ("PKWTT", "PKWT")'
RUMUS_UMP = re.compile(r"^\s*ump_harian\s*\*\s*(.+?)\s*$", re.S)


def pastikan_field_salary_slip():
	"""Field hari Tanpa Allocation di Salary Slip harus ada sebelum rumusnya dipakai.

	bench migrate menyinkronkan folder custom/ sesudah semua patch. Tanpa ini,
	resave slip di patch berikutnya gagal karena rumus memanggil field yang
	belum ada.
	"""
	from frappe.modules.utils import sync_customizations_for_doctype

	folder = frappe.get_app_path("sth", "hr_customize", "custom")
	with open(os.path.join(folder, "salary_slip.json")) as f:
		sync_customizations_for_doctype(json.load(f), folder)
	frappe.db.commit()
	frappe.clear_cache(doctype="Salary Slip")


def baris_gaji_pokok():
	"""Baris GAJI POKOK NON STAFF: rumusnya ump_harian * (jumlah hari).

	GAJI POKOK STAFF dilewati: payment_days STAF sudah berisi semua hari dalam
	periode, jadi hari sakit sudah terbayar di sana.
	"""
	rows = frappe.db.sql(
		"""
		select sd.name, sd.parent, sd.idx, sd.formula, sd.`condition`
		from `tabSalary Detail` sd
		join `tabSalary Structure` ss on ss.name = sd.parent
		where sd.parenttype = 'Salary Structure'
			and sd.parentfield = 'earnings'
			and sd.salary_component like '%%GAJI POKOK%%'
			and sd.salary_component <> 'GAJI POKOK STAFF'
			and ss.docstatus < 2
		order by sd.parent, sd.idx
		""",
		as_dict=True,
	)
	return [r for r in rows if r.formula and RUMUS_UMP.match(r.formula)]


def gabung_kondisi(lama, tambahan):
	lama = (lama or "").strip()
	return f"({lama}) and {tambahan}" if lama else tambahan


def execute():
	"""GAJI POKOK NON STAFF jadi dua lapis.

	1. Baris yang ada dibatasi ke employment_type selain PKWTT/PKWT.
	2. Salinannya, tepat di bawahnya, untuk PKWTT/PKWT: hari yang dikali
	   ump_harian ditambah attendance_tidak_present_include_gaji_pokok (sakit
	   yang tetap dibayar gaji pokoknya).

	Salary Structure sudah disubmit dan dipakai ribuan Salary Structure
	Assignment, jadi tidak di-amend (nama baru memutus SSA-nya). condition dan
	formula memang boleh diubah setelah submit; baris salinan disisipkan
	langsung. Baris yang kondisinya sudah menyebut employment_type dianggap
	sudah diproses, jadi patch aman dijalankan ulang.
	"""
	pastikan_field_salary_slip()

	diubah = []
	for row in baris_gaji_pokok():
		if "employment_type" in (row.condition or ""):
			continue

		ss = frappe.get_doc("Salary Structure", row.parent)
		asal = next(r for r in ss.earnings if r.name == row.name)
		hari = RUMUS_UMP.match(asal.formula).group(1)

		# geser baris di bawahnya supaya salinan duduk tepat setelah aslinya
		for r in ss.earnings:
			if r.idx > asal.idx:
				frappe.db.set_value("Salary Detail", r.name, "idx", r.idx + 1, update_modified=False)

		salinan = frappe.new_doc("Salary Detail", parent_doc=ss, parentfield="earnings")
		for field, nilai in asal.as_dict(no_default_fields=True).items():
			salinan.set(field, nilai)
		salinan.idx = asal.idx + 1
		salinan.docstatus = ss.docstatus
		salinan.condition = gabung_kondisi(asal.condition, KONDISI_PKWT)
		salinan.formula = f"ump_harian * ({hari} + {FIELD_HARI})"
		salinan.db_insert()

		frappe.db.set_value(
			"Salary Detail",
			asal.name,
			"condition",
			gabung_kondisi(asal.condition, KONDISI_BUKAN_PKWT),
			update_modified=False,
		)
		frappe.clear_document_cache("Salary Structure", ss.name)
		diubah.append(f"{ss.name} baris {asal.idx} ({asal.salary_component})")

	frappe.db.commit()
	print(f"GAJI POKOK dua lapis: {len(diubah)} baris")
	for x in diubah:
		print("   ", x)
