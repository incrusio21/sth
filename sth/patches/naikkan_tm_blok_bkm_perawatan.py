import frappe

from sth.plantation.doctype.blok.blok import naikkan_ke_tm

BKM_PERAWATAN = [
	"BKM-PWT-04238", "BKM-PWT-04237", "BKM-PWT-04185", "BKM-PWT-04147", "BKM-PWT-04067",
	"BKM-PWT-04036", "BKM-PWT-04029", "BKM-PWT-03997", "BKM-PWT-03956", "BKM-PWT-03908",
	"BKM-PWT-03907", "BKM-PWT-03868", "BKM-PWT-03862", "BKM-PWT-03814", "BKM-PWT-03810",
	"BKM-PWT-03809", "BKM-PWT-03754", "BKM-PWT-03753", "BKM-PWT-03744", "BKM-PWT-03685",
	"BKM-PWT-03684", "BKM-PWT-03636", "BKM-PWT-03570", "BKM-PWT-03509", "BKM-PWT-03508",
	"BKM-PWT-03446", "BKM-PWT-03445", "BKM-PWT-03444", "BKM-PWT-03386", "BKM-PWT-03350",
	"BKM-PWT-03303", "BKM-PWT-03302", "BKM-PWT-03242", "BKM-PWT-03197", "BKM-PWT-03151",
	"BKM-PWT-03150", "BKM-PWT-03132", "BKM-PWT-03131", "BKM-PWT-03070", "BKM-PWT-03069",
	"BKM-PWT-03053", "BKM-PWT-03015", "BKM-PWT-02974", "BKM-PWT-02973", "BKM-PWT-02947",
	"BKM-PWT-02927",
]


def execute(dry_run=True):
	"""Naikkan ke TM Blok TBM dari BKM Perawatan berkategori TM di BKM_PERAWATAN.

	BKM ini dibuat sebelum Accounting Period menaikkan Blok TBM sendiri (commit
	c378ece1), jadi bloknya masih TBM dan GL Entry-nya tidak mendapat Cost
	Center Blok. Sama dengan naikkan_blok_tbm_on_submit: satu JE "Naik TM" per
	tahun tanam + unit, bertanggal hari ini. BKM berkategori selain TM dilewati,
	bloknya memang dirawat sebagai TBM.

	Commit per kelompok; kelompok yang gagal di-rollback dan kelompok lain
	jalan terus. Default-nya dry run. Tulis dengan --kwargs "{'dry_run': 0}".
	"""
	bkm = frappe.get_all(
		"Buku Kerja Mandor Perawatan",
		filters={"name": ["in", BKM_PERAWATAN]},
		fields=["name", "blok", "kategori_kegiatan", "docstatus"],
	)

	hilang = set(BKM_PERAWATAN) - {b.name for b in bkm}
	for name in sorted(hilang):
		print(f"{name}: tidak ditemukan")

	bloks = set()
	for b in bkm:
		if b.kategori_kegiatan != "TM":
			print(f"{b.name}: dilewati, kategori {b.kategori_kegiatan or '-'}")
		elif not b.blok:
			print(f"{b.name}: dilewati, blok kosong")
		else:
			bloks.add(b.blok)

	if not bloks:
		print("Tidak ada Blok yang perlu dinaikkan")
		return

	sudah_tm = frappe.get_all(
		"Blok", filters={"name": ["in", list(bloks)], "workflow_state": ["!=", "TBM"]},
		fields=["name", "blok", "workflow_state"],
	)
	for b in sudah_tm:
		print(f"Blok {b.blok or b.name}: dilewati, status {b.workflow_state}")

	kelompok = {}
	for b in frappe.get_all(
		"Blok",
		filters={"name": ["in", list(bloks)], "workflow_state": "TBM"},
		fields=["name", "blok", "tahun_tanam", "unit"],
		order_by="tahun_tanam asc, unit asc, name asc",
	):
		kelompok.setdefault((b.tahun_tanam, b.unit), []).append(b)

	berhasil = gagal = 0
	for (tahun_tanam, unit), anggota in kelompok.items():
		nama = [b.name for b in anggota]
		label = f"Tahun Tanam {tahun_tanam} Unit {unit}: {', '.join(b.blok or b.name for b in anggota)}"

		if dry_run:
			print(f"{label}: akan dinaikkan")
			berhasil += 1
			continue

		try:
			hasil = naikkan_ke_tm(nama[0], nama, commit=False)
			frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			print(f"{label}: GAGAL, {e}")
			gagal += 1
			continue

		print(f"{label}: naik TM, {hasil}")
		berhasil += 1

	print(f"{'Dry run: ' if dry_run else ''}{berhasil} kelompok diproses, {gagal} gagal")
