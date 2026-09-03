import frappe
from frappe.utils import cint, flt
from frappe import _, bold
from erpnext.accounts.doctype.accounting_period.accounting_period import (
	AccountingPeriod,
	OverlapError,
	ClosedAccountingPeriod
)

from sth.accounting_sth.validasi_closing import tutup_sementara

class SthAccountingPeriod(AccountingPeriod):

	def autoname(self):
		company_abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = " - ".join([self.period_name, company_abbr])

	def validate(self):
		self.validate_overlap()

	def validate_overlap(self):
		existing_accounting_period = frappe.db.sql(
			"""select name, unit from `tabAccounting Period`
			where (
				(%(start_date)s between start_date and end_date)
				or (%(end_date)s between start_date and end_date)
				or (start_date between %(start_date)s and %(end_date)s)
				or (end_date between %(start_date)s and %(end_date)s)
			) and name!=%(name)s and company=%(company)s
			and unit = %(unit)s
			""",
			{
				"start_date": self.start_date,
				"end_date": self.end_date,
				"name": self.name,
				"company": self.company,
				"unit": self.unit
			},
			as_dict=True,
		)

		if len(existing_accounting_period) > 0:
			frappe.throw(
				_("Accounting Period overlaps with {0} - {1}").format(existing_accounting_period[0].get("name"), existing_accounting_period[0].get("unit")),
				OverlapError,
			)
	def on_submit(self):
		post_bkm_on_submit(self)
		create_costing_on_submit(self)

	def on_cancel(self):
		# urutannya kebalikan on_submit: costing dulu baru BKM, supaya costing
		# masih melihat BKM-nya utuh saat dibatalkan.
		cancel_costing_on_cancel(self)
		unpost_bkm_on_cancel(self)

	def on_trash(self):
		delete_costing_on_trash(self)

# BKM yang GL Entry-nya baru dibuat saat periodenya ditutup
BKM_POSTED_ON_PERIOD_SUBMIT = ("Buku Kerja Mandor Panen", "Buku Kerja Mandor Perawatan")

# samakan dengan POSTED di sth.controllers.buku_kerja_mandor. sengaja tidak diimpor:
# modul ini sudah ditarik sth/__init__.py saat app boot, dan ikut menarik seluruh
# controller stack ke sana cuma demi satu konstanta tidak sepadan.
POSTED = "Posted"


def filter_bkm_periode(doc):
	"""BKM submitted milik company/unit/periode Accounting Period ini."""
	return {
		"company": doc.company,
		"unit": doc.unit,
		"posting_date": ["between", [doc.start_date, doc.end_date]],
		"docstatus": 1,
	}


def bkm_state_field(doctype):
	"""
	Fieldname state workflow BKM, atau None kalau doctype-nya belum punya workflow
	aktif. Tanpa workflow GL Entry sudah dibuat sejak submit, jadi tidak ada yang
	perlu diposting maupun dilepas postingnya.
	"""
	workflow = frappe.get_meta(doctype).get_workflow()
	if not workflow:
		return None

	return frappe.get_cached_value("Workflow", workflow, "workflow_state_field") or "workflow_state"


def proses_bkm(daftar, aksi):
	"""
	Jalankan `aksi` (nama method di BukuKerjaMandorController) untuk tiap (doctype,
	name) di daftar. Satu savepoint per dokumen supaya yang gagal tidak menyeret
	yang lain, dan errornya dikumpulkan untuk dirangkum sekali di akhir.
	"""
	gagal = []

	for doctype, name in daftar:
		savepoint = "proses_bkm"
		try:
			frappe.db.savepoint(savepoint)

			bkm = frappe.get_doc(doctype, name)
			bkm.flags.ignore_permissions = True
			getattr(bkm, aksi)()
		except Exception as e:
			# pesan error per dokumen dirangkum di bawah, jangan ditampilkan dua kali
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=savepoint)
			gagal.append((doctype, name, str(e)))

	return gagal


def throw_bkm_gagal(gagal, title, intro):
	if not gagal:
		return

	rows = "".join(
		f"<tr><td>{dt}</td><td>{name}</td><td>{frappe.utils.escape_html(msg)}</td></tr>"
		for dt, name, msg in gagal
	)

	frappe.throw(
		title=title,
		msg="""
			<p>{intro}</p>
			<table class="table table-bordered table-sm" style="margin-top:8px;">
				<thead><tr><th>Doctype</th><th>Document</th><th>Error</th></tr></thead>
				<tbody>{rows}</tbody>
			</table>
		""".format(intro=intro, rows=rows)
	)


