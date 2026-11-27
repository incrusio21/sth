import frappe

from sth.patches.gaji_pokok_tanpa_allocation_pkwt import PKWT, baris_gaji_pokok


def execute():
	"""Simpan ulang Salary Slip draft PKWTT/PKWT supaya GAJI POKOK dua lapis berlaku.

	Hanya slip yang Salary Structure-nya punya baris GAJI POKOK yang diubah
	gaji_pokok_tanpa_allocation_pkwt; slip STAFF tidak tersentuh. Slip yang gagal
	disimpan dicatat dan dilewati supaya migrate tidak berhenti di tengah.
	"""
	structures = sorted({r.parent for r in baris_gaji_pokok()})
	if not structures:
		return

	slips = frappe.db.sql(
		"""
		select s.name from `tabSalary Slip` s
		join `tabEmployee` e on e.name = s.employee
		where s.docstatus = 0
			and e.employment_type in %(pkwt)s
			and s.salary_structure in %(ss)s
		order by s.start_date, s.name
		""",
		{"pkwt": PKWT, "ss": structures},
		pluck=True,
	)

	berhasil, gagal = 0, []
	for name in slips:
		try:
			doc = frappe.get_doc("Salary Slip", name)
			doc.flags.ignore_permissions = True
			doc.save()
			frappe.db.commit()
			berhasil += 1
		except Exception as e:
			frappe.db.rollback()
			frappe.clear_last_message()
			gagal.append(f"{name}: {frappe.utils.strip_html(str(e))[:150]}")

	print(f"Salary Slip draft PKWTT/PKWT disimpan ulang: {berhasil} dari {len(slips)}")
	for g in gagal:
		print("   GAGAL", g)
