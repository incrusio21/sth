import frappe

from sth.plantation.doctype.buku_kerja_mandor_panen.buku_kerja_mandor_panen import (
	FIELD_PEMEGANG_PREMI,
	kunci_baris,
)

DOCTYPE = "Buku Kerja Mandor Panen"
CHILD_HASIL_KERJA = "Detail BKM Hasil Kerja Panen"

# Header yang harus sama persis sebelum dua dokumen boleh disatukan. Kalau salah
# satu berbeda, trans_no-nya memang sama tapi isinya bukan satu buku kerja, dan
# menggabungkannya berarti memindahkan upah ke kegiatan yang salah.
#
# Pemegang premi tidak ada di sini: dokumen dengan kerani atau mandor berbeda
# bukan ditolak, tapi dipecah jadi kelompok sendiri-sendiri — lihat _muat_subgrup.
#
# Tarif ikut diperiksa — beda dari Perawatan — karena nilai tiap baris dihitung
# ulang memakai header penampung: baris yang pindah ke dokumen bertarif lain akan
# berganti upah tanpa ada yang memutuskan.
FIELD_HEADER = (
	"company",
	"posting_date",
	"unit",
	"divisi",
	"kegiatan",
	"kemandoran",
	"is_kontanan",
	"rupiah_basis",
	"volume_basis",
	"upah_brondolan",
	"premi_kontanan_basis",
	"buah_tidak_dipanen_rate",
	"buah_mentah_disimpan_rate",
	"buah_mentah_ditinggal_rate",
	"brondolan_tinggal_rate",
	"pelepah_tidak_disusun_rate",
	"tangkai_panjang_rate",
	"buah_tidak_disusun_rate",
	"pelepah_sengkleh_rate",
)

# Total yang dinolkan di dokumen sumber sebelum dibatalkan. Yang tidak ada di
# doctype dilewati, jadi daftar ini boleh memuat field yang belum tentu terpasang.
FIELD_TOTAL = (
	"hasil_kerja_qty",
	"hasil_kerja_amount",
	"hasil_kerja_hari_kerja",
	"hasil_kerja_jumlah_janjang",
	"hasil_kerja_qty_brondolan",
	"hasil_kerja_brondolan_amount",
	"hasil_kerja_denda",
	"hasil_kerja_kontanan_amount",
	"grand_total",
)


def execute(dry_run=True):
	"""Satukan BKM Panen kembar yang terlanjur terbentuk per pemanen.

	Sistem luar mengirim satu request per pemanen dengan trans_no yang sama untuk
	semuanya, dan sebelum insert() memeriksa trans_no tiap request jadi satu BKM
	Panen sendiri — di produksi satu trans_no sampai memecah jadi 15 dokumen.

	Barisnya dipindahkan, bukan dibuat ulang: Employee Payment Log menunjuk baris
	lewat voucher_detail_no, dan nama baris tidak berubah waktu induknya diganti.
	Jadi log-nya cukup diarahkan ulang ke dokumen penampung, tanpa dihapus dan
	dibuat lagi — riwayat pembayarannya utuh.

	Recap Panen by Blok dibangun ulang untuk penampung **sebelum** dokumen sumber
	dibatalkan. Urutannya bukan selera: recap yang kehilangan voucher terakhirnya
	akan dihapus, dan recap pengganti lahir dengan nama baru sehingga link di SPB
	Timbangan Pabrik dan draft Rekap Timbangan Panen menggantung.

	Default-nya dry run — tidak ada yang diubah, cuma rencananya yang dicetak:

	    from sth.patches.gabung_bkm_panen_trans_no import execute
	    execute()                # lihat dulu
	    execute(dry_run=False)   # baru kerjakan

	Yang tidak aman digabung dilewati dan dicetak di akhir supaya bisa ditangani
	manual. Tiap trans_no dikerjakan sendiri-sendiri dan langsung di-commit, jadi
	satu grup yang gagal tidak menarik grup lain yang sudah berhasil.
	"""
	trans_nos = frappe.db.sql(
		"""
		SELECT trans_no
		FROM `tabBuku Kerja Mandor Panen`
		WHERE IFNULL(trans_no, '') != ''
			AND docstatus < 2
		GROUP BY trans_no
		HAVING COUNT(*) > 1
		""",
		pluck=True,
	)

	if not trans_nos:
		print("Tidak ada BKM Panen kembar.")
		return {"digabung": [], "manual": []}

	digabung, manual = [], []

	for trans_no in trans_nos:
		try:
			hasil = _periksa_grup(trans_no) if dry_run else _merge_group(trans_no)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"BKM Panen kembar {trans_no}: gagal digabung",
				message=frappe.get_traceback(),
			)
			manual.append((trans_no, "gagal, lihat Error Log"))
			continue

		if not dry_run:
			frappe.db.commit()

		for label, alasan in hasil:
			(manual if alasan else digabung).append((label, alasan))

	awalan = "[dry run] " if dry_run else ""
	print(f"{awalan}BKM Panen kembar: {len(digabung)} kelompok bisa digabung, {len(manual)} perlu dicek manual")

	for label, alasan in manual:
		print(f"  {label}: {alasan}")

	return {
		"digabung": [label for label, _ in digabung],
		"manual": [{"kelompok": label, "alasan": alasan} for label, alasan in manual],
	}


