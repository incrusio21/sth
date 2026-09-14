import frappe
from frappe.utils import add_days, flt

from sth.mill.doctype.tbs_ledger_entry.tbs_ledger_entry import repost_qty_tbs, reverse_tbs_ledger
from sth.mill.doctype.timbangan.timbangan import perbarui_sisa_do_timbangan


def execute(koreksi=None, dry_run=True):
	"""Betulkan bruto/tara Timbangan yang sudah submit, berikut seluruh turunannya.

	netto cuma dihitung di JavaScript (calculate_weight di timbangan.js), jadi
	dokumen yang sudah submit tidak punya jalan untuk dihitung ulang lewat form.
	Script ini menulis langsung ke dokumennya, lalu mengulang setiap langkah yang
	dijalankan on_submit supaya turunannya ikut bergeser:

	    Surat Pengantar Buah : in_weight, out_weight, total_weight, bjr, dan
	                           pembagian berat per baris blok (TBS Internal saja)
	    TBS Ledger Entry     : entry lama dibalik, dibuat ulang dengan netto_2
	                           yang baru, lalu qty TBS di-repost (Receive saja)
	    Delivery Note        : DN lama dibatalkan dan dibuat ulang dengan qty_do
	                           yang baru (Dispatch saja)
	    Timbangan lain       : Sisa DO ditulis ulang untuk DO yang ikut tersentuh

	Dipanggil dari bench console dengan daftar nilai yang benar. Tiap baris boleh
	menyebut tara dengan bruto, atau tara dengan netto — yang ketiga dihitung
	sendiri. Yang tidak disebut sama sekali memakai nilai yang sekarang:

	    from sth.patches.koreksi_netto_tara_timbangan import execute
	    execute([
	        {"timbangan": "TMB-0001", "tara": 5100, "bruto": 17600},
	        {"timbangan": "TMB-0002", "tara": 4980, "netto": 9840},
	    ])

	Default-nya dry run: hanya menghitung dan mencetak rencana perubahan, tanpa
	menulis apa pun. Jalankan ulang dengan dry_run=False setelah angkanya cocok.

	Tiap dokumen di-commit sendiri-sendiri. Kalau satu gagal, perubahannya
	di-rollback sampai dokumen terakhir yang berhasil, dan sisanya tetap
	diproses — jadi satu dokumen bermasalah tidak menggagalkan seluruh daftar.
	"""
	if not koreksi:
		print("Koreksi netto tara: daftar koreksi kosong, tidak ada yang dikerjakan")
		return

	berhasil, dilewati, gagal = [], [], []

	for baris in koreksi:
		nama = baris.get("timbangan") or baris.get("name")

		if not nama:
			gagal.append(("(tanpa nama)", "baris tidak menyebut nama Timbangan"))
			continue

		try:
			hasil, pesan = _koreksi_satu(nama, baris, dry_run)
		except Exception as e:
			frappe.db.rollback()
			gagal.append((nama, str(e)))
			continue

		if hasil == "dilewati":
			dilewati.append((nama, pesan))
			continue

		if not dry_run:
			frappe.db.commit()

		berhasil.append((nama, pesan))

	_cetak_ringkasan(berhasil, dilewati, gagal, dry_run)


