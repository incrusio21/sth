import frappe

from sth.overrides.accounting_period import BKM_POSTED_ON_PERIOD_SUBMIT, POSTED, bkm_state_field

SUBMITTED = "Submitted"

# commit tiap sekian dokumen supaya patch panjang tidak jadi satu transaksi raksasa
# dan yang sudah beres tidak ikut hilang kalau putus di tengah. Aman karena patch ini
# idempoten: dokumen yang sudah Submitted tidak terpilih lagi waktu diulang.
UKURAN_BATCH = 200

# error yang ditampilkan penuh di akhir; sisanya cukup dihitung
CONTOH_GAGAL = 5


def execute():
	"""Lepas BKM yang terlanjur Posted padahal periodenya tidak tertutup.

	BKM Panen dan Perawatan ditandai Posted waktu Accounting Period-nya disubmit,
	dan di situ pula GL Entry-nya dibuat. Sebelum unpost_bkm_on_cancel ada,
	pembatalan periode cuma membatalkan costing — BKM-nya dibiarkan Posted berikut
	GL Entry-nya. Dokumen seperti itu terkunci: repair_employee_payment_log menolak
	dokumen Posted, jadi upah dan premi tidak bisa dihitung ulang, sementara
	periodenya sendiri sudah terbuka lagi. GL Entry-nya pun ikut terhitung di buku
	besar untuk periode yang secara resmi belum ditutup.

	Yang dilepas cuma yang periodenya benar-benar tidak tertutup: BKM di bawah
	Accounting Period ber-docstatus 1 dibiarkan apa adanya, karena di situ Posted
	memang keadaan yang benar. Jadi patch ini tetap benar kalau nanti dijalankan di
	site yang sudah punya periode tertutup, bukan cuma di keadaan sekarang.

	GL Entry-nya dihapus, tidak diarsipkan seperti arsipkan_bkm_perawatan_batal.
	Bedanya di situ barisnya hilang untuk selamanya, sedangkan di sini set_as_posted
	membuatnya lagi dari dokumen yang sama begitu periodenya ditutup. Yang dihapus
	juga hanya yang is_cancelled = 0, sama seperti delete_gl_entry di controller;
	jejak reverse dari pembatalan lama tidak disentuh.

	Pekerjaannya diserahkan ke set_as_unposted, bukan UPDATE langsung, supaya
	persis sama dengan yang dijalankan hook saat periode dibatalkan. Tiap dokumen
	dipagari savepoint sendiri: tanpa itu, kegagalan menghapus GL Entry — misalnya
	kena Accounts Frozen Till — akan meninggalkan dokumen yang sudah berubah jadi
	Submitted tapi GL Entry-nya masih ada, lebih kacau daripada keadaan awalnya.

	Dokumen yang gagal dilaporkan di akhir tanpa menggagalkan migrate. Patch ini
	bisa diulang setelah penyebabnya dibereskan:

		bench --site <site> execute sth.patches.lepas_bkm_posted_tanpa_periode_tertutup.execute
	"""
	total_dokumen = 0
	total_gl = 0
	semua_gagal = []

	for doctype in BKM_POSTED_ON_PERIOD_SUBMIT:
		state_field = bkm_state_field(doctype)

		# tanpa workflow aktif tidak ada state Posted yang bisa dilepas, dan
		# set_as_unposted pun akan menolak bekerja
		if not state_field or not frappe.db.has_column(doctype, state_field):
			print(f"{doctype}: belum punya workflow aktif, dilewati")
			continue

		nama = frappe.db.sql_list(_kandidat(doctype, state_field), {"posted": POSTED})
		if not nama:
			print(f"{doctype}: tidak ada yang perlu dilepas")
			continue

		# dihitung sebelum apa pun dihapus, supaya angkanya menggambarkan keadaan awal
		gl = _hitung_gl_entry(doctype, state_field)

		dilepas, gagal = _lepas(doctype, nama)

		total_dokumen += dilepas
		total_gl += gl
		semua_gagal.extend(gagal)

		print(f"{doctype}: {dilepas} dari {len(nama)} dokumen dilepas ke {SUBMITTED}, {gl} GL Entry dihapus")

	_cetak_laporan(total_dokumen, total_gl, semua_gagal)


def _kandidat(doctype, state_field):
	"""BKM Posted yang tidak berada di bawah Accounting Period tertutup.

	Periode dianggap tertutup kalau docstatus-nya 1, bukan kalau workflow_state-nya
	"Submitted". Sengaja dipilih yang lebih longgar: salah menganggap periode
	tertutup cuma membuat BKM-nya dilewati, sedangkan salah menganggap terbuka
	berarti melepas dokumen yang seharusnya tetap Posted.
	"""
	return f"""
		SELECT bkm.name
		FROM `tab{doctype}` bkm
		WHERE bkm.docstatus = 1
			AND bkm.`{state_field}` = %(posted)s
			AND NOT EXISTS (
				SELECT 1 FROM `tabAccounting Period` ap
				WHERE ap.docstatus = 1
					AND ap.company = bkm.company
					AND ap.unit = bkm.unit
					AND bkm.posting_date BETWEEN ap.start_date AND ap.end_date
			)
	"""


def _hitung_gl_entry(doctype, state_field):
	return frappe.db.sql(
		f"""
		SELECT COUNT(*) FROM `tabGL Entry`
		WHERE voucher_type = %(doctype)s
			AND is_cancelled = 0
			AND voucher_no IN ({_kandidat(doctype, state_field)})
		""",
		{"doctype": doctype, "posted": POSTED},
	)[0][0]


def _lepas(doctype, nama):
	dilepas = 0
	gagal = []

	for urut, name in enumerate(nama, start=1):
		savepoint = "lepas_bkm"
		try:
			frappe.db.savepoint(savepoint)

			bkm = frappe.get_doc(doctype, name)
			bkm.flags.ignore_permissions = True

			if bkm.set_as_unposted():
				dilepas += 1
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			gagal.append((doctype, name, str(e)))

		if urut % UKURAN_BATCH == 0:
			frappe.db.commit()
			print(f"  {doctype}: {urut}/{len(nama)}")

	frappe.db.commit()

	return dilepas, gagal


def _cetak_laporan(total_dokumen, total_gl, gagal):
	if total_dokumen:
		print(
			f"BKM terlanjur Posted: {total_dokumen} dokumen dikembalikan ke {SUBMITTED}, "
			f"{total_gl} GL Entry dihapus. GL Entry-nya dibuat lagi oleh set_as_posted "
			f"waktu periodenya ditutup."
		)

	if not gagal:
		return

	print(f"{len(gagal)} dokumen gagal dilepas dan dibiarkan Posted:")

	for doctype, name, pesan in gagal[:CONTOH_GAGAL]:
		print(f"  {doctype} {name}: {pesan}")

	if len(gagal) > CONTOH_GAGAL:
		print(f"  ... dan {len(gagal) - CONTOH_GAGAL} lainnya")

	print("Bereskan penyebabnya lalu jalankan ulang patch ini; yang sudah dilepas tidak terpilih lagi.")
