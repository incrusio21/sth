from sth.patches.isi_rata_rata_rendemen_sounding import execute as isi_ulang


def execute():
	"""Jalankan ulang isi_rata_rata_rendemen_sounding sesudah rumusnya berubah.

	Patch aslinya sudah tercatat pernah jalan di site yang hidup, jadi tidak akan
	jalan lagi meski isinya sekarang memakai rumus tertimbang. Entri ini cuma
	pemicu supaya kolom rata-ratanya dihitung ulang sekali lagi; logikanya tetap
	satu-satunya di modul aslinya, dan di site baru patch ini tidak menemukan
	apa-apa untuk diperbaiki karena yang duluan jalan sudah memakai rumus baru.
	"""
	isi_ulang()
