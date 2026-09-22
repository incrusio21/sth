import frappe

# Batas rincian yang dicetak, supaya output bench tidak kebanjiran.
BATAS_RINCIAN = 20

# Sekali baca Employee Payment Log maksimal sekian nama baris.
BATAS_IN = 500


def execute(daftar_bpjs=None):
	"""Cari karyawan yang tercatat lebih dari sekali di Daftar BPJS.

	pasang_bpjs dulu mengambil karyawan lewat Salary Structure Assignment tanpa
	menyisakan satu SSA per orang dan tanpa menyaring docstatus, jadi karyawan
	yang SSA-nya pernah di-amend atau yang upahnya pernah naik ikut terdaftar
	sebanyak jumlah SSA-nya. create_payment_log membuat satu Employee Payment Log
	per baris set_up_bpjs_detail_table, dan slip membaca dari sana — jadi baris
	kembar berarti satu karyawan tertagih dua kali.

	Ini cuma membaca, tidak mengubah apa pun. Yang dikeluarkan kombinasi
	(Daftar BPJS, karyawan, program) yang barisnya lebih dari satu, beserta
	kelebihan bebannya dan berapa Employee Payment Log-nya yang sudah menempel di
	slip — supaya bisa dinilai per dokumen mana yang masih aman dibatalkan dan
	mana yang sudah telanjur terbayar.

	    from sth.patches.cek_daftar_bpjs_employee_dobel import execute
	    hasil = execute()
	    hasil = execute("BPJS KES-PT. TRIMITRA LESTARI-31179")
	"""
	baris = _baris_dobel(daftar_bpjs)

	if not baris:
		print("Daftar BPJS: tidak ada karyawan yang tercatat dobel")
		return baris

	_pasang_info_log(baris)
	_cetak_ringkasan(baris)

	return baris


