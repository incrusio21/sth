from sth.patches.kembalikan_nama_berprefiks import namai_tph_dari_nama_blok

# Kebun yang Bloknya tetap diawali kode divisi, tapi TPH-nya memakai penyebutan
# lama: "ASRE01A06a-001" jadi "A06a-001" pada Blok "ASRE01A06a".
UNIT = ("APLE", "ASRE")


def execute():
	namai_tph_dari_nama_blok(UNIT)
