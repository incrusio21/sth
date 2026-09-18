import frappe

from sth.plantation.doctype.surat_pengantar_buah.surat_pengantar_buah import (
	sambungkan_recap_ke_detail_spb,
)

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran kalau blok
# yang belum punya recap ternyata banyak.
BATAS_RINCIAN = 20


def execute():
	"""Sambungkan baris SPB lama ke Recap Panen by Blok yang sudah terlanjur ada.

	Baris SPB mencari recap-nya sekali saja, waktu SPB itu disimpan. Recap sendiri
	baru lahir waktu BKM Panen disubmit, dan BKM sering menyusul berhari-hari
	kemudian — di saat SPB disimpan tidak ada yang bisa dicari, jadi kolomnya
	ditinggal kosong dan tidak pernah ditengok lagi. Sekarang BKM ikut
	menyusulkan tautannya, tapi yang telanjur kosong tetap kosong tanpa patch ini.

	Kosongnya bukan berarti datanya hilang: recap-nya hampir selalu sudah ada,
	cuma lahir belakangan. Blok dan tanggal panen yang recap-nya memang belum ada
	dilewati dan disebut di ringkasan — BKM-nya belum masuk, dan begitu masuk
	tautannya terpasang sendiri.

	Aman diulang: yang sudah tertaut tidak ikut dicari, apalagi ditimpa.
	"""
	pasangan = kumpulkan_pasangan()

	if not pasangan:
		print("Tidak ada baris SPB Timbangan Pabrik yang recap_panen-nya kosong.")
		return

	tersambung = 0
	tanpa_recap = []

	for blok, panen_date in pasangan:
		recap = frappe.db.get_value(
			"Recap Panen by Blok", {"blok": blok, "posting_date": panen_date}, "name"
		)

		if not recap:
			tanpa_recap.append(f"{blok} {panen_date}")
			continue

		tersambung += sambungkan_recap_ke_detail_spb(blok, panen_date, recap)

	cetak_ringkasan(len(pasangan), tersambung, tanpa_recap)


def kumpulkan_pasangan():
	"""Pasangan blok + tanggal panen yang masih punya baris tanpa tautan recap.

	Baris restan ikut dikumpulkan lewat pasangan kolomnya sendiri. SPB yang
	dibatalkan dilewati: janjangnya sudah tidak dihitung siapa-siapa lagi.
	"""
	pasangan = set()

	for kolom_blok, kolom_tanggal, kolom_recap in (
		("blok", "panen_date", "recap_panen"),
		("blok_restan", "panen_date_restan", "recap_panen_restan"),
	):
		baris = frappe.db.sql("""
			SELECT DISTINCT d.{kolom_blok} AS blok, d.{kolom_tanggal} AS panen_date
			FROM `tabSPB Timbangan Pabrik` d
			INNER JOIN `tabSurat Pengantar Buah` s ON s.name = d.parent
			WHERE s.docstatus < 2
				AND IFNULL(d.{kolom_recap}, '') = ''
				AND IFNULL(d.{kolom_blok}, '') != ''
				AND d.{kolom_tanggal} IS NOT NULL
		""".format(
			kolom_blok=kolom_blok, kolom_tanggal=kolom_tanggal, kolom_recap=kolom_recap
		), as_dict=True)

		pasangan.update((b.blok, b.panen_date) for b in baris)

	return sorted(pasangan, key=lambda p: (str(p[1]), p[0]))


def cetak_ringkasan(jumlah_pasangan, tersambung, tanpa_recap):
	print(f"Blok + tanggal panen yang diperiksa: {jumlah_pasangan}")
	print(f"Baris SPB Timbangan Pabrik yang tersambung: {tersambung}")

	if not tanpa_recap:
		return

	print(f"Belum ada Recap Panen by Blok (BKM Panen-nya belum masuk): {len(tanpa_recap)}")

	for item in tanpa_recap[:BATAS_RINCIAN]:
		print(f"  {item}")

	if len(tanpa_recap) > BATAS_RINCIAN:
		print(f"  ... dan {len(tanpa_recap) - BATAS_RINCIAN} lainnya")
