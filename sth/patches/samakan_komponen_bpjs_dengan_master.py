import frappe

from sth.hr_customize.doctype.daftar_bpjs.daftar_bpjs import samakan_komponen_dengan_master

# Batas nama yang dicetak utuh, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 20


def execute():
	"""Samakan komponen BPJS yang sudah dibekukan dengan Set Up BPJS PT sekarang.

	Daftar BPJS menyalin salary component dan expense account dari Set Up BPJS PT
	waktu divalidasi, lalu membekukannya ke Employee Payment Log waktu disubmit.
	Salary slip membacanya dari log itu, sering berbulan-bulan kemudian. Master
	yang dibetulkan di antara kedua saat itu tidak pernah menjalar: dokumen
	tersubmit tidak divalidasi lagi.

	Yang ketahuan 21 September 2026: BPJS KES-PT. TRIMITRA LESTARI-00038 periode
	Juni 2026 membekukan 'BPJS Kesehatan (Perusahaan)-Staff HO/RO' untuk 674
	karyawan TPRE Non Staf. Master 'TPRE - BPJS KESEHATAN NON STAF' dibetulkan ke
	'-Opr Kebun' pada 15 September, tiga bulan sesudahnya. Kedua komponen memakai
	akun berbeda -- 8210107 ASURANSI BPJS KESEHATAN lawan 4121001 BIAYA GAJI
	DIALOKASI -- jadi Rp 96,5 juta biaya BPJS kebun akan mendarat di beban umum,
	bukan di gaji dialokasi kebun yang masuk costing.

	Nilai uang tidak pernah disentuh, cuma nama komponen dan akunnya. Baris yang
	sudah dipakai salary slip tersubmit dilewati dan dilaporkan.

	Slip draft yang sudah memuat komponen lama diganti namanya di tempat. Nilai
	dan jumlah barisnya tidak berubah, jadi gross dan net tetap -- yang berbeda
	cuma akun tujuan komponennya. Slipnya sengaja tidak disimpan ulang:
	update_component_row() menambah baris komponen baru tanpa membuang yang
	lama, dan uji coba 21 September 2026 memperlihatkan gross ke-17 slip naik
	persis sebesar komponennya.

	Aman diulang: yang sudah sama tidak disentuh.

	Sengaja tidak didaftarkan di patches.txt. Ini perbaikan data sekali jalan
	yang menyentuh penggajian dan menyimpan ulang salary slip, jadi mau diawasi
	sendiri waktu dijalankan:

	    bench --site <site> execute sth.patches.samakan_komponen_bpjs_dengan_master.execute
	"""
	hasil = samakan_komponen_dengan_master()

	print(f"Baris Daftar BPJS disesuaikan  : {hasil['detail']}")
	print(f"Employee Payment Log diperbaiki: {hasil['log']}")

	cetak_daftar("Payment log sudah dibayar, dilewati", hasil["log_terkunci"])

	if not hasil["slip_draft"]:
		print("Tidak ada Salary Slip draft yang perlu dihitung ulang.")
		return

	ganti_komponen_slip_draft(sorted(hasil["slip_draft"]))


def ganti_komponen_slip_draft(daftar):
	"""Ganti nama komponen di baris Salary Slip draft, nilainya dibiarkan.

	`daftar` berisi (nama slip, komponen lama, komponen baru). Baris yang slipnya
	sudah punya komponen baru tidak diganti — itu berarti slipnya sempat disimpan
	ulang dan sekarang memuat keduanya, yang harus dibereskan orang karena
	nilainya sudah terlanjur dobel.
	"""
	print("")
	print(f"Mengganti komponen di {len(daftar)} baris Salary Slip draft:")

	diganti = 0
	dobel = []
	tidak_ketemu = []

	for nama_slip, lama, baru in daftar:
		baris = frappe.get_all(
			"Salary Detail",
			filters={"parent": nama_slip, "parenttype": "Salary Slip", "salary_component": lama},
			fields=["name", "parentfield"],
		)

		if not baris:
			tidak_ketemu.append(f"{nama_slip}: {lama}")
			continue

		if frappe.db.exists(
			"Salary Detail",
			{"parent": nama_slip, "parenttype": "Salary Slip", "salary_component": baru},
		):
			dobel.append(f"{nama_slip}: {lama} dan {baru} dua-duanya ada")
			continue

		abbr = frappe.db.get_value("Salary Component", baru, "salary_component_abbr")

		for row in baris:
			frappe.db.set_value(
				"Salary Detail", row.name, {"salary_component": baru, "abbr": abbr}
			)
			diganti += 1

	print(f"  baris diganti: {diganti}")

	cetak_daftar("Slip yang komponen lamanya sudah tidak ada", tidak_ketemu)
	cetak_daftar("Slip yang memuat komponen lama DAN baru, perlu dibereskan manual", dobel)


def cetak_daftar(judul, baris):
	if not baris:
		return

	print("")
	print(f"{judul} ({len(baris)}):")
	for satu in baris[:BATAS_RINCIAN]:
		print(f"  {satu}")

	sisa = len(baris) - BATAS_RINCIAN
	if sisa > 0:
		print(f"  ... dan {sisa} lagi")
