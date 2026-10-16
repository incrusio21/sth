import frappe
from frappe.utils import flt, getdate

from sth.procurement_sth.utils import get_cost_center_from_divisi

PPB = "Permintaan Pengeluaran Barang"


def execute(dry_run=False, dari_tanggal=None, sampai_tanggal=None):
	"""Samakan PPB dari RKH yang sudah terbuat dengan aturan pembuatnya sekarang.

	PPB lama sub_unit barisnya divisi RKH dan no_induk_karyawan-nya kosong.
	Sekarang sub_unit diambil dari divisi Warehouse gudang_virtual RKH dan
	no_induk_karyawan dari no_ktp penerimanya. Gudangnya tetap gudang_central
	RKH; yang sempat berbeda ikut dikembalikan. gudang_tujuan diisi
	gudang_virtual RKH.

	Draft disimpan ulang lewat save() supaya cost center dan stoknya dihitung
	lagi. Yang sudah disubmit tidak punya field allow_on_submit, jadi ditulis
	langsung ke DB — aman karena PPB tidak membuat ledger apa pun.

	PPB yang sudah punya Pengeluaran Barang (draft maupun submit) hanya diisi
	no_induk_karyawan dan gudang_tujuan-nya: barangnya sudah diambil dan
	sub_unit-nya sudah tersalin ke Pengeluaran Barang. Yang begini dibereskan
	tangan.

	Tidak didaftarkan di patches.txt. Jalankan dry_run dulu dan baca daftarnya.

	    bench --site <site> execute sth.patches.perbaiki_ppb_rkh_gudang_virtual.execute --kwargs "{'dry_run': 1}"
	"""
	if not frappe.db.has_column(PPB, "gudang_tujuan"):
		frappe.throw("Kolom gudang_tujuan belum ada di PPB. Jalankan bench migrate dulu.")

	kondisi = ""
	if dari_tanggal:
		kondisi += " AND ppb.tanggal >= %(dari_tanggal)s"
	if sampai_tanggal:
		kondisi += " AND ppb.tanggal <= %(sampai_tanggal)s"

	daftar = frappe.db.sql(
		f"""
		SELECT ppb.name, ppb.rencana_kerja_harian
		FROM `tabPermintaan Pengeluaran Barang` ppb
		WHERE ppb.docstatus < 2
			AND IFNULL(ppb.rencana_kerja_harian, '') != ''
			{kondisi}
		ORDER BY ppb.tanggal, ppb.name
		""",
		{
			"dari_tanggal": getdate(dari_tanggal) if dari_tanggal else None,
			"sampai_tanggal": getdate(sampai_tanggal) if sampai_tanggal else None,
		},
		as_dict=True,
	)

	hitung = {"diubah": 0, "kepala_saja": 0, "sudah_benar": 0, "dilewati": 0}

	for d in daftar:
		ppb = frappe.get_doc(PPB, d.name)
		rkh = frappe.db.get_value(
			"Rencana Kerja Harian", d.rencana_kerja_harian,
			["name", "gudang_central", "gudang_virtual"], as_dict=True
		)

		hasil, keterangan = perbaiki(ppb, rkh, dry_run)
		hitung[hasil] += 1
		print(f"{ppb.name} {ppb.tanggal} {'Draft' if ppb.docstatus == 0 else 'Submit'}: {hasil} {keterangan}")

		if not dry_run:
			frappe.db.commit()

	print(
		f"{len(daftar)} PPB {'akan diperiksa' if dry_run else 'diperiksa'} — "
		+ ", ".join(f"{k} {v}" for k, v in hitung.items())
	)


def perbaiki(ppb, rkh, dry_run):
	no_induk = frappe.db.get_value("Employee", ppb.nama_karyawan, "no_ktp") if ppb.nama_karyawan else None
	gudang_tujuan = rkh.gudang_virtual if rkh else None

	kepala = {}
	if no_induk and ppb.no_induk_karyawan != no_induk:
		kepala["no_induk_karyawan"] = no_induk
	if gudang_tujuan and ppb.gudang_tujuan != gudang_tujuan:
		kepala["gudang_tujuan"] = gudang_tujuan

	def kepala_saja(alasan):
		if kepala and not dry_run:
			ppb.db_set(kepala, update_modified=False)
		return ("kepala_saja" if kepala else "dilewati"), alasan

	if not (rkh and rkh.gudang_virtual):
		return kepala_saja("gudang_virtual RKH kosong")

	sub_unit = frappe.db.get_value("Warehouse", rkh.gudang_virtual, "divisi")
	if not sub_unit:
		return kepala_saja(f"divisi Warehouse {rkh.gudang_virtual} kosong")

	pengeluaran = frappe.db.get_value(
		"Pengeluaran Barang", {"no_permintaan_pengeluaran": ppb.name, "docstatus": ["<", 2]}, "name"
	)
	if pengeluaran or flt(ppb.outgoing) > 0:
		return kepala_saja(
			f"sudah ada Pengeluaran Barang {pengeluaran or ''}".strip() + ", sub_unit dibereskan tangan"
		)

	gudang = rkh.gudang_central or ppb.gudang
	ganti_gudang = ppb.gudang != gudang
	baris_beda = [r for r in ppb.items if r.sub_unit != sub_unit]

	if not (ganti_gudang or baris_beda or kepala):
		return "sudah_benar", ""

	keterangan = []
	if ganti_gudang:
		keterangan.append(f"gudang {ppb.gudang} -> {gudang}")
	if baris_beda:
		keterangan.append(f"sub_unit {len(baris_beda)} baris -> {sub_unit}")
	if "gudang_tujuan" in kepala:
		keterangan.append(f"gudang_tujuan -> {gudang_tujuan}")
	if "no_induk_karyawan" in kepala:
		keterangan.append(f"no_induk -> {no_induk}")

	if dry_run:
		return "diubah", "; ".join(keterangan)

	if ppb.docstatus == 0:
		ppb.gudang = gudang
		ppb.update(kepala)
		for r in ppb.items:
			r.sub_unit = sub_unit

		ppb.flags.ignore_permissions = True
		ppb.flags.ignore_mandatory = True
		ppb.save()
		return "diubah", "; ".join(keterangan)

	ppb.db_set({"gudang": gudang, **kepala}, update_modified=False)

	cost_center = get_cost_center_from_divisi(sub_unit, ppb.pt_pemilik_barang)
	for r in ppb.items:
		r.db_set({"sub_unit": sub_unit, "cost_center": cost_center}, update_modified=False)

	if ganti_gudang:
		# stoknya dulu dicek terhadap gudang lain; yang kurang di gudang ini
		# tetap submit, tapi Pengeluaran Barang-nya nanti akan tertahan
		stok = {}
		kebutuhan = {}
		for r in ppb.items:
			if r.kode_barang not in stok:
				stok[r.kode_barang] = flt(frappe.db.get_value(
					"Bin", {"warehouse": gudang, "item_code": r.kode_barang}, "actual_qty"
				))
			kebutuhan[r.kode_barang] = kebutuhan.get(r.kode_barang, 0) + flt(r.jumlah)
			r.db_set("jumlah_saat_ini", stok[r.kode_barang], update_modified=False)

		kurang = sorted(k for k, jumlah in kebutuhan.items() if jumlah > stok[k])
		if kurang:
			keterangan.append("stok kurang di gudang ini: " + ", ".join(kurang))

	return "diubah", "; ".join(keterangan)