def _koreksi_satu(nama, baris, dry_run):
	doc = frappe.get_doc("Timbangan", nama)

	if doc.docstatus != 1:
		return "dilewati", "docstatus {0}, bukan dokumen submitted".format(doc.docstatus)

	tara = flt(baris["tara"]) if baris.get("tara") is not None else flt(doc.tara)

	# netto boleh disebut langsung. Bruto ikut dihitung ulang dari netto + tara,
	# bukan dibiarkan apa adanya: seluruh sistem memegang netto = bruto - tara,
	# dan SPB menyalin ketiganya sekaligus ke in_weight, out_weight, dan
	# total_weight. Membiarkan bruto lama berarti menanam dokumen yang tidak
	# konsisten dengan dirinya sendiri.
	if baris.get("netto") is not None:
		netto = flt(baris["netto"])
		bruto = flt(baris["bruto"]) if baris.get("bruto") is not None else netto + tara

		if bruto - tara != netto:
			return "dilewati", "bruto {0} dikurangi tara {1} bukan netto {2}".format(bruto, tara, netto)
	else:
		bruto = flt(baris["bruto"]) if baris.get("bruto") is not None else flt(doc.bruto)
		netto = bruto - tara

	netto_2 = netto - (netto * flt(doc.potongan_sortasi) / 100)

	if netto < 0:
		return "dilewati", "netto jadi minus ({0}), bruto {1} lebih kecil dari tara {2}".format(netto, bruto, tara)

	ringkas = "bruto {0} -> {1}, tara {2} -> {3}, netto {4} -> {5}, netto_2 {6} -> {7} | {8}".format(
		flt(doc.bruto), bruto, flt(doc.tara), tara, flt(doc.netto), netto, flt(doc.netto_2), netto_2,
		_rencana_turunan(doc),
	)

	if dry_run:
		return "berhasil", ringkas + " [dry run]"

	doc.bruto = bruto
	doc.tara = tara
	doc.netto = netto
	doc.netto_2 = netto_2

	# mengikuti timbangan.js: jumlah janjang hanya dihitung ulang kalau isi
	# komidelnya terisi, supaya jumlah janjang kiriman API tidak ikut tertimpa
	if flt(doc.isi_komidel):
		doc.jumlah_janjang = netto / flt(doc.isi_komidel)

	# menghitung ulang sisa_do, qty_do, dan qty_do_2 dari netto_2 yang baru.
	# bisa melempar kalau netto barunya melebihi sisa DO — itu memang harus
	# dilihat orang, bukan dibiarkan lewat
	if doc.do_no:
		doc.validate_qty_do()

	doc.db_update()

	if doc.receive_type == "TBS Internal":
		doc.update_spb_weight()

	if doc.type == "Receive" and doc.receive_type != "Lain - Lain":
		reverse_tbs_ledger(doc.name)
		doc.make_tbs_ledger()
		repost_qty_tbs(from_date=add_days(doc.posting_date, -7), item_code=doc.kode_barang)

	if doc.type == "Dispatch":
		_buat_ulang_delivery_note(doc)

	return "berhasil", ringkas


def _rencana_turunan(doc):
	"""Sebutkan dokumen lain yang akan ikut disentuh.

	Yang paling perlu terbaca sebelum dijalankan adalah pembatalan Delivery
	Note: itu menyentuh stok dan bisa ditolak kalau DN-nya sudah dipakai
	dokumen lain. Tanpa ini dry run cuma memperlihatkan angka timbangannya,
	padahal bagian terberatnya ada di turunannya.
	"""
	rencana = []

	if doc.receive_type == "TBS Internal":
		rencana.append("SPB {0}".format(doc.spb or "(kosong)"))

	if doc.type == "Receive" and doc.receive_type != "Lain - Lain":
		rencana.append("TBS Ledger dibalik & dibuat ulang")

	if doc.type == "Dispatch":
		dn = [nama for nama in (doc.delivery_note, doc.delivery_note_2) if nama]
		rencana.append(
			"DN {0} dibatalkan & dibuat ulang".format(", ".join(dn)) if dn else "DN dibuat"
		)

	return "turunan: " + "; ".join(rencana) if rencana else "tanpa turunan"


def _buat_ulang_delivery_note(doc):
	"""Batalkan DN lama, buat ulang dengan qty_do yang sudah dihitung ulang.

	DN yang sudah dipakai dokumen lain (Sales Invoice misalnya) tidak bisa
	dibatalkan, dan Frappe akan melempar di sini. Itu dibiarkan naik ke pemanggil
	supaya dokumennya ikut di-rollback dan dilaporkan, bukan dibetulkan setengah.
	"""
	for fieldname in ("delivery_note", "delivery_note_2"):
		nama_dn = doc.get(fieldname)

		if not nama_dn:
			continue

		dn = frappe.get_doc("Delivery Note", nama_dn)

		if dn.docstatus == 1:
			dn.cancel()

		doc.db_set(fieldname, None, update_modified=False)

	doc.create_delivery_notes()

	# Sisa DO di timbangan lain ikut bergeser karena qty_do dokumen ini berubah
	perbarui_sisa_do_timbangan(doc.do_no, doc.kode_barang)

	if doc.no_do_2:
		perbarui_sisa_do_timbangan(doc.no_do_2, doc.kode_barang)


def _cetak_ringkasan(berhasil, dilewati, gagal, dry_run):
	judul = "Koreksi netto tara (dry run)" if dry_run else "Koreksi netto tara"

	print("{0}: {1} berhasil, {2} dilewati, {3} gagal".format(
		judul, len(berhasil), len(dilewati), len(gagal)
	))

	for nama, pesan in berhasil:
		print("  ok      {0}: {1}".format(nama, pesan))

	for nama, pesan in dilewati:
		print("  lewat   {0}: {1}".format(nama, pesan))

	for nama, pesan in gagal:
		print("  gagal   {0}: {1}".format(nama, pesan))

	if dry_run and berhasil:
		print("Belum ada yang ditulis. Jalankan ulang dengan dry_run=False untuk menerapkan.")
