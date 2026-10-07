import frappe
from frappe.utils import flt, getdate

PPB = "Permintaan Pengeluaran Barang"


def execute(dry_run=False, dari_tanggal=None, sampai_tanggal=None):
	"""Buat Permintaan Pengeluaran Barang untuk RKH yang disubmit sebelum PPB otomatis ada.

	Sejak RencanaKerjaHarian.on_submit, material RKH langsung diajukan ke gudang
	central sebagai PPB. RKH yang sudah disubmit sebelumnya tidak punya PPB, dan
	patch ini memanggil pembuat yang sama untuk mereka: yang lolos langsung
	disubmit, yang stoknya kurang atau datanya belum lengkap ditinggal di Draft
	dengan alasannya dicatat di RKH. RKH yang sudah punya PPB dilewati, jadi
	patch ini aman diulang.

	Tidak didaftarkan di patches.txt: RKH lama bisa saja materialnya sudah
	diminta lewat PPB manual, dan PPB dari sini akan menggandakannya. Batasi
	dengan rentang posting_date dan baca dulu daftarnya.

	    bench --site <site> execute sth.patches.buat_ppb_rkh_submitted.execute --kwargs "{'dry_run': 1, 'dari_tanggal': '2026-10-01'}"
	"""
	if not frappe.db.has_column(PPB, "rencana_kerja_harian"):
		frappe.throw("Kolom rencana_kerja_harian belum ada di PPB. Jalankan bench migrate dulu.")

	kondisi = ""
	if dari_tanggal:
		kondisi += " AND rkh.posting_date >= %(dari_tanggal)s"
	if sampai_tanggal:
		kondisi += " AND rkh.posting_date <= %(sampai_tanggal)s"

	daftar = frappe.db.sql_list(
		f"""
		SELECT rkh.name
		FROM `tabRencana Kerja Harian` rkh
		WHERE rkh.docstatus = 1
			AND EXISTS (
				SELECT 1 FROM `tabDetail RKH Material` m
				WHERE m.parent = rkh.name AND m.parenttype = 'Rencana Kerja Harian'
			)
			AND NOT EXISTS (
				SELECT 1 FROM `tabPermintaan Pengeluaran Barang` ppb
				WHERE ppb.rencana_kerja_harian = rkh.name AND ppb.docstatus < 2
			)
			{kondisi}
		ORDER BY rkh.posting_date, rkh.name
		""",
		{
			"dari_tanggal": getdate(dari_tanggal) if dari_tanggal else None,
			"sampai_tanggal": getdate(sampai_tanggal) if sampai_tanggal else None,
		},
	)

	hitung = {"submit": 0, "draft": 0, "gagal": 0, "kosong": 0}

	for nama in daftar:
		rkh = frappe.get_doc("Rencana Kerja Harian", nama)

		if dry_run:
			hasil, keterangan = perkiraan(rkh)
		else:
			rkh.buat_permintaan_pengeluaran_barang()
			frappe.db.commit()
			hasil, keterangan = keadaan(rkh)

		hitung[hasil] += 1
		print(f"{rkh.name} {rkh.posting_date} {rkh.divisi}: {hasil} {keterangan}")

	print(
		f"{len(daftar)} RKH {'akan diproses' if dry_run else 'diproses'} — "
		+ ", ".join(f"{k} {v}" for k, v in hitung.items())
	)


def perkiraan(rkh):
	"""Tebakan nasib PPB-nya tanpa menulis apa pun.

	Hanya kendala yang paling sering: stok kurang dan field wajib kosong.
	Penolakan lain baru ketahuan waktu dijalankan sungguhan.
	"""
	items = rkh.susun_item_permintaan_pengeluaran()
	if not items:
		return "kosong", "tidak ada material untuk kegiatan Perawatan"

	kendala = []
	if not rkh.gudang_central:
		kendala.append("gudang_central kosong")
	if not (rkh.nik_penerima_material or rkh.mandor):
		kendala.append("penerima material kosong")

	tanpa_akun = sorted({i["kegiatan"] for i in items if not i["account"]})
	if tanpa_akun:
		kendala.append("akun Kegiatan Company kosong: " + ", ".join(tanpa_akun))

	kebutuhan = {}
	for i in items:
		kebutuhan[i["kode_barang"]] = kebutuhan.get(i["kode_barang"], 0) + flt(i["jumlah"])

	for item, jumlah in kebutuhan.items():
		stok = flt(frappe.db.get_value(
			"Bin", {"warehouse": rkh.gudang_central, "item_code": item}, "actual_qty"
		))
		if jumlah > stok:
			kendala.append(f"stok {item} {stok:g} < {jumlah:g}")

	keterangan = f"{len(items)} baris"
	if kendala:
		return "draft", keterangan + " — " + "; ".join(kendala)

	return "submit", keterangan


def keadaan(rkh):
	ppb = frappe.db.get_value(
		PPB, {"rencana_kerja_harian": rkh.name, "docstatus": ["<", 2]},
		["name", "docstatus"], as_dict=True,
	)

	if ppb:
		return ("submit" if ppb.docstatus == 1 else "draft"), ppb.name

	if not rkh.susun_item_permintaan_pengeluaran():
		return "kosong", "tidak ada material untuk kegiatan Perawatan"

	return "gagal", "lihat komentar di RKH dan Error Log"