def post_bkm_on_submit(doc, method=None):
	"""
	Saat Accounting Period disubmit (workflow_state = "Submitted"), semua BKM Panen &
	Perawatan pada company/unit/periode yang sama dipindahkan ke state Posted sekaligus
	membuat GL Entry-nya.
	"""
	if doc.get("workflow_state") != "Submitted":
		return

	daftar = []

	for doctype in BKM_POSTED_ON_PERIOD_SUBMIT:
		state_field = bkm_state_field(doctype)
		if not state_field:
			continue

		names = frappe.get_all(
			doctype,
			filters=filter_bkm_periode(doc),
			# dokumen lama (sebelum workflow dipasang) state-nya kosong, bukan "Submitted",
			# dan tetap harus ikut ditandai Posted
			or_filters=[
				[doctype, state_field, "!=", POSTED],
				[doctype, state_field, "is", "not set"],
			],
			pluck="name"
		)

		daftar.extend((doctype, name) for name in names)

	throw_bkm_gagal(
		proses_bkm(daftar, "set_as_posted"),
		_("BKM Gagal Diposting"),
		_("Accounting Period tidak dapat disubmit. Dokumen berikut gagal dipindahkan ke state <b>Posted</b>:"),
	)


def unpost_bkm_on_cancel(doc, method=None):
	"""
	Kebalikan post_bkm_on_submit. Saat Accounting Period dibatalkan, BKM Panen &
	Perawatan yang sudah Posted dikembalikan ke Submitted dan GL Entry-nya dihapus,
	supaya periodenya benar-benar terbuka lagi: selama masih Posted, upah dan premi
	BKM tidak bisa dihitung ulang, jadi periode yang batal pun tetap terkunci.

	Tidak dijaga workflow_state: on_cancel hanya jalan saat docstatus benar-benar
	pindah ke 2, dan periode yang batal harus melepas BKM-nya lewat jalur pembatalan
	mana pun. Lihat cancel_costing_on_cancel untuk duduk perkaranya.

	BKM yang dipindah ke Posted manual lewat workflow, bukan lewat closing, ikut
	dilepas. Itu memang yang diinginkan: periodenya dibuka, isinya boleh dikoreksi.
	"""
	daftar = []

	for doctype in BKM_POSTED_ON_PERIOD_SUBMIT:
		state_field = bkm_state_field(doctype)
		if not state_field:
			continue

		filters = filter_bkm_periode(doc)
		filters[state_field] = POSTED

		daftar.extend(
			(doctype, name)
			for name in frappe.get_all(doctype, filters=filters, pluck="name")
		)

	throw_bkm_gagal(
		proses_bkm(daftar, "set_as_unposted"),
		_("BKM Gagal Dilepas Postingnya"),
		_("Accounting Period tidak dapat dibatalkan. Dokumen berikut gagal dikembalikan ke state <b>Submitted</b>:"),
	)


# Costing yang dibuat sekalian waktu Accounting Period ditutup, berikut
# builder-nya. Semuanya membaca dokumen sumber — slip gaji, BKM, pengeluaran
# barang — bukan hasil costing lain, jadi urutan daftar ini tidak mengikat. Yang
# harus lebih dulu cuma posting BKM, dan itu sudah dikerjakan di on_submit.
#
# Builder yang mendapati periodenya kosong mengembalikan None tanpa membuat
# dokumen, jadi unit kebun tidak ditinggali Costing Mill kosong tiap bulan,
# begitu juga sebaliknya. Costing Bengkel tetap dibuat apa adanya seperti
# sebelumnya.
COSTING_OTOMATIS = (
	{
		"doctype": "Costing Bengkel",
		"builder": "sth.accounting_sth.doctype.costing_bengkel.costing_bengkel.build_and_submit_costing_bengkel",
	},
	{
		"doctype": "Costing Mill",
		"builder": "sth.accounting_sth.doctype.costing_mill.costing_mill.build_and_submit_costing_mill",
	},
	{
		"doctype": "Costing Panen",
		"builder": "sth.accounting_sth.costing_kebun.build_and_submit_costing_kebun",
		"args": {"doctype": "Costing Panen"},
	},
	{
		"doctype": "Costing Perawatan",
		"builder": "sth.accounting_sth.costing_kebun.build_and_submit_costing_kebun",
		"args": {"doctype": "Costing Perawatan"},
	},
)


