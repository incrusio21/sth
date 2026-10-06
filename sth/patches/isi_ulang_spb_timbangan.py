import frappe
from frappe.utils import add_days, flt

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 30

# SPB dibuat sebelum truknya ditimbang, jadi yang dicari mundur dari tanggal
# timbangan. Seminggu sudah longgar untuk buah yang menginap di pabrik.
JENDELA_HARI = 7


def execute(pasangan=None, dry_run=False):
	"""Isi ulang SPB Timbangan TBS Internal yang terhapus waktu disimpan.

	Field `spb` dulu ber-fetch_from ticket_number.spb tanpa fetch_if_empty. Kalau
	Security Check Point-nya tidak mencatat SPB, SPB yang dipilih operator
	ditimpa kosong tiap kali timbangannya disimpan atau disubmit, sehingga berat
	tidak pernah masuk ke SPB dan kebunnya ikut kosong. Sejak commit 8e1e0078
	itu tidak terjadi lagi; yang tersisa dokumen yang telanjur kosong.

	Nama SPB-nya sendiri tidak pernah sampai ke database. Yang tertinggal rincian
	blok di `spb_detail`: form mengisinya dari SPB yang dipilih (trigger `spb` di
	timbangan.js), dan baris itu tidak ikut terhapus. SPB dicari dari situ:
	company sama, tanggalnya paling lama JENDELA_HARI sebelum timbangan, belum
	dipakai Timbangan aktif mana pun, dan rincian (blok, janjang)-nya persis
	sama. Kalau lebih dari satu, dipersempit lewat no polisi lalu tanggal yang
	sama. Yang tetap ragu, atau yang `spb_detail`-nya kosong, tidak diisi —
	cuma dicetak supaya dipasangkan sendiri lewat argumen `pasangan`.

	Yang diisi: `spb`, lalu `kebun` dan `divisi_kebun` dari SPB-nya. Untuk yang
	sudah submit, berat juga ditulis ke SPB lewat update_spb_weight, seperti
	yang mestinya terjadi di on_submit. Data TBS tidak disentuh: angkanya dibaca
	per unit pabrik, bukan per SPB.

	Aman dijalankan berulang: yang SPB-nya sudah terisi tidak lagi dicari.

	Lihat dulu tanpa menulis:

	    bench --site <site> execute sth.patches.isi_ulang_spb_timbangan.execute --kwargs "{'dry_run': 1}"

	Pasangkan sendiri yang tidak bisa ditebak:

	    bench --site <site> execute sth.patches.isi_ulang_spb_timbangan.execute --kwargs "{'pasangan': {'TBG-13698': 'SPB-40261'}}"
	"""
	if pasangan:
		hasil = [_pasangan_tangan(timbangan, spb) for timbangan, spb in pasangan.items()]
	else:
		hasil = [_tebak(t) for t in _timbangan_tanpa_spb()]
		_tandai_spb_rebutan(hasil)

	terisi = [h for h in hasil if h.spb]
	if not dry_run:
		for h in terisi:
			_isi(h)

	_cetak_ringkasan(hasil, dry_run)


def _timbangan_tanpa_spb():
	"""Timbangan TBS Internal dari form yang SPB-nya kosong.

	Kiriman API dilewati: SPB-nya dicari lewat trans_no di map_api_ticket_number,
	dan kosongnya punya sebab lain.
	"""
	return frappe.db.sql("""
		SELECT t.name, t.docstatus, t.company, t.posting_date, t.no_polisi
		FROM `tabTimbangan` t
		WHERE t.docstatus < 2
			AND t.type = 'Receive'
			AND t.receive_type = 'TBS Internal'
			AND IFNULL(t.spb, '') = ''
			AND IFNULL(t.api_ticket_number, '') = ''
			AND t.owner NOT LIKE '%%api@sth%%'
		ORDER BY t.posting_date, t.name
	""", as_dict=True)


