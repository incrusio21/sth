import frappe
from frappe.utils import flt

DOCTYPE = "Buku Kerja Mandor Perawatan"
CHILD = "Detail BKM Hasil Kerja Perawatan"

# Header yang harus sama persis sebelum dua dokumen boleh disatukan. Kalau salah
# satu berbeda, trans_no-nya memang sama tapi isinya bukan satu buku kerja, dan
# menggabungkannya berarti memindahkan upah ke blok atau kegiatan yang salah.
FIELD_HEADER = (
	"company",
	"posting_date",
	"unit",
	"divisi",
	"kegiatan",
	"kategori_kegiatan",
	"blok",
	"batch",
	"kode_mandor",
	"kemandoran",
)


def execute():
	"""Satukan BKM Perawatan kembar yang terlanjur terbentuk per employee.

	Sistem luar mengirim satu request per employee dengan trans_no yang sama untuk
	semuanya, dan sebelum insert() memeriksa trans_no tiap request jadi satu BKM
	Perawatan sendiri. Yang dimaksud satu buku kerja berisi beberapa employee.

	Barisnya dipindahkan, bukan dibuat ulang: Employee Payment Log menunjuk baris
	lewat voucher_detail_no, dan nama baris tidak berubah waktu induknya diganti.
	Jadi log-nya cukup diarahkan ulang ke dokumen penampung, tanpa dihapus dan
	dibuat lagi — riwayat pembayarannya utuh.

	Yang tidak aman digabung dilewati dan dicetak di akhir supaya bisa ditangani
	manual. Tiap trans_no dikerjakan sendiri-sendiri dan langsung di-commit, jadi
	satu grup yang gagal tidak menarik grup lain yang sudah berhasil.
	"""
	trans_nos = frappe.db.sql(
		"""
		SELECT trans_no
		FROM `tabBuku Kerja Mandor Perawatan`
		WHERE IFNULL(trans_no, '') != ''
			AND docstatus < 2
		GROUP BY trans_no
		HAVING COUNT(*) > 1
		""",
		pluck=True,
	)

	if not trans_nos:
		return

	digabung, manual = [], []

	for trans_no in trans_nos:
		try:
			ok = _merge_group(trans_no)
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"BKM Perawatan kembar {trans_no}: gagal digabung",
				message=frappe.get_traceback(),
			)
			ok = False

		frappe.db.commit()
		(digabung if ok else manual).append(trans_no)

	print(f"BKM Perawatan kembar: {len(digabung)} trans_no digabung, {len(manual)} perlu dicek manual")
	if manual:
		print("  perlu dicek manual: " + ", ".join(manual))


def _merge_group(trans_no):
	"""Gabungkan satu trans_no. Balikan False kalau grupnya tidak aman disentuh."""
	rows = frappe.get_all(
		DOCTYPE,
		filters={"trans_no": trans_no, "docstatus": ("<", 2)},
		fields=["name", "docstatus"],
		order_by="creation asc",
	)

	if len(rows) < 2:
		return True

	docs = [frappe.get_doc(DOCTYPE, row.name) for row in rows]

	# penampung dipilih lebih dulu karena pemeriksaan di bawah bergantung padanya:
	# yang boleh menyimpan material cuma penampung, sisanya dokumen sumber.
	#
	# yang sudah disubmit jadi penampung: dokumennya sudah punya Employee Payment
	# Log, jurnal, dan nomor yang dipakai di laporan. Kalau semuanya masih draft,
	# yang tertua yang dipakai.
	submitted = [doc for doc in docs if doc.docstatus == 1]
	keeper = submitted[0] if submitted else docs[0]

	losers = [doc for doc in docs if doc.name != keeper.name]

	alasan = _alasan_tidak_aman(keeper, losers)
	if alasan:
		frappe.log_error(
			title=f"BKM Perawatan kembar {trans_no}: dilewati",
			message=alasan,
		)
		return False

	_merge_into(keeper, losers)

	return True


def _alasan_tidak_aman(keeper, losers):
	"""Keterangan kenapa grup ini tidak boleh digabung otomatis, atau None."""
	for doc in losers:
		beda = [f for f in FIELD_HEADER if (doc.get(f) or None) != (keeper.get(f) or None)]
		if beda:
			return (
				f"{doc.name} dan {keeper.name} berbeda di header: {', '.join(beda)}. "
				"trans_no-nya sama tapi isinya bukan satu buku kerja."
			)

	for doc in [keeper] + losers:
		# jurnalnya sudah masuk buku besar dan periodenya ditutup
		if doc.is_posted():
			return f"{doc.name} sudah Posted, nilainya tidak boleh berubah lagi."

	# Material dibawa Stock Entry sendiri, dan yang isinya sama persis dengan
	# penampung memang keluar dua kali untuk pekerjaan yang satu — sistem luar
	# mengulang seluruh header di tiap request. Barangnya kembali sendiri waktu
	# dokumen sumber dibatalkan, lewat delete_ste di on_cancel.
	#
	# Yang isinya berbeda tidak boleh disentuh. Membatalkannya mengembalikan barang
	# yang benar-benar dipakai, dan materialnya tidak pernah pindah ke penampung.
	# Termasuk keadaan yang sumbernya punya material sedangkan penampung tidak.
	material_beda = [doc.name for doc in losers if not _material_sama(keeper, doc)]
	if material_beda:
		return (
			f"{', '.join(material_beda)} punya material yang berbeda dari {keeper.name}. "
			"Materialnya harus diurus manual sebelum dokumennya digabung."
		)

	terlihat = {}
	for doc in [keeper] + losers:
		for hk in doc.hasil_kerja:
			if hk.employee in terlihat:
				return (
					f"Employee {hk.employee} ada di {terlihat[hk.employee]} dan {doc.name}. "
					"Salah satunya upah dobel, jadi harus diputuskan manual."
				)

			terlihat[hk.employee] = doc.name

	return None


