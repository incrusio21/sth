from sth.patches.kembalikan_nama_berprefiks import kembalikan_tph

# Kebun ini dikembalikan ke nama lama; kebun yang tidak disebut tetap berprefiks
# kode divisi.
UNIT = "TMDE"


def execute():
	kembalikan_tph(UNIT)