def _tebak(t):
	t.spb = None
	t.alasan = None

	rincian = _rincian("Timbangan SPB Detail", "jumlah_janjang", [t.name]).get(t.name)
	if not rincian:
		t.alasan = "rincian blok kosong, tidak ada petunjuk SPB"
		return t

	kandidat = frappe.db.sql("""
		SELECT spb.name, spb.posting_date, spb.no_polisi
		FROM `tabSurat Pengantar Buah` spb
		WHERE spb.docstatus < 2
			AND spb.company = %(company)s
			AND spb.posting_date BETWEEN %(dari)s AND %(sampai)s
			AND NOT EXISTS (
				SELECT 1 FROM `tabTimbangan` x WHERE x.spb = spb.name AND x.docstatus < 2
			)
	""", {
		"company": t.company,
		"dari": add_days(t.posting_date, -JENDELA_HARI),
		"sampai": t.posting_date,
	}, as_dict=True)

	rincian_spb = _rincian("SPB Timbangan Pabrik", "qty", [k.name for k in kandidat])
	cocok = [k for k in kandidat if rincian_spb.get(k.name) == rincian]

	if len(cocok) > 1 and t.no_polisi:
		cocok = _persempit(cocok, lambda k: _polisi(k.no_polisi) == _polisi(t.no_polisi))
	if len(cocok) > 1:
		cocok = _persempit(cocok, lambda k: k.posting_date == t.posting_date)

	if not cocok:
		t.alasan = "tidak ada SPB yang rincian bloknya sama"
	elif len(cocok) > 1:
		t.alasan = "lebih dari satu SPB cocok: " + ", ".join(k.name for k in cocok)
	else:
		t.spb = cocok[0].name

	return t


def _persempit(cocok, syarat):
	"""Saring kandidat, tapi jangan sampai habis: syarat cuma pemecah seri."""
	sisa = [k for k in cocok if syarat(k)]
	return sisa or cocok


def _polisi(nilai):
	return (nilai or "").replace(" ", "").upper()


def _rincian(doctype, kolom_qty, parents):
	"""Rincian (blok, janjang) per dokumen, sebagai daftar terurut supaya urutan
	baris tidak ikut dibandingkan."""
	if not parents:
		return {}

	rows = frappe.get_all(
		doctype,
		filters={"parent": ("in", parents)},
		fields=["parent", "blok", f"{kolom_qty} as qty"],
		limit_page_length=0,
	)

	hasil = {}
	for r in rows:
		hasil.setdefault(r.parent, []).append((r.blok or "", round(flt(r.qty), 3)))

	return {parent: sorted(baris) for parent, baris in hasil.items()}


def _tandai_spb_rebutan(hasil):
	"""Satu SPB yang ditebak untuk dua timbangan tidak diisikan ke keduanya."""
	pemakai = {}
	for h in hasil:
		if h.spb:
			pemakai.setdefault(h.spb, []).append(h)

	for spb, daftar in pemakai.items():
		if len(daftar) < 2:
			continue
		for h in daftar:
			h.alasan = f"{spb} juga cocok untuk " + ", ".join(x.name for x in daftar if x is not h)
			h.spb = None


def _pasangan_tangan(timbangan, spb):
	t = frappe._dict(name=timbangan, spb=None, alasan=None)

	data = frappe.db.get_value("Timbangan", timbangan, ["docstatus", "spb", "receive_type"], as_dict=True)
	if not data:
		t.alasan = "Timbangan tidak ada"
	elif data.docstatus == 2:
		t.alasan = "Timbangan sudah dibatalkan"
	elif data.spb:
		t.alasan = f"SPB-nya sudah terisi {data.spb}"
	elif not frappe.db.exists("Surat Pengantar Buah", spb):
		t.alasan = f"SPB {spb} tidak ada"
	else:
		t.spb = spb

	return t


def _isi(h):
	spb = frappe.db.get_value("Surat Pengantar Buah", h.spb, ["unit", "divisi"], as_dict=True)

	nilai = {"spb": h.spb}
	if spb.unit:
		nilai["kebun"] = spb.unit
	if spb.divisi:
		nilai["divisi_kebun"] = spb.divisi

	# Lewat db karena kebanyakan sudah submit dan `spb` bukan allow_on_submit.
	# `modified` ikut naik supaya sinkronisasi inkremental EPCS melihatnya lagi.
	frappe.db.set_value("Timbangan", h.name, nilai)

	doc = frappe.get_doc("Timbangan", h.name)
	if doc.docstatus == 1:
		doc.update_spb_weight()


def _cetak_ringkasan(hasil, dry_run):
	terisi = [h for h in hasil if h.spb]
	gagal = [h for h in hasil if not h.spb]
	kata = "akan diisi" if dry_run else "diisi"

	print(f"SPB Timbangan: {len(terisi)} {kata}, {len(gagal)} perlu dipasangkan sendiri")

	for h in terisi[:BATAS_RINCIAN]:
		print(f"  {h.name} -> {h.spb}")
	if len(terisi) > BATAS_RINCIAN:
		print(f"  ... dan {len(terisi) - BATAS_RINCIAN} lain")

	for h in gagal[:BATAS_RINCIAN]:
		print(f"  {h.name}: {h.alasan}")
	if len(gagal) > BATAS_RINCIAN:
		print(f"  ... dan {len(gagal) - BATAS_RINCIAN} lain")