def _material_sama(keeper, loser):
	"""True kalau material dokumen sumber tidak menambah apa pun di luar penampung.

	Sumber tanpa material selalu aman — tidak ada barang yang perlu diurus. Yang
	isinya sama persis (item, gudang, qty) berarti header yang sama dikirim ulang,
	jadi Stock Entry-nya memang kelebihan dan boleh ikut dibatalkan.

	Sumber tanpa baris material tapi punya Stock Entry dianggap berbeda: keadaan
	itu tidak masuk akal, dan menebaknya bukan tugas patch.
	"""
	if not loser.material:
		return not loser.stock_entry

	return _kunci_material(loser) == _kunci_material(keeper)


def _kunci_material(doc):
	"""Isi material sebagai daftar terurut, supaya dua dokumen bisa dibandingkan."""
	return sorted(
		(d.item or "", d.warehouse or "", flt(d.qty)) for d in doc.material
	)


def _merge_into(keeper, losers):
	idx = len(keeper.hasil_kerja)

	for loser in losers:
		for hk in loser.hasil_kerja:
			idx += 1
			frappe.db.set_value(
				CHILD,
				hk.name,
				{
					"parent": keeper.name,
					"parenttype": DOCTYPE,
					"parentfield": "hasil_kerja",
					"docstatus": keeper.docstatus,
					"idx": idx,
				},
				update_modified=False,
			)

		# voucher_detail_no tiap log menunjuk nama baris yang barusan pindah, dan
		# nama itu tidak berubah — jadi cukup induknya yang diarahkan ulang
		frappe.db.set_value(
			"Employee Payment Log",
			{"voucher_type": DOCTYPE, "voucher_no": loser.name},
			"voucher_no",
			keeper.name,
			update_modified=False,
		)

		_kosongkan_loser(loser)

	_hitung_ulang(keeper.name)


def _kosongkan_loser(loser):
	"""Batalkan dokumen yang isinya sudah pindah, tanpa menyentuh milik penampung.

	Jurnalnya dibuang lebih dulu — bukan dibalik — karena nilainya sekarang jadi
	tanggungan penampung, yang jurnalnya dibuat ulang di _hitung_ulang. Tanpa itu
	on_cancel akan menerbitkan entry pembalik untuk angka yang sudah pindah.

	Stock Entry-nya justru sengaja dibiarkan diurus on_cancel: delete_ste yang
	membatalkan lalu menghapusnya, dan itulah yang mengembalikan barang yang
	terlanjur keluar dua kali. Sampai di sini materialnya sudah dipastikan sama
	persis dengan penampung, jadi yang kembali memang kelebihannya — barang untuk
	pekerjaan itu tetap keluar sekali lewat Stock Entry milik penampung.

	Dokumen dibatalkan, bukan dihapus, supaya nomornya tetap bisa ditelusuri dari
	trans_no yang sama. Draft memang tidak pernah punya jurnal, log, maupun Stock
	Entry, jadi langsung dibuang seperti dokumen hantu.
	"""
	if loser.docstatus == 0:
		frappe.delete_doc(DOCTYPE, loser.name, ignore_permissions=True, force=True)
		return

	frappe.db.sql(
		"DELETE FROM `tabGL Entry` WHERE voucher_type = %s AND voucher_no = %s",
		(DOCTYPE, loser.name),
	)

	frappe.db.set_value(
		DOCTYPE,
		loser.name,
		{
			"hasil_kerja_qty": 0,
			"hasil_kerja_amount": 0,
			"hasil_kerja_hari_kerja": 0,
			"hasil_kerja_premi_amount": 0,
			"material_amount": 0,
			"grand_total": 0,
		},
		update_modified=False,
	)

	# diambil ulang supaya hasil_kerja-nya kosong dan nilainya nol seperti di
	# database; on_cancel jadi tidak punya apa-apa lagi untuk dibersihkan
	frappe.get_doc(DOCTYPE, loser.name).cancel()


def _hitung_ulang(nama):
	doc = frappe.get_doc(DOCTYPE, nama)

	doc.calculate()
	doc.validate_hasil_kerja_harian()
	doc.db_update_all()

	if doc.docstatus != 1:
		# draft belum punya Employee Payment Log maupun jurnal; keduanya dibuat
		# seperti biasa waktu dokumennya disubmit
		return

	doc.create_or_update_payment_log()
	doc.repair_gl_entry()
