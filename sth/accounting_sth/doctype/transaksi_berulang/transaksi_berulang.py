

import frappe
from frappe import _, throw
from frappe.model.document import Document
from frappe.utils import getdate, add_months, today, flt

from sth.custom import method_ambil_account

class TransaksiBerulang(Document):

	# ── Lifecycle ────────────────────────────────────────────────────────────

	def validate(self):
		_validate(self)
		_generate_je_schedule(self)

	def on_submit(self):
		self.make_gl_entries()

	def on_cancel(self):
		# Batalkan JE yang sudah dibuat (yang masih Draft)
		self.cancel_gl_entries()
		_cancel_linked_je(self)

	def make_gl_entries(doc, method=None):
		"""
		Buat GL Entry untuk Transaksi Berulang Leasing.
		Debit  : leasing_jurnal_debit
		Credit : leasing_jurnal_kredit
		Nilai  : total_kredit
		"""
		if not doc.total_kredit:
			frappe.throw(_("Total Kredit tidak boleh kosong atau nol."))

		gl_entries = []

		# --- DEBIT ---
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.leasing_jurnal_debit,
				"debit": doc.total_kredit,
				"credit": 0.0,
				"debit_in_account_currency": doc.total_kredit,
				"credit_in_account_currency": 0.0,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"party": doc.vendor,
				"party_type": "Supplier",
				"against_voucher_type": "Purchase Invoice",
				"against_voucher": doc.tarik_purchase_invoice
			})
		)

		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.leasing_jurnal_debit,
				"debit": doc.total_pembayaran_pertama,
				"credit": 0.0,
				"debit_in_account_currency": doc.total_pembayaran_pertama,
				"credit_in_account_currency": 0.0,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"party": doc.vendor,
				"party_type": "Supplier",
				"against_voucher_type": "Purchase Invoice",
				"against_voucher": doc.tarik_purchase_invoice
			})
		)


		total_biaya_admin = doc.biaya_admin+doc.admin_polis

		# biaya admin
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.biaya_admin_account,
				"debit": total_biaya_admin ,
				"credit": 0.0,
				"debit_in_account_currency": total_biaya_admin,
				"credit_in_account_currency": 0.0,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"cost_center" : frappe.db.get_value("Company", doc.company, "cost_center")
			})
		)

		# biaya asuransi
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.biaya_asuransi_account,
				"debit": doc.asuransi_kredit,
				"credit": 0.0,
				"debit_in_account_currency": doc.asuransi_kredit,
				"credit_in_account_currency": 0.0,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"cost_center" : frappe.db.get_value("Company", doc.company, "cost_center")
			})
		)

		# ppn
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.ppn_masukan_account,
				"debit": doc.ppn,
				"credit": 0.0,
				"debit_in_account_currency": doc.ppn,
				"credit_in_account_currency": 0.0,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"cost_center" : frappe.db.get_value("Company", doc.company, "cost_center")
			})
		)

		# --- CREDIT ---
		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": doc.leasing_jurnal_kredit,
				"debit": 0.0,
				"credit": doc.total_kredit + total_biaya_admin + doc.ppn + doc.asuransi_kredit,
				"debit_in_account_currency": 0.0,
				"credit_in_account_currency": doc.total_kredit + total_biaya_admin + doc.ppn + doc.asuransi_kredit,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
			})
		)

		supplier_uang_muka_account = ""

		supplier_uang_muka_account = method_ambil_account.ambil_ap_in_transit_procurement("jasa", self.company)

		gl_entries.append(
			frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": doc.tanggal_invoice,
				"account": supplier_uang_muka_account,
				"debit": 0.0,
				"credit": doc.total_pembayaran_pertama,
				"debit_in_account_currency": 0.0,
				"credit_in_account_currency": doc.total_pembayaran_pertama,
				"voucher_type": doc.doctype,
				"voucher_no": doc.name,
				"company": doc.company,
				"remarks": f"Transaksi Berulang Leasing - {doc.name}",
				"is_opening": "No",
				"party": doc.vendor,
				"party_type": "Supplier",
			})
		)


		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		make_payment_ledger_entry(doc)

		frappe.msgprint(_("GL Entry berhasil dibuat."), indicator="green", alert=True)


	def cancel_gl_entries(doc, method=None):
		"""
		Batalkan (reverse) GL Entry saat dokumen di-cancel.
		"""
		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(doc.doctype, doc.name),
		)
		# --- CANCEL PAYMENT LEDGER ENTRY ---
		frappe.db.sql(
			"""
			UPDATE `tabPayment Ledger Entry`
			SET is_cancelled = 1,
				docstatus    = 2
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(doc.doctype, doc.name),
		)

		frappe.msgprint(_("GL Entry & Payment Ledger Entry berhasil dibatalkan."), indicator="orange", alert=True)


def make_payment_ledger_entry(doc):
	"""
	Buat Payment Ledger Entry untuk melunasi/mengaitkan
	Transaksi Berulang Leasing terhadap Purchase Invoice.
	"""
	# Ambil currency dari Purchase Invoice yang direferensikan
	invoice_currency = frappe.db.get_value(
		"Purchase Invoice",
		doc.tarik_purchase_invoice,
		"currency"
	) or frappe.get_cached_value("Company", doc.company, "default_currency")

	ple = frappe.get_doc({
		"doctype"                        : "Payment Ledger Entry",
		"posting_date"                   : doc.tanggal_invoice,
		"company"                        : doc.company,
		"account_type"                   : "Payable",
		"account"                        : doc.leasing_jurnal_debit,
		"party_type"                     : "Supplier",
		"party"                          : doc.vendor,
		"voucher_type"                   : doc.doctype,
		"voucher_no"                     : doc.name,
		"against_voucher_type"           : "Purchase Invoice",
		"against_voucher_no"             : doc.tarik_purchase_invoice,
		"amount"                         : doc.total_kredit,
		"amount_in_account_currency"     : doc.total_kredit,
		"account_currency"               : invoice_currency,
	})

	ple.flags.ignore_permissions = True
	ple.flags.ignore_mandatory   = True
	ple.insert()

	frappe.db.set_value(
		"Payment Ledger Entry",
		ple.name,
		"docstatus",
		1
	)

# ─────────────────────────────────────────────────────────────────────────────
# Generate jadwal saat submit
# ─────────────────────────────────────────────────────────────────────────────

def _generate_je_schedule(doc) -> None:
	"""
	Hitung semua tanggal jadwal JE dan masukkan ke child table je_log.
	Dipanggil sekali saat on_submit.

	- LEASING     : ambil langsung dari transaksi_berulang_leasing_table
					scheduled_date = tanggal_angsuran
					amount         = pembayaran_pokok
	- Non-LEASING : hitung dari periode_from s/d tanggal_mulai (akumulasi + per-bulan)
	"""
	doc.transaksi_berulang_je_log = []

	# ─────────────────────────────────────────────
	# LEASING: ambil jadwal dari leasing table
	# ─────────────────────────────────────────────
	if doc.jenis_transaksi == "LEASING":
		for row in doc.transaksi_berulang_leasing_table:
			tgl = getdate(row.tanggal_angsuran)
			doc.append("transaksi_berulang_je_log", {
				"doctype"       : "Transaksi Berulang JE Log",
				"parent"        : doc.name,
				"parenttype"    : "Transaksi Berulang",
				"parentfield"   : "transaksi_berulang_je_log",
				"scheduled_date": tgl,
				"amount"        : flt(row.pembayaran_pokok, 2),
				"keterangan"    : (
					f"Angsuran Leasing {tgl.strftime('%B %Y')}"
				),
				"journal_entry" : None,
			})
		return  # selesai, tidak perlu lanjut ke blok non-LEASING

	# ─────────────────────────────────────────────
	# Non-LEASING: hitung jadwal dari periode_from
	# ─────────────────────────────────────────────
	masa         = int(doc.masa_periode)
	monthly_amt  = flt(doc.premi) / masa
	start_date   = getdate(doc.tanggal_mulai)
	periode_from = getdate(doc.periode_from)

	all_dates = [add_months(periode_from, i) for i in range(masa)]

	past   = [d for d in all_dates if d <= start_date]
	future = sorted(d for d in all_dates if d >  start_date)

	accum_count = len(past)
	schedule    = []

	if future:
		if accum_count > 0:
			accum_amt = flt(monthly_amt * accum_count, 2)
			schedule.append({
				"scheduled_date": start_date,
				"amount"        : accum_amt,
				"keterangan"    : (
					f"Akumulasi {accum_count} bulan "
					f"({periode_from.strftime('%d %b %Y')} "
					f"s/d {start_date.strftime('%d %b %Y')})"
					f". No Polis {doc.nomor_polis}."
				),
			})
		for je_date in future:
			schedule.append({
				"scheduled_date": je_date,
				"amount"        : flt(monthly_amt, 2),
				"keterangan"    : (
					f"Amortisasi {je_date.strftime('%B %Y')}"
					f". No Polis {doc.nomor_polis}."
				),
			})
	else:
		schedule.append({
			"scheduled_date": start_date,
			"amount"        : flt(doc.premi),
			"keterangan"    : (
				f"Akumulasi semua {masa} bulan "
				f"({periode_from.strftime('%d %b %Y')} "
				f"s/d {start_date.strftime('%d %b %Y')})"
				f". No Polis {doc.nomor_polis}."
			),
		})

	for row in schedule:
		doc.append("transaksi_berulang_je_log", {
			"doctype"       : "Transaksi Berulang JE Log",
			"parent"        : doc.name,
			"parenttype"    : "Transaksi Berulang",
			"parentfield"   : "transaksi_berulang_je_log",
			"scheduled_date": row["scheduled_date"],
			"amount"        : row["amount"],
			"keterangan"    : row["keterangan"],
			"journal_entry" : None,
		})
# ─────────────────────────────────────────────────────────────────────────────
# Scheduled task – dipanggil Frappe setiap hari
# ─────────────────────────────────────────────────────────────────────────────

def process_scheduled_je() -> None:
	"""
	Entry point untuk scheduler Frappe (daily).
	Daftarkan di hooks.py → scheduler_events → daily.
	"""
	today_date = getdate(today())
	company    = _get_company()

	# Cari semua baris je_log yang sudah due dan belum dibuatkan JE
	due_rows = frappe.db.sql("""
		SELECT
			name,
			parent,
			scheduled_date,
			amount,
			keterangan
		FROM `tabTransaksi Berulang JE Log`
		WHERE scheduled_date <= %s
			AND (journal_entry IS NULL OR journal_entry = '')
			AND docstatus = 1
		ORDER BY scheduled_date ASC
	""", (today_date,), as_dict=True)

	if not due_rows:
		return

	# Group per parent agar get_doc hanya sekali per dokumen
	parent_map: dict[str, list] = {}
	for row in due_rows:
		parent_map.setdefault(row.parent, []).append(row)

	for docname, rows in parent_map.items():
		try:
			doc = frappe.get_doc("Transaksi Berulang", docname)
			if doc.jenis_transaksi == "LEASING":
				return

			_process_due_rows(doc, rows, company)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				frappe.get_traceback(),
				f"Transaksi Berulang – gagal buat JE untuk {docname}",
			)


def _process_due_rows(doc, rows: list, company: str) -> None:
	"""Buat JE untuk setiap baris yang sudah jatuh tempo."""
	for row_data in rows:
		je_name = _make_je(
			doc       = doc,
			company   = company,
			post_date = getdate(row_data.scheduled_date),
			amount    = flt(row_data.amount),
			remark    = f"{row_data.keterangan} — {doc.name}",
		)

		frappe.db.set_value(
			"Transaksi Berulang JE Log",
			row_data.name,
			"journal_entry",
			je_name,
		)

		frappe.logger().info(
			f"[Transaksi Berulang] JE {je_name} dibuat "
			f"({row_data.keterangan}) untuk {doc.name} "
			f"tanggal {row_data.scheduled_date}"
		)


# ─────────────────────────────────────────────────────────────────────────────
# Buat satu Journal Entry
# ─────────────────────────────────────────────────────────────────────────────

def _make_je(doc, company: str, post_date, amount: float, remark: str) -> str:
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.posting_date = post_date
	je.company      = company
	je.user_remark  = remark
	je.transaksi_berulang = doc.name

	cost_center = frappe.db.get_value("Company", company, "cost_center")

	je.append("accounts", {
		"account"                   : doc.jurnal_debit,
		"debit_in_account_currency" : amount,
		"credit_in_account_currency": 0,
		"cost_center"               : cost_center,
	})
	je.append("accounts", {
		"account"                   : doc.jurnal_kredit,
		"debit_in_account_currency" : 0,
		"credit_in_account_currency": amount,
		"cost_center"               : cost_center,
	})
	
	je.insert(ignore_permissions=True)
	je.submit()
	frappe.db.commit()
	return je.name


# ─────────────────────────────────────────────────────────────────────────────
# Cancel: batalkan JE draft yang terkait
# ─────────────────────────────────────────────────────────────────────────────

def _cancel_linked_je(doc) -> None:
	linked = frappe.get_list(
		"Transaksi Berulang JE Log",
		filters={"parent": doc.name, "journal_entry": ["is", "set"]},
		fields=["journal_entry"],
	)
	for row in linked:
		je_doc = frappe.get_doc("Journal Entry", row.journal_entry)
		if je_doc.docstatus == 1:
			je_doc.cancel()
		elif je_doc.docstatus == 0:
			je_doc.delete()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate(doc) -> None:
	required = {
		"tanggal_mulai": "Tanggal Mulai",
		"masa_periode" : "Masa Periode",
		"premi"        : "Premi",
		"jurnal_debit" : "Jurnal Debit (COA)",
		"jurnal_kredit": "Jurnal Kredit (COA)",
	}
	missing = [label for field, label in required.items() if not doc.get(field)]
	if doc.jenis_transaksi != "LEASING":

		if missing:
			frappe.throw(
				f"Field wajib belum diisi: <b>{', '.join(missing)}</b>",
				title="Validasi Gagal",
			)
		if int(doc.masa_periode or 0) <= 0:
			frappe.throw("Masa Periode harus lebih dari 0.", title="Validasi Gagal")
		if flt(doc.premi) <= 0:
			frappe.throw("Premi harus lebih dari 0.", title="Validasi Gagal")


def _get_company() -> str:
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)
	if not company:
		frappe.throw(
			"Default Company belum disetel. Cek Global Defaults atau User Defaults.",
			title="Company Tidak Ditemukan",
		)
	return company


# ─────────────────────────────────────────────────────────────────────────────
# LEASING: Scheduler entry point
# ─────────────────────────────────────────────────────────────────────────────

def process_scheduled_pe_leasing() -> None:
	"""
	Entry point scheduler (daily) – khusus jenis_transaksi == 'LEASING'.
	Daftarkan di hooks.py → scheduler_events → daily.

	Jurnal PE yang terbentuk:
		jurnal_debit              Debit   angsuran
		biaya_bunga_leasing_debit Debit   bunga
		jurnal_kredit             Credit  angsuran + bunga
	"""
	today_date = getdate(today())
	company    = _get_company()

	due_rows = frappe.db.sql("""
		SELECT
			log.name,
			log.parent,
			log.scheduled_date,
			log.keterangan,
			log.idx                          -- posisi baris → kunci ke tabel leasing
		FROM `tabTransaksi Berulang JE Log` log
		INNER JOIN `tabTransaksi Berulang` tb ON tb.name = log.parent
		WHERE log.scheduled_date <= %s
		  AND log.docstatus = 1
		  AND tb.jenis_transaksi = 'LEASING'
		ORDER BY log.scheduled_date ASC
	""", (today_date,), as_dict=True)
	print(due_rows)
	if not due_rows:
		return

	parent_map: dict[str, list] = {}
	for row in due_rows:
		parent_map.setdefault(row.parent, []).append(row)

	for docname, rows in parent_map.items():
		try:
			doc = frappe.get_doc("Transaksi Berulang", docname)
			_process_due_rows_leasing(doc, rows, company)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				frappe.get_traceback(),
				f"Transaksi Berulang LEASING – gagal buat PE untuk {docname}",
			)


# ─────────────────────────────────────────────────────────────────────────────
# Proses baris-baris due untuk satu dokumen
# ─────────────────────────────────────────────────────────────────────────────

def _process_due_rows_leasing(doc, rows: list, company: str) -> None:
	"""Buat Payment Entry untuk setiap baris JE Log leasing yang jatuh tempo."""

	# Bangun lookup idx → baris leasing agar tidak loop O(n²)
	leasing_lookup: dict[int, object] = {
		r.idx: r for r in doc.transaksi_berulang_leasing_table
	}

	for row_data in rows:
		leasing_row = leasing_lookup.get(row_data.idx)

		if not leasing_row:
			frappe.log_error(
				f"idx={row_data.idx} tidak ditemukan di transaksi_berulang_leasing_table "
				f"pada dokumen {doc.name}",
				"Transaksi Berulang LEASING – baris tidak cocok",
			)
			continue

		angsuran = flt(leasing_row.angsuran)
		bunga    = flt(leasing_row.bunga)

		pe_name = _make_pe_leasing(
			doc       = doc,
			company   = company,
			post_date = getdate(row_data.scheduled_date),
			angsuran  = angsuran,
			bunga     = bunga,
			remark    = f"{row_data.keterangan} — {doc.name}",
		)

		# Simpan nama PE ke kolom journal_entry di JE Log
		frappe.db.set_value(
			"Transaksi Berulang JE Log",
			row_data.name,
			"journal_entry",
			pe_name,
		)

		frappe.logger().info(
			f"[Transaksi Berulang LEASING] PE {pe_name} dibuat "
			f"({row_data.keterangan}) untuk {doc.name} "
			f"tanggal {row_data.scheduled_date} | "
			f"angsuran={angsuran} bunga={bunga}"
		)


# ─────────────────────────────────────────────────────────────────────────────
# Buat satu Payment Entry
# ─────────────────────────────────────────────────────────────────────────────

def _make_pe_leasing(
	doc,
	company: str,
	post_date,
	angsuran: float,
	bunga: float,
	remark: str,
) -> str:
	"""
	Buat Payment Entry Internal Transfer untuk angsuran leasing.

	Struktur akun:
		paid_from  = doc.jurnal_kredit   → dikredit  sebesar (angsuran + bunga)
		paid_to    = doc.jurnal_debit    → diddebit  sebesar angsuran
		deductions → biaya_bunga_leasing_debit  sebesar bunga
	"""
	total       = angsuran + bunga
	cost_center = frappe.db.get_value("Company", company, "cost_center")

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type  = "Internal Transfer"
	pe.posting_date  = post_date
	pe.company       = company
	pe.remarks       = remark
	pe.transaksi_berulang = doc.name          # custom link field

	# ── Akun sumber (dikredit) ──────────────────────────────────────────────
	pe.paid_from = doc.jurnal_kredit
	pe.paid_from_account_currency = frappe.db.get_value(
		"Account", doc.jurnal_kredit, "account_currency"
	)
	pe.paid_amount = total                    # keluar dari sumber: angsuran + bunga

	# ── Akun tujuan (didebit / lunasi liability) ────────────────────────────
	pe.paid_to = doc.jurnal_debit
	pe.paid_to_account_currency = frappe.db.get_value(
		"Account", doc.jurnal_debit, "account_currency"
	)
	pe.received_amount = angsuran             # netto ke tujuan: hanya angsuran

	# ── Deduction: beban bunga ──────────────────────────────────────────────
	if bunga:
		pe.append("deductions", {
			"account"     : doc.biaya_bunga_leasing_debit,
			"cost_center" : cost_center,
			"amount"      : bunga,
		})

	pe.insert(ignore_permissions=True)
	pe.submit()
	frappe.db.commit()
	return pe.name


# ─────────────────────────────────────────────────────────────────────────────
# Cancel: batalkan PE yang terkait
# ─────────────────────────────────────────────────────────────────────────────

def _cancel_linked_pe_leasing(doc) -> None:
	"""Batalkan semua Payment Entry yang terkait dengan transaksi berulang leasing."""
	linked = frappe.get_list(
		"Transaksi Berulang JE Log",
		filters={"parent": doc.name, "journal_entry": ["is", "set"]},
		fields=["journal_entry"],
	)
	for row in linked:
		try:
			pe_doc = frappe.get_doc("Payment Entry", row.journal_entry)
			if pe_doc.docstatus == 1:
				pe_doc.cancel()
			elif pe_doc.docstatus == 0:
				pe_doc.delete()
		except frappe.DoesNotExistError:
			pass