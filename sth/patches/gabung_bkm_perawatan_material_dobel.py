from sth.patches.gabung_bkm_perawatan_trans_no import execute as gabung_bkm_perawatan


def execute():
	"""Kesempatan kedua untuk grup yang dulu dilewati karena punya material.

	gabung_bkm_perawatan_trans_no semula melewati setiap grup yang dokumen
	sumbernya punya material. Alasannya keliru dua kali berturut-turut: mula-mula
	materialnya dikira ikut lenyap waktu dokumennya dibatalkan, lalu sempat
	dibalik jadi membatalkan Stock Entry-nya.

	Yang benar, stok tidak perlu disentuh sama sekali. Tiap dokumen kembar
	terlanjur membuat Stock Entry sendiri, jadi barangnya memang sudah keluar
	sebanyak itu — membatalkannya mengembalikan stok yang secara fisik tidak
	pernah kembali, dan tiap pembatalan cuma menambah record baru. Baris
	materialnya cukup ikut pindah ke penampung supaya angka di dokumen menyusul
	kenyataannya.

	Karena stok tidak lagi jadi taruhan, penjagaannya dibuang seluruhnya:
	memindahkan baris selalu benar, entah materialnya sama atau berbeda. Tapi di
	site yang sudah terlanjur migrate, patch itu sudah tercatat pernah jalan dan
	tidak akan diulang. Entri ini yang menjalankannya sekali lagi.

	Aman dijalankan berkali-kali: grup yang sudah digabung tinggal satu dokumen,
	dan grup satu dokumen langsung dilewati tanpa disentuh.
	"""
	gabung_bkm_perawatan()