def filter_costing_periode(doc, docstatus=None):
	filters = {
		"company": doc.company,
		"unit": doc.unit,
		"periode_dari": doc.start_date,
		"periode_sampai": doc.end_date,
	}

	if docstatus is not None:
		filters["docstatus"] = docstatus

	return filters


def create_costing_on_submit(doc, method=None):
	"""
	Saat Accounting Period disubmit (workflow_state = "Submitted"), buat & submit
	seluruh costing otomatis dengan periode/company/unit yang sama.
	Dicek dulu supaya tidak dobel kalau doc disimpan ulang saat sudah Submitted.

	Satu costing yang gagal tidak menghentikan sisanya: yang gagal dibatalkan
	sampai savepoint-nya lalu dirangkum di akhir, supaya sekali submit ketahuan
	semua yang perlu dibereskan, bukan satu per satu.
	"""
	if doc.get("workflow_state") != "Submitted":
		return

	gagal = []

	for costing in COSTING_OTOMATIS:
		doctype = costing["doctype"]

		if frappe.db.exists(doctype, filter_costing_periode(doc, ["!=", 2])):
			continue

		savepoint = "buat_costing"
		try:
			frappe.db.savepoint(savepoint)

			args = dict(costing.get("args") or {})
			args.update({
				"company": doc.company,
				"unit": doc.unit,
				"periode_dari": doc.start_date,
				"periode_sampai": doc.end_date,
			})

			frappe.get_attr(costing["builder"])(**args)
		except Exception as e:
			# pesan error per costing dirangkum di bawah, jangan ditampilkan dua kali
			if frappe.message_log:
				frappe.message_log.pop()

			frappe.db.rollback(save_point=savepoint)
			gagal.append((doctype, str(e)))

	if gagal:
		rows = "".join(
			f"<tr><td>{dt}</td><td>{frappe.utils.escape_html(msg)}</td></tr>"
			for dt, msg in gagal
		)

		frappe.throw(
			title=_("Costing Gagal Dibuat"),
			msg=_("""
				<p>Accounting Period tidak dapat disubmit. Costing berikut gagal dibuat:</p>
				<table class="table table-bordered table-sm" style="margin-top:8px;">
					<thead><tr><th>Doctype</th><th>Error</th></tr></thead>
					<tbody>{rows}</tbody>
				</table>
			""").format(rows=rows)
		)


@frappe.whitelist()
def buat_costing_periode(accounting_period):
	"""Bangun costing untuk Accounting Period yang sudah terlanjur ditutup.

	Hook-nya cuma jalan sekali waktu submit, jadi periode yang ditutup sebelum
	costing ini ikut otomatis tidak punya dokumennya. Yang sudah ada dilewati,
	jadi aman dipanggil ulang:

		bench --site <site> execute sth.overrides.accounting_period.buat_costing_periode --args "['JULI 2026 - TML']"
	"""
	doc = frappe.get_doc("Accounting Period", accounting_period)
	create_costing_on_submit(doc)


def cancel_costing_on_cancel(doc, method=None):
	"""
	Saat Accounting Period dibatalkan, cancel juga seluruh costing yang otomatis
	dibuat untuk company/unit/periode yang sama.

	Dulu fungsi ini dijaga `workflow_state in ("Canceled", "Cancelled")`. Guard itu
	dicabut karena menyaring jalur pembatalan, bukan memastikan dokumennya batal:
	on_cancel sendiri hanya dipanggil saat docstatus benar-benar pindah ke 2. Yang
	menulis workflow_state cuma transisi workflow — doc.cancel() langsung (bench
	console, API, patch) meninggalkannya di "Submitted", jadi costing-nya diam-diam
	tidak ikut dibatalkan padahal periodenya sudah batal.

	Sekarang sejajar dengan unpost_bkm_on_cancel: keduanya jalan lewat jalur
	pembatalan mana pun.
	"""
	for costing in COSTING_OTOMATIS:
		doctype = costing["doctype"]

		for name in frappe.get_all(doctype, filters=filter_costing_periode(doc, 1), pluck="name"):
			cd = frappe.get_doc(doctype, name)
			cd.flags.ignore_links = True
			cd.flags.ignore_permissions = True
			cd.cancel()


