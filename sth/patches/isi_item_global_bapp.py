import frappe

from sth.legal import get_legal_settings


def execute(dry_run=False):
	"""Isi item global ke baris BAPP lama yang item code-nya kosong.

	Sejak BAPP.set_item_global, baris yang cuma berisi kegiatan diisi Default
	Item Code dari Legal Settings tiap disimpan. Draft ikut terisi begitu
	disimpan ulang, tapi yang sudah submit tidak, padahal Purchase Invoice yang
	ditarik dari situ ikut kosong item code-nya.

	Jurnalnya tidak bergeser: GL Entry BAPP sudah terbentuk, dan make_gl_entries
	memperlakukan item global sama dengan baris tanpa item code.

	    bench --site <site> execute sth.patches.isi_item_global_bapp.execute --kwargs "{'dry_run': 1}"
	"""
	item_global = get_legal_settings("default_item_code")
	if not item_global:
		frappe.throw("Isi Default Item Code di Legal Settings dulu.")

	baris = frappe.db.sql(
		"""
		SELECT bi.name, bi.parent, bi.idx, bi.kegiatan
		FROM `tabBAPP Item` bi
		JOIN `tabBAPP` b ON b.name = bi.parent
		WHERE IFNULL(bi.item_code, '') = ''
		  AND b.docstatus < 2
		ORDER BY bi.parent, bi.idx
		""",
		as_dict=True,
	)

	for b in baris:
		print(f"{b.parent} baris {b.idx} ({b.kegiatan or '-'}) -> {item_global}")

	if not dry_run and baris:
		frappe.db.sql(
			"""
			UPDATE `tabBAPP Item`
			SET item_code = %(item)s
			WHERE name IN %(nama)s
			""",
			{"item": item_global, "nama": [b.name for b in baris]},
		)
		frappe.db.commit()

	print(f"{len(baris)} baris {'akan diisi' if dry_run else 'diisi'} {item_global}")