def _muat_subgrup(trans_no):
	"""Dokumen se-trans_no, dipecah per pemegang premi, sebagai (penampung, sumber).

	Satu trans_no bisa dipakai dua kerani sekaligus — di produksi pembagiannya 11
	lawan 4 dokumen, bukan satu yang nyasar. Premi kerani dan mandor dihitung dari
	jumlah qty seluruh baris BKM sebulan yang kolom perannya menunjuk mereka, jadi
	menyatukan dua kerani berarti memindahkan premi dari satu orang ke orang lain.
	Yang seperti itu tetap digabung, tapi masing-masing ke penampungnya sendiri.

	Yang sudah disubmit jadi penampung: dokumennya sudah punya Employee Payment
	Log, jurnal, baris voucher di recap, dan nomor yang dipakai di laporan. Kalau
	semuanya masih draft, yang tertua yang dipakai.
	"""
	rows = frappe.get_all(
		DOCTYPE,
		filters={"trans_no": trans_no, "docstatus": ("<", 2)},
		fields=["name"],
		order_by="creation asc",
	)

	if len(rows) < 2:
		return []

	subgrup = {}
	for row in rows:
		doc = frappe.get_doc(DOCTYPE, row.name)
		kunci = tuple(doc.get(f) or "" for f in FIELD_PEMEGANG_PREMI)
		subgrup.setdefault(kunci, []).append(doc)

	hasil = []
	for kunci, docs in subgrup.items():
		if len(docs) < 2:
			continue

		submitted = [doc for doc in docs if doc.docstatus == 1]
		keeper = submitted[0] if submitted else docs[0]

		hasil.append((kunci, keeper, [doc for doc in docs if doc.name != keeper.name]))

	return hasil


def _label(trans_no, kunci):
	return "{} ({})".format(trans_no, "/".join(k or "-" for k in kunci))


def _periksa_grup(trans_no):
	"""Daftar (label, alasan) tiap subgrup; alasan None berarti aman digabung."""
	return [
		(_label(trans_no, kunci), _alasan_tidak_aman(keeper, losers))
		for kunci, keeper, losers in _muat_subgrup(trans_no)
	]


def _merge_group(trans_no):
	"""Gabungkan tiap subgrup satu trans_no. Balikan daftar (label, alasan gagal)."""
	hasil = []

	for kunci, keeper, losers in _muat_subgrup(trans_no):
		label = _label(trans_no, kunci)
		alasan = _alasan_tidak_aman(keeper, losers)

		if alasan:
			frappe.log_error(
				title=f"BKM Panen kembar {label}: dilewati",
				message=alasan,
			)
		else:
			_merge_into(keeper, losers)

		hasil.append((label, alasan))

	return hasil