def delete_costing_on_trash(doc, method=None):
	"""
	Saat Accounting Period dihapus, ikut hapus seluruh costing yang otomatis
	dibuat untuk company/unit/periode yang sama. Yang masih submitted
	dibatalkan dulu sebelum dihapus.
	"""
	for costing in COSTING_OTOMATIS:
		doctype = costing["doctype"]

		for name in frappe.get_all(doctype, filters=filter_costing_periode(doc), pluck="name"):
			cd = frappe.get_doc(doctype, name)
			if cd.docstatus == 1:
				cd.flags.ignore_links = True
				cd.flags.ignore_permissions = True
				cd.cancel()

			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def validate_accounting_period_on_doc_save(doc, method=None):
	if doc.doctype == "Bank Clearance":
		return
	elif doc.doctype == "Asset":
		if doc.is_existing_asset:
			return
		else:
			date = doc.available_for_use_date
	elif doc.doctype == "Asset Repair":
		date = doc.completion_date
	elif doc.doctype == "Period Closing Voucher":
		date = doc.period_end_date
	else:
		date = doc.posting_date

	ap = frappe.qb.DocType("Accounting Period")
	cd = frappe.qb.DocType("Closed Document")

	accounting_period = (
		frappe.qb.from_(ap)
		.from_(cd)
		.select(ap.name)
		.where(
			(ap.name == cd.parent)
			& (ap.company == doc.company)
			& (cd.closed == 1)
			& (cd.document_type == doc.doctype)
			& (date >= ap.start_date)
			& (date <= ap.end_date)
			& (ap.unit == doc.unit)
			& (ap.workflow_state == "Submitted")
		)
	).run(as_dict=1)

	if accounting_period:
		frappe.throw(
			_("You cannot create a {0} within the closed Accounting Period {1} Unit {2}").format(
				doc.doctype, frappe.bold(accounting_period[0]["name"]), frappe.bold(doc.unit)
			),
			ClosedAccountingPeriod,
		)

	# frappe.throw(
	# 	title=_("Closing Periode Tidak Dapat Dilanjutkan"),
	# 	msg=_("""
	# 		<p>Closing periode tidak dapat dilanjutkan karena:</p>
	# 		{msg}
	# 		<p style="margin-top:12px;">Silakan selesaikan item-item di atas sebelum melakukan closing.</p>
	# 	""").format(msg=msg)
	# )


@frappe.whitelist()
def check_unsubmitted_salary_slip(self, method):
	"""
	Cek Salary Slip yang masih Draft (belum disubmit) dalam periode Accounting Period.
	Accounting Period tidak boleh disubmit selama masih ada Salary Slip Draft di periode tsb.

	Dilewati untuk periode yang ditutup sementara, sama seperti pemeriksaan
	kesiapan closing yang lain.
	"""
	if tutup_sementara(self):
		return

	result = frappe.db.sql("""
		SELECT ss.name, ss.employee, ss.employee_name, ss.start_date, ss.end_date
		FROM `tabSalary Slip` ss
		WHERE ss.docstatus = 0
		  AND ss.company = %(company)s
		  AND ss.unit = %(unit)s
		  AND ss.start_date <= %(end)s
		  AND ss.end_date >= %(start)s
	""", {
		'company': self.company,
		'unit': self.unit,
		'start': self.start_date,
		'end': self.end_date,
	}, as_dict=True)

	if result:
		rows = "".join([
			f"<tr><td>{r.name}</td><td>{r.employee} - {r.employee_name}</td><td>{r.start_date}</td><td>{r.end_date}</td></tr>"
			for r in result
		])

		frappe.throw(
			title=_("Salary Slip Belum Disubmit"),
			msg=_("""
				<p>Accounting Period tidak dapat disubmit. Masih terdapat <b>Salary Slip</b> berstatus Draft
				dalam periode ini:</p>
				<table class="table table-bordered table-sm" style="margin-top:8px;">
					<thead>
						<tr>
							<th>Salary Slip</th>
							<th>Employee</th>
							<th>Start Date</th>
							<th>End Date</th>
						</tr>
					</thead>
					<tbody>{rows}</tbody>
				</table>
				<p>Silakan submit atau batalkan Salary Slip tersebut terlebih dahulu.</p>
			""").format(rows=rows)
		)

	submitted_count = frappe.db.count("Salary Slip", {
		"docstatus": 1,
		"company": self.company,
		"unit": self.unit,
		"start_date": ["<=", self.end_date],
		"end_date": [">=", self.start_date],
	})

	if not submitted_count:
		frappe.throw(
			title=_("Salary Slip Belum Ada"),
			msg=_("""
				<p>Accounting Period tidak dapat disubmit. Belum ada <b>Salary Slip</b> berstatus Submitted
				dalam periode ini.</p>
			""")
		)
