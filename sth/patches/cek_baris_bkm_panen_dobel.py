import frappe


def execute(posting_date_dari=None, posting_date_sampai=None):
	"""Cari baris hasil kerja panen yang tercatat di lebih dari satu BKM.

	Sebelum penggabungan per trans_no ada, tiap request API jadi dokumen sendiri.
	Kiriman susulan untuk trans_no yang sama — di produksi ada yang datang
	berhari-hari kemudian — ikut jadi dokumen baru, dan kalau isinya mengulang
	baris yang sudah tercatat, janjangnya masuk dua kali ke Recap Panen by Blok
	lewat voucher yang berbeda.

	Ini cuma membaca, tidak mengubah apa pun. Yang keluar adalah kombinasi
	(trans_no, employee, blok, tph) yang muncul di lebih dari satu BKM, beserta
	dokumen dan janjangnya, supaya bisa dinilai orang mana yang memang dobel dan
	mana yang kebetulan sah.

	    from sth.patches.cek_baris_bkm_panen_dobel import execute
	    hasil = execute("2026-07-01", "2026-07-31")
	"""
	kondisi = ""
	nilai = {}

	if posting_date_dari:
		kondisi += " AND b.posting_date >= %(dari)s"
		nilai["dari"] = posting_date_dari

	if posting_date_sampai:
		kondisi += " AND b.posting_date <= %(sampai)s"
		nilai["sampai"] = posting_date_sampai

	rows = frappe.db.sql(
		f"""
		SELECT
			b.trans_no,
			b.company,
			b.posting_date,
			b.is_kontanan,
			hk.employee,
			hk.blok,
			IFNULL(hk.tph, '') AS tph,
			COUNT(DISTINCT hk.parent) AS jml_bkm,
			GROUP_CONCAT(DISTINCT hk.parent ORDER BY hk.parent) AS dokumen,
			SUM(hk.jumlah_janjang) AS janjang,
			MIN(hk.jumlah_janjang) AS janjang_terkecil
		FROM `tabDetail BKM Hasil Kerja Panen` hk
		INNER JOIN `tabBuku Kerja Mandor Panen` b ON b.name = hk.parent
		WHERE IFNULL(b.trans_no, '') != ''
			AND b.docstatus < 2
			{kondisi}
		GROUP BY b.trans_no, b.company, b.posting_date, b.is_kontanan,
			hk.employee, hk.blok, IFNULL(hk.tph, '')
		HAVING COUNT(DISTINCT hk.parent) > 1
		ORDER BY b.posting_date, hk.blok, hk.employee
		""",
		nilai,
		as_dict=True,
	)

	for r in rows:
		# perkiraan janjang yang kelebihan kalau baris kembarnya memang salah:
		# satu baris dianggap yang sah, sisanya kelebihan
		r.janjang_lebih = r.janjang - r.janjang_terkecil

	return rows


def ringkas_per_blok(rows):
	"""Kumpulkan hasil execute() per blok + tanggal, sejajar dengan Recap Panen by Blok.

	Dipakai untuk membandingkan langsung dengan jumlah_janjang recap: kalau
	angkanya cocok dengan selisih yang dikeluhkan SPB, dobelnya memang di sini.
	"""
	ringkas = {}
	for r in rows:
		kunci = (r.blok, r.posting_date)
		data = ringkas.setdefault(kunci, {"baris": 0, "janjang_lebih": 0.0, "dokumen": set()})
		data["baris"] += 1
		data["janjang_lebih"] += r.janjang_lebih
		data["dokumen"].update(r.dokumen.split(","))

	return ringkas
