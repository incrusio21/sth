import frappe

DOCTYPE = "Timbangan"


def execute(timbangan=None, dry_run=True):
	"""Isi supplier Timbangan TBS Eksternal yang kosong, dibaca dari master Driver.

	Security Check Point menarik supplier lewat fetch_from qr_code_scan.supplier,
	dan fetch_from cuma jalan pada saat dokumen disimpan. Kalau master Driver baru
	diberi supplier sesudah kendaraannya lewat pos - persis yang terjadi pada
	HR-DRI-2026-00692 (SUKUR) tanggal 15 September 2026, dua jam sesudah tiketnya
	dibuat - dokumen yang telanjur tersimpan tetap kosong selamanya. Timbangan
	ikut kosong karena menarik dari ticket_number.supplier.

	Akibatnya baris itu tidak ikut grup supplier mana pun di Laporan Penerimaan
	TBS Mill dan tidak pernah terjaring ke Pengakuan Pembelian TBS.

	Suppliernya diambil dari Driver yang benar-benar discan di tiketnya, bukan
	ditebak dari no polisi: satu plat bisa dipakai beberapa record Driver dengan
	supplier yang berbeda.

	Security Check Point dan Timbangan dua-duanya sudah submit dan field supplier
	read only, jadi nilainya ditulis langsung ke kolomnya. Yang disentuh hanya
	kolom supplier - tidak ada perhitungan ulang, tidak ada dokumen turunan yang
	dibuat ulang, dan tidak ada GL yang bergerak.

	    from sth.patches.isi_supplier_timbangan_tbs_eksternal import execute
	    execute()                            # dry run, cuma mencetak rencana
	    execute(dry_run=False)               # tulis semua yang bisa
	    execute(["TBG-12414"], dry_run=False)

	Dokumen yang supirnya belum punya supplier di master, atau yang tiketnya tidak
	menyebut supir sama sekali, dilewati dan didaftar di akhir: masternya harus
	dibetulkan lebih dulu, baru script ini dijalankan ulang.
	"""
	daftar = timbangan or cari_timbangan_tanpa_supplier()

	if not daftar:
		print("Isi supplier Timbangan: tidak ada dokumen yang perlu dibetulkan")
		return

	berhasil, dilewati = [], []

	for nama in daftar:
		hasil, pesan = _proses_satu(nama, dry_run)

		if hasil:
			berhasil.append((nama, pesan))
			if not dry_run:
				frappe.db.commit()
		else:
			dilewati.append((nama, pesan))

	_cetak_ringkasan(berhasil, dilewati, dry_run)


def cari_timbangan_tanpa_supplier():
	"""Timbangan TBS Eksternal yang sudah submit tapi suppliernya kosong."""
	return frappe.db.sql_list("""
		select name from `tabTimbangan`
		where docstatus = 1
		  and receive_type = 'TBS Eksternal'
		  and coalesce(supplier, '') = ''
		order by posting_date, creation
	""")


def _proses_satu(nama, dry_run):
	doc = frappe.db.get_value(
		DOCTYPE, nama, ["name", "receive_type", "supplier", "ticket_number"], as_dict=True
	)

	if not doc:
		return False, "dokumen tidak ada"

	if doc.receive_type != "TBS Eksternal":
		return False, f"receive_type {doc.receive_type}, bukan TBS Eksternal"

	if doc.supplier:
		return False, f"supplier sudah terisi ({doc.supplier})"

	if not doc.ticket_number:
		return False, "tidak punya ticket_number"

	tiket = frappe.db.get_value(
		"Security Check Point", doc.ticket_number, ["name", "qr_code_scan", "supplier"], as_dict=True
	)

	if not tiket:
		return False, f"Security Check Point {doc.ticket_number} tidak ada"

	if not tiket.qr_code_scan:
		return False, f"tiket {tiket.name} tidak menyebut supir (QR tidak discan)"

	supplier = frappe.db.get_value("Driver", tiket.qr_code_scan, "supplier")

	if not supplier:
		return False, f"Driver {tiket.qr_code_scan} belum punya supplier di master"

	jejak = f"supplier {supplier} dari Driver {tiket.qr_code_scan}"

	if tiket.supplier and tiket.supplier != supplier:
		# Tiketnya sudah menyebut supplier lain; yang di tiket dipakai apa adanya
		# supaya Timbangan tidak bertentangan dengan dokumen induknya.
		supplier = tiket.supplier
		jejak = f"supplier {supplier} dari tiket {tiket.name}"

	if dry_run:
		tambahan = "" if tiket.supplier else f"; tiket {tiket.name} ikut diisi"
		return True, jejak + tambahan

	if not tiket.supplier:
		frappe.db.set_value(
			"Security Check Point", tiket.name, "supplier", supplier, update_modified=False
		)

	frappe.db.set_value(DOCTYPE, doc.name, "supplier", supplier, update_modified=False)

	return True, jejak


def _cetak_ringkasan(berhasil, dilewati, dry_run):
	judul = "RENCANA (dry run)" if dry_run else "HASIL"

	print("")
	print(f"=== Isi supplier Timbangan TBS Eksternal - {judul} ===")

	print(f"Dibetulkan: {len(berhasil)}")
	for nama, pesan in berhasil:
		print(f"  {nama}: {pesan}")

	print("")
	print(f"Dilewati: {len(dilewati)}")
	for nama, pesan in dilewati:
		print(f"  {nama}: {pesan}")

	if dry_run and berhasil:
		print("")
		print("Jalankan ulang dengan dry_run=False untuk menulis.")
