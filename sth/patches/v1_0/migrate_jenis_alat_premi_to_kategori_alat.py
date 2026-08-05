import frappe


def execute():
	"""Copy premi rows from Jenis Alat to the matching Kategori Alat record (same name/kode)."""
	for jenis_alat_name in frappe.get_all("Jenis Alat", pluck="name"):
		if not frappe.db.exists("Kategori Alat", jenis_alat_name):
			continue

		premi_rows = frappe.get_all(
			"Jenis Alat Premi",
			filters={"parenttype": "Jenis Alat", "parent": jenis_alat_name},
			fields=["start_time", "end_time", "amount"],
			order_by="idx",
		)
		if not premi_rows:
			continue

		kategori_alat = frappe.get_doc("Kategori Alat", jenis_alat_name)
		existing = {(d.start_time, d.end_time, d.amount) for d in kategori_alat.premi}

		changed = False
		for row in premi_rows:
			key = (row.start_time, row.end_time, row.amount)
			if key in existing:
				continue
			kategori_alat.append("premi", {
				"start_time": row.start_time,
				"end_time": row.end_time,
				"amount": row.amount,
			})
			existing.add(key)
			changed = True

		if changed:
			kategori_alat.save(ignore_permissions=True)