def _baris_dobel(daftar_bpjs):
	"""Kombinasi (dokumen, karyawan, program) yang barisnya lebih dari satu."""
	if isinstance(daftar_bpjs, str):
		daftar_bpjs = [n.strip() for n in daftar_bpjs.split(",")]

	names = [n for n in (daftar_bpjs or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND db.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT
			db.name AS daftar_bpjs,
			db.docstatus,
			db.pt,
			db.unit,
			db.jenis_bpjs,
			db.start_periode,
			d.employee,
			d.nama_employee,
			d.program,
			COUNT(*) AS jml_baris,
			SUM(d.beban_karyawan) AS beban_karyawan,
			SUM(d.beban_perusahaan) AS beban_perusahaan,
			MIN(d.beban_karyawan) AS beban_karyawan_satu,
			MIN(d.beban_perusahaan) AS beban_perusahaan_satu,
			GROUP_CONCAT(d.name ORDER BY d.idx) AS baris
		FROM `tabSet Up BPJS Detail Table` d
		INNER JOIN `tabDaftar BPJS` db ON db.name = d.parent
		WHERE d.parenttype = 'Daftar BPJS'
			AND db.docstatus < 2
			{syarat}
		GROUP BY db.name, db.docstatus, db.pt, db.unit, db.jenis_bpjs,
			db.start_periode, d.employee, d.nama_employee, d.program
		HAVING COUNT(*) > 1
		ORDER BY db.start_periode, db.name, d.nama_employee
	""".format(syarat=syarat), nilai, as_dict=True)


def _pasang_info_log(baris):
	"""Lengkapi tiap baris dengan kelebihan beban dan keadaan payment log-nya.

	Yang dianggap sah satu baris, sisanya kelebihan. Nilai tiap baris kembar
	memang selalu sama — dobelnya lahir dari jumlah SSA, bukan dari angkanya —
	jadi kelebihan cukup dihitung dari salah satu baris dikali barisnya yang lebih.
	"""
	log_per_baris = _log_per_baris(baris)

	for b in baris:
		satu = frappe.utils.flt(b.beban_karyawan_satu) + frappe.utils.flt(b.beban_perusahaan_satu)
		b.beban_lebih = frappe.utils.flt(satu * (b.jml_baris - 1), 2)

		b.jml_log = 0
		b.log_di_slip = 0
		b.log_dibayar = 0
		b.slip = set()

		for nama_baris in b.baris.split(","):
			for log in log_per_baris.get(nama_baris, []):
				b.jml_log += 1
				if log.salary_slip:
					b.log_di_slip += 1
					b.slip.add(log.salary_slip)
				if log.is_paid:
					b.log_dibayar += 1

		b.slip = sorted(b.slip)


def _log_per_baris(baris):
	"""Employee Payment Log yang lahir dari baris-baris itu, dikunci voucher_detail_no."""
	nama_baris = [n for b in baris for n in b.baris.split(",")]

	if not nama_baris:
		return {}

	per_baris = {}

	# dibaca sepotong-sepotong: sekali jalan untuk seluruh company, daftar nama
	# barisnya bisa ribuan dan IN sepanjang itu tidak enak buat MariaDB
	for awal in range(0, len(nama_baris), BATAS_IN):
		logs = frappe.get_all(
			"Employee Payment Log",
			filters={"voucher_detail_no": ["in", nama_baris[awal:awal + BATAS_IN]]},
			fields=["name", "voucher_detail_no", "salary_component", "amount", "salary_slip", "is_paid"],
			limit_page_length=0,
		)

		for log in logs:
			per_baris.setdefault(log.voucher_detail_no, []).append(log)

	return per_baris


def _cetak_ringkasan(baris):
	per_dokumen = ringkas_per_dokumen(baris)

	print("Daftar BPJS dobel: {} kombinasi karyawan+program di {} dokumen".format(
		len(baris), len(per_dokumen)
	))

	for nama, data in sorted(per_dokumen.items()):
		print("  {} (docstatus {}): {} karyawan, kelebihan {:,.0f}, {} log di slip, {} log dibayar".format(
			nama,
			data["docstatus"],
			data["baris"],
			data["beban_lebih"],
			data["log_di_slip"],
			data["log_dibayar"],
		))

	for b in baris[:BATAS_RINCIAN]:
		print("  {} | {} {} | {} | {} baris | lebih {:,.0f}{}".format(
			b.daftar_bpjs,
			b.employee,
			b.nama_employee,
			b.program,
			b.jml_baris,
			b.beban_lebih,
			" | slip {}".format(", ".join(b.slip)) if b.slip else "",
		))

	if len(baris) > BATAS_RINCIAN:
		print("  ... dan {} kombinasi lain".format(len(baris) - BATAS_RINCIAN))


def ringkas_per_dokumen(baris):
	"""Kumpulkan hasil execute() per Daftar BPJS, untuk menilai dokumen per dokumen."""
	ringkas = {}

	for b in baris:
		data = ringkas.setdefault(b.daftar_bpjs, {
			"docstatus": b.docstatus,
			"pt": b.pt,
			"unit": b.unit,
			"jenis_bpjs": b.jenis_bpjs,
			"start_periode": b.start_periode,
			"baris": 0,
			"beban_lebih": 0.0,
			"jml_log": 0,
			"log_di_slip": 0,
			"log_dibayar": 0,
			"slip": set(),
		})

		data["baris"] += 1
		data["beban_lebih"] += b.beban_lebih
		data["jml_log"] += b.jml_log
		data["log_di_slip"] += b.log_di_slip
		data["log_dibayar"] += b.log_dibayar
		data["slip"].update(b.slip)

	return ringkas


def baris_daftar_dobel(daftar_bpjs=None):
	"""Karyawan yang kembar di tabel Daftar BPJS Employee — daftarnya saja.

	Dipisah dari execute() karena tabel ini tidak melahirkan Employee Payment Log:
	dampaknya cuma daftar yang dicetak, bukan angka yang ditagih. Untuk BPJS KES,
	karyawan yang kelas BPJS-nya tidak cocok dengan program manapun tidak punya
	baris di set_up_bpjs_detail_table sama sekali, jadi dobelnya hanya kelihatan
	di sini.
	"""
	if isinstance(daftar_bpjs, str):
		daftar_bpjs = [n.strip() for n in daftar_bpjs.split(",")]

	names = [n for n in (daftar_bpjs or []) if n]

	syarat = ""
	nilai = {}

	if names:
		syarat = "AND db.name IN %(names)s"
		nilai["names"] = tuple(names)

	return frappe.db.sql("""
		SELECT
			db.name AS daftar_bpjs,
			db.docstatus,
			db.start_periode,
			e.employee,
			e.nama,
			COUNT(*) AS jml_baris,
			GROUP_CONCAT(e.idx ORDER BY e.idx) AS idx
		FROM `tabDaftar BPJS Employee` e
		INNER JOIN `tabDaftar BPJS` db ON db.name = e.parent
		WHERE e.parenttype = 'Daftar BPJS'
			AND db.docstatus < 2
			{syarat}
		GROUP BY db.name, db.docstatus, db.start_periode, e.employee, e.nama
		HAVING COUNT(*) > 1
		ORDER BY db.start_periode, db.name, e.nama
	""".format(syarat=syarat), nilai, as_dict=True)