def _alasan_tidak_aman(keeper, losers):
	"""Keterangan kenapa grup ini tidak boleh digabung otomatis, atau None."""
	for doc in losers:
		beda = [
			f for f in FIELD_HEADER
			if keeper.meta.has_field(f) and (doc.get(f) or None) != (keeper.get(f) or None)
		]
		if beda:
			return (
				f"{doc.name} dan {keeper.name} berbeda di header: {', '.join(beda)}. "
				"trans_no-nya sama tapi isinya bukan satu buku kerja."
			)

	for doc in [keeper] + losers:
		# jurnalnya sudah masuk buku besar dan periodenya ditutup
		if doc.is_posted():
			return f"{doc.name} sudah Posted, nilainya tidak boleh berubah lagi."

		# kontanan yang sudah diajukan: nilainya sudah dipakai dokumen lain
		if doc.get("is_rekap"):
			return f"{doc.name} sudah punya Pengajuan Panen Kontanan, batalkan dulu."

	terlihat = {}
	for doc in [keeper] + losers:
		for hk in doc.hasil_kerja:
			kunci = kunci_baris(hk)
			if kunci in terlihat:
				return (
					f"Baris {kunci} ada di {terlihat[kunci]} dan {doc.name}. "
					"Salah satunya janjang dobel, jadi harus diputuskan manual."
				)

			terlihat[kunci] = doc.name

	return None


def _merge_into(keeper, losers):
	idx = len(keeper.hasil_kerja)

	for loser in losers:
		for hk in loser.hasil_kerja:
			idx += 1
			_pindahkan_baris(hk, keeper, idx)

		# voucher_detail_no tiap log menunjuk nama baris yang barusan pindah, dan
		# nama itu tidak berubah — jadi cukup induknya yang diarahkan ulang
		frappe.db.set_value(
			"Employee Payment Log",
			{"voucher_type": DOCTYPE, "voucher_no": loser.name},
			"voucher_no",
			keeper.name,
			update_modified=False,
		)

	# didahulukan supaya recap selalu memegang voucher penampung waktu dokumen
	# sumber melepas vouchernya sendiri di _kosongkan_loser
	_hitung_ulang(keeper.name)

	for loser in losers:
		_kosongkan_loser(loser)


def _pindahkan_baris(baris, keeper, idx):
	frappe.db.set_value(
		CHILD_HASIL_KERJA,
		baris.name,
		{
			"parent": keeper.name,
			"parenttype": DOCTYPE,
			"parentfield": "hasil_kerja",
			"docstatus": keeper.docstatus,
			"idx": idx,
		},
		update_modified=False,
	)


def _kosongkan_loser(loser):
	"""Batalkan dokumen yang isinya sudah pindah, tanpa menyentuh milik penampung.

	Jurnalnya dibuang lebih dulu — bukan dibalik — karena nilainya sekarang jadi
	tanggungan penampung, yang jurnalnya sudah dibuat ulang di _hitung_ulang.
	Tanpa itu on_cancel akan menerbitkan entry pembalik untuk angka yang sudah
	pindah.

	Dokumen dibatalkan, bukan dihapus, supaya nomornya tetap bisa ditelusuri dari
	trans_no yang sama — dan nomor itu masih tercatat di recap sampai on_cancel
	melepasnya. Draft memang tidak pernah punya jurnal, log, maupun baris voucher,
	jadi langsung dibuang seperti dokumen hantu.
	"""
	if loser.docstatus == 0:
		frappe.delete_doc(DOCTYPE, loser.name, ignore_permissions=True, force=True)
		return

	frappe.db.sql(
		"DELETE FROM `tabGL Entry` WHERE voucher_type = %s AND voucher_no = %s",
		(DOCTYPE, loser.name),
	)

	nol = {f: 0 for f in FIELD_TOTAL if loser.meta.has_field(f)}
	if nol:
		frappe.db.set_value(DOCTYPE, loser.name, nol, update_modified=False)

	# diambil ulang supaya hasil_kerja-nya kosong dan nilainya nol seperti di
	# database; on_cancel jadi tidak punya apa-apa lagi untuk dibersihkan
	frappe.get_doc(DOCTYPE, loser.name).cancel()


def _hitung_ulang(nama):
	doc = frappe.get_doc(DOCTYPE, nama)

	doc.calculate()
	doc.db_update_all()

	if doc.docstatus != 1:
		# draft belum punya Employee Payment Log, baris voucher, maupun jurnal;
		# semuanya dibuat seperti biasa waktu dokumennya disubmit
		return

	doc.create_or_update_payment_log()
	doc.create_or_update_mandor_premi()
	doc.create_or_update_recap_panen_by_blok()
	doc.repair_gl_entry()
