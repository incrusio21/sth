from sth.patches.gabung_bkm_perawatan_trans_no import execute as gabung_bkm_perawatan


def execute():
	"""Kesempatan kedua untuk grup yang dulu dilewati karena punya material.

	gabung_bkm_perawatan_trans_no semula melewati setiap grup yang dokumen
	sumbernya punya material, karena materialnya dikira ikut lenyap waktu
	dokumennya dibatalkan. Ternyata sebaliknya: sistem luar mengulang seluruh
	header di tiap request, jadi tiap dokumen kembar membuat Stock Entry sendiri
	dengan isi yang sama — barangnya keluar dua kali untuk pekerjaan yang satu.
	Membatalkan dokumen sumber justru yang mengembalikannya, lewat delete_ste di
	on_cancel, dan barang untuk pekerjaan itu tetap keluar sekali lewat Stock
	Entry milik penampung.

	Aturannya sudah dilonggarkan di modul itu — sekarang yang ditolak cuma
	material yang isinya berbeda dari penampung. Tapi di site yang sudah terlanjur
	migrate, patch-nya sudah tercatat pernah jalan dan tidak akan diulang. Entri
	ini yang menjalankannya sekali lagi dengan aturan yang baru.

	Aman dijalankan berkali-kali: grup yang sudah digabung tinggal satu dokumen,
	dan grup satu dokumen langsung dilewati tanpa disentuh.
	"""
	gabung_bkm_perawatan()
