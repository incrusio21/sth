import frappe
from frappe.utils import cint

from sth.accounting_sth.doctype.master_harga_shu.master_harga_shu import (
	NAMA_BULAN,
	kelompok_untuk_umur,
)

DOCTYPE_LAMA = ("Masa SHU", "Masa SHU Detail", "Master Harga SHU Tahun Tanam")


def execute():
	"""Masa SHU dilebur ke Master Harga SHU, dan kolom matriks jadi kelompok umur.

	Tiga perubahan bentuk sekaligus, semuanya di satu keluarga doctype:
	pembagian masa pindah jadi child table, harga tidak lagi dikunci ke tahun
	tanam melainkan ke rentang umur, dan bulan kembali ditulis dengan nama
	Indonesia."""
	pindahkan_masa()
	ubah_harga_ke_kelompok_umur()
	pindahkan_rujukan_perhitungan_kud()
	kembalikan_nama_bulan()
	hapus_doctype_lama()


def pindahkan_masa():
	"""Salin pembagian masa dari Masa SHU yang sudah disubmit.

	Pengajuan berdocstatus 0 sengaja dilewat: itu draft yang belum jadi acuan
	harga, dan pemiliknya bisa mengisi ulang di tempat baru."""
	if not frappe.db.table_exists("Masa SHU"):
		return

	rows = frappe.db.sql(
		"""
		SELECT p.company, p.tahun, p.bulan, p.bulan_no,
		       d.masa_no, d.tanggal_mulai, d.tanggal_selesai, d.jumlah_hari
		FROM `tabMasa SHU Detail` d
		INNER JOIN `tabMasa SHU` p ON d.parent = p.name
		WHERE p.docstatus = 1
		ORDER BY p.company, p.tahun, p.bulan_no, d.idx
		""",
		as_dict=True,
	)

	per_dokumen = {}
	for row in rows:
		per_dokumen.setdefault((row.company, cint(row.tahun)), []).append(row)

	for (company, tahun), baris in per_dokumen.items():
		doc = master_harga_shu(company, tahun)

		# bulan yang sudah punya masa di tempat baru tidak ditimpa — patch ini
		# harus aman kalau dijalankan ulang
		sudah = {cint(m.bulan_no) for m in doc.masa}

		tambahan = 0
		for row in baris:
			if cint(row.bulan_no) in sudah:
				continue

			doc.append(
				"masa",
				{
					"bulan": row.bulan or NAMA_BULAN.get(cint(row.bulan_no)),
					"bulan_no": cint(row.bulan_no),
					"masa_no": cint(row.masa_no),
					"tanggal_mulai": row.tanggal_mulai,
					"tanggal_selesai": row.tanggal_selesai,
					"jumlah_hari": cint(row.jumlah_hari),
				},
			)
			tambahan += 1

		if not tambahan:
			continue

		# validate() akan menyusun ulang nomor masa dan memeriksa cakupan bulan;
		# di sini yang dipindahkan sudah lolos pemeriksaan itu waktu disubmit
		doc.flags.ignore_validate = True
		doc.save(ignore_permissions=True)


def master_harga_shu(company, tahun):
	nama = frappe.db.get_value(
		"Master Harga SHU", {"company": company, "tahun": tahun}, "name"
	)
	if nama:
		return frappe.get_doc("Master Harga SHU", nama)

	doc = frappe.new_doc("Master Harga SHU")
	doc.company = company
	doc.tahun = tahun
	doc.flags.ignore_validate = True
	doc.insert(ignore_permissions=True)

	return doc


def ubah_harga_ke_kelompok_umur():
	"""Harga lama dikunci ke tahun tanam, sekarang ke rentang umur.

	Beberapa tahun tanam bisa jatuh ke kelompok yang sama. Kalau harganya
	berbeda, yang pertama dipakai dan sisanya dilaporkan — bukan dihapus diam-diam.
	"""
	if not frappe.db.has_column("Master Harga SHU Detail", "tahun_tanam"):
		return

	rows = frappe.db.sql(
		"""
		SELECT d.name, d.parent, d.bulan_no, d.masa_no, d.tahun_tanam, d.harga, m.tahun
		FROM `tabMaster Harga SHU Detail` d
		INNER JOIN `tabMaster Harga SHU` m ON d.parent = m.name
		WHERE d.tahun_tanam > 0
		  AND (d.kelompok_umur IS NULL OR d.kelompok_umur = '')
		ORDER BY d.parent, d.bulan_no, d.masa_no, d.tahun_tanam DESC
		""",
		as_dict=True,
	)

	sudah = set()
	bentrok = []

	for row in rows:
		kelompok = kelompok_untuk_umur(cint(row.tahun) - cint(row.tahun_tanam))

		if not kelompok:
			bentrok.append(
				f"{row.parent} bulan {row.bulan_no} masa {row.masa_no} tahun tanam "
				f"{row.tahun_tanam}: umurnya di luar daftar kelompok"
			)
			frappe.db.delete("Master Harga SHU Detail", {"name": row.name})
			continue

		kunci = (row.parent, cint(row.bulan_no), cint(row.masa_no), kelompok["label"])

		if kunci in sudah:
			bentrok.append(
				f"{row.parent} bulan {row.bulan_no} masa {row.masa_no} tahun tanam "
				f"{row.tahun_tanam} (umur {kelompok['label']}) harga {row.harga}: "
				f"kelompoknya sudah terisi, baris ini dibuang"
			)
			frappe.db.delete("Master Harga SHU Detail", {"name": row.name})
			continue

		sudah.add(kunci)
		frappe.db.set_value(
			"Master Harga SHU Detail",
			row.name,
			{
				"kelompok_umur": kelompok["label"],
				"umur_min": kelompok["umur_min"],
				"umur_max": kelompok["umur_max"],
			},
			update_modified=False,
		)

	if bentrok:
		frappe.log_error(
			message="\n".join(bentrok),
			title="Harga SHU yang tidak terbawa ke kelompok umur",
		)


def pindahkan_rujukan_perhitungan_kud():
	"""Baris Perhitungan KUD dulu menunjuk Masa SHU, sekarang Master Harga SHU."""
	if not frappe.db.has_column("Perhitungan KUD Detail", "master_harga_shu"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPerhitungan KUD Detail` d
		INNER JOIN `tabPerhitungan KUD` p ON d.parent = p.name
		INNER JOIN `tabMaster Harga SHU` m
		        ON m.company = p.company AND m.tahun = p.tahun
		SET d.master_harga_shu = m.name
		WHERE d.master_harga_shu IS NULL OR d.master_harga_shu = ''
		"""
	)


def kembalikan_nama_bulan():
	"""Bulan sempat ditulis angka romawi. Dikembalikan ke nama Indonesia."""
	for bulan_no, nama in NAMA_BULAN.items():
		frappe.db.sql(
			"""
			UPDATE `tabMaster Harga SHU Penetapan`
			SET bulan = %(nama)s
			WHERE bulan_no = %(bulan_no)s
			  AND (bulan IS NULL OR bulan != %(nama)s)
			""",
			{"nama": nama, "bulan_no": bulan_no},
		)


def hapus_doctype_lama():
	for doctype in DOCTYPE_LAMA:
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
