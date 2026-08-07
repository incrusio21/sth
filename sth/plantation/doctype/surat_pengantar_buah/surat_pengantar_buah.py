# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
import re
import frappe
from frappe import unscrub
from frappe.model.meta import get_field_precision
from frappe.utils import cint, cstr, flt
from frappe.model.document import Document
from frappe.utils.synchronization import filelock

force_item_fields = (
	"recap_panen"
)

class SuratPengantarBuah(Document):

	def validate(self):
		for row in self.details:
			if row.total_janjang and not row.qty:
				row.qty = row.total_janjang

		self.remove_input_pks()
		self.set_missing_value()
		self.validate_recap_panen()
		self.calculate_janjang()

	def remove_input_pks(self):
		self.in_time = self.out_time = self.in_time_internal = self.out_time_internal = ""
		self.in_weight = self.in_weight_internal = self.out_weight = self.out_weight_internal = self.mill_cut = 0

	def set_missing_value(self):
		def _apply_recap(detail, suffix=""):
			blok = detail.get(f"blok{suffix}")
			panen_date = detail.get(f"panen_date{suffix}")
			
			ret = get_recap_panen(blok, panen_date)
			
			for fieldname, value in ret.items():
				target_field = f"{fieldname}{suffix}"
				
				if not (detail.meta.get_field(target_field) and value is not None):
					continue
				
				if detail.get(target_field) is None or target_field in force_item_fields:
					detail.set(target_field, value)

		doctype, fieldname, nopol = ["Driver", "kendaraan_eksternal", "custom_license_plate"]if self.tipe_kendaraan == "External" else ["Alat Berat Dan Kendaraan", "kendaraan", "no_pol"] 
		self.no_polisi = frappe.get_value(doctype, self.get(fieldname), nopol)

		for d in self.details:
			_apply_recap(d)

			# Process restan recap if exists
			if d.blok_restan and d.panen_date_restan:
				_apply_recap(d, suffix="_restan")

	def validate_recap_panen(self):
		# SPB bisa dibuat sebagai stub tanpa detail (mis. dari Security Check Point),
		# dan isin([]) menghasilkan "IN ()" yang bukan SQL valid di MariaDB.
		recap_panen = list({d.recap_panen for d in self.details if d.recap_panen})
		if not recap_panen:
			return

		rpb = frappe.qb.DocType("Recap Panen by Blok")

		query = (
			frappe.qb.from_(rpb)
			.select(rpb.kontanan, rpb.voucher_no)
			.where(
				(rpb.voucher_type == "Buku Kerja Mandor Panen") &
				(rpb.name.isin(recap_panen))
			)
		).run(as_dict=True)

		kontanan = [r.voucher_no for r in query if r.kontanan]
		non_kontanan = [r.voucher_no for r in query if not r.kontanan]

		errors = []

		if kontanan:
			e_kontanan = frappe.db.exists("Pengajuan Panen Kontanan", {
				"bkm_panen": ["in", kontanan], 
				"docstatus": 1
			})
			if e_kontanan:
				errors.append("Some harvests already have submitted Kontanan")

		if non_kontanan:
			p_payment = frappe.db.exists("Employee Payment Log", {
				"voucher_type": "Buku Kerja Mandor Panen",
				"voucher_no": ["in", non_kontanan], 
				"is_paid": 1
			})
			if p_payment:
				errors.append("Some harvests have already been paid")

		if errors:
			frappe.throw("<br>".join(errors))

	def calculate_janjang(self):
		total_janjang = 0.0
		total_brondolan = 0.0
		for d in self.details:

			if not d.blok_restan:
				d.qty_restan = 0

			d.total_janjang = (d.qty or 0) + d.qty_restan

			total_janjang += d.total_janjang
			total_brondolan += flt(d.brondolan_terkirim)

			d.total_weight = 0.0

		self.total_janjang = total_janjang
		self.total_brondolan = total_brondolan

	def on_submit(self):
		self.update_transfered_bkm_panen()

	def on_cancel(self):
		self.update_transfered_bkm_panen()

	def update_transfered_bkm_panen(self):
		for d in self.details:
			for field in ("", "_restan"):
				if recap := d.get(f"recap_panen{field}"):
					doc = frappe.get_doc("Recap Panen by Blok", recap)
					doc.calculate_transfered_weight()

	def before_update_after_submit(self):
		if self.workflow_state != "Weighed":
			return
		
		self.weighed_cannot_update()

	def weighed_cannot_update(self):
		if not (self.out_weight and self.in_weight):
			frappe.throw("Set Weight before Save")

		doc_before = self._doc_before_save

		in_time_unchanged = doc_before.in_time == self.in_time
		out_time_unchanged = doc_before.out_time == self.out_time
		in_weight_unchanged = doc_before.in_weight == self.in_weight
		out_weight_unchanged = doc_before.out_weight == self.out_weight
		mill_cut_unchanged = doc_before.mill_cut == self.mill_cut
		
		in_time_internal_unchanged = doc_before.in_time_internal == self.in_time_internal
		out_time_internal_unchanged = doc_before.out_time_internal == self.out_time_internal
		in_weight_internal_unchanged = doc_before.in_weight_internal == self.in_weight_internal
		out_weight_internal_unchanged = doc_before.out_weight_internal == self.out_weight_internal
		
		if not (
			in_time_unchanged
			and out_time_unchanged
			and in_weight_unchanged
			and out_weight_unchanged
			and mill_cut_unchanged
			and in_time_internal_unchanged
			and out_time_internal_unchanged
			and in_weight_internal_unchanged
			and out_weight_internal_unchanged
		):
			frappe.throw("Weigh cannot be changed")
			
	@frappe.whitelist()
	def set_pabrik_weight(self, args):
		if isinstance(args, str):
			args = json.loads(args)
		
		self.update(args)
		self._calculate_weight()

		self.flags.ignore_validate_update_after_submit = True
		self.save()

	def _calculate_weight(self):
		self.calculate_total_weight()
		self.calculate_weight_in_blok()

	def calculate_total_weight(self):
		if self.out_weight and self.in_weight:
			self.total_weight = flt(self.in_weight - self.out_weight - self.mill_cut, self.precision("total_weight"))
			self.bjr = flt(self.total_weight / self.total_janjang, self.precision("bjr"))
		
		if self.total_weight < 0:
			frappe.throw("Out weight is greater than In weight")

		if self.out_weight_internal and self.in_weight_internal:
			self.total_weight_internal = flt(self.out_weight_internal - self.in_weight_internal, self.precision("total_weight_internal"))
			self.bjr_internal = flt(self.total_weight_internal / self.total_janjang, self.precision("bjr"))

		if self.total_weight_internal < 0:
			frappe.throw("Out weight is greater than In weight")

	def calculate_weight_in_blok(self):
		precision = get_field_precision(
			frappe.get_meta("SPB Timbangan Pabrik").get_field("total_weight")
		)
		for d in self.details:
			d.total_weight = flt(self.total_weight * d.total_janjang / self.total_janjang, precision)

@frappe.whitelist()
def create_or_update(**kwargs):
	args = kwargs
	trans_no = cstr(args.get("trans_no")).strip()

	if not trans_no:
		return _insert_spb(args)

	# Dua panggilan API dengan trans_no yang sama bisa masuk barengan. Tanpa lock
	# keduanya sama-sama melihat "belum ada" lalu masing-masing insert SPB baru.
	with filelock(_trans_no_lock_name(trans_no), timeout=60):
		# Mulai transaksi baru supaya baris yang baru saja di-commit oleh request
		# yang antre sebelum kita ikut terbaca (bukan snapshot lama).
		frappe.db.commit()

		existing_name = _get_spb_by_trans_no(trans_no)

		if not existing_name:
			doc = _insert_spb(args, catch_duplicate=True)

			if doc:
				# commit selagi lock masih dipegang, supaya request berikutnya
				# pasti melihat SPB ini dan masuk ke jalur update.
				frappe.db.commit()
				return doc

			existing_name = _get_spb_by_trans_no(trans_no)
			if not existing_name:
				frappe.throw(f"Failed to create Surat Pengantar Buah for Trans No {trans_no}")

		return _update_spb(existing_name, args)

def _trans_no_lock_name(trans_no):
	return "spb-trans-no-" + re.sub(r"[^A-Za-z0-9]+", "-", trans_no)[:64]

def _get_spb_by_trans_no(trans_no):
	return frappe.db.get_value("Surat Pengantar Buah", {"trans_no": trans_no}, "name")

def _insert_spb(args, catch_duplicate=False):
	def _insert():
		doc = frappe.get_doc(dict(args, doctype="Surat Pengantar Buah"))

		submit_after_insert = doc.docstatus == 1
		if submit_after_insert:
			doc.docstatus = 0

		doc.insert(ignore_permissions=True)

		if submit_after_insert:
			doc.submit()

		return doc

	if not catch_duplicate:
		return _insert()

	# Unique index pada trans_no adalah penjaga terakhir kalau lock tidak berlaku
	# (mis. worker jalan di node lain). Rollback ke savepoint supaya transaksi
	# request ini tetap bisa dipakai untuk jalur update.
	save_point = "spb_insert"
	frappe.db.sql(f"savepoint {save_point}")
	try:
		return _insert()
	except (frappe.UniqueValidationError, frappe.DuplicateEntryError):
		frappe.db.sql(f"rollback to savepoint {save_point}")
		return None

# Field yang tidak boleh ikut ditimpa args saat memperbarui SPB draft: identitas
# dokumen, penanda transaksi, dan detail yang punya jalur pembaruannya sendiri.
_SKIP_HEADER_FIELDS = {
	"doctype", "name", "owner", "creation", "modified", "modified_by",
	"naming_series", "amended_from", "trans_no", "docstatus", "details",
}

def _update_spb(existing_name, args):
	doc = frappe.get_doc("Surat Pengantar Buah", existing_name)
	details = args.get("details") or []

	if doc.docstatus == 0:
		# SPB draft bisa berasal dari stub yang dibuat Security Check Point, yang
		# baru berisi company/unit/divisi. Data panen yang sebenarnya baru datang
		# di panggilan ini, jadi header ikut diperbarui, bukan cuma detailnya.
		_apply_header(doc, args)
		_apply_details(doc, details)
		doc.save(ignore_permissions=True)

		if cint(args.get("docstatus")) == 1:
			doc.submit()
	else:
		# Dokumen sudah submit: hanya detail dan totalnya yang boleh disentuh,
		# lewat db_set supaya tidak kena validate_update_after_submit.
		_apply_details(doc, details)

		doc.update_child_table("details")
		doc.db_set({
			"total_janjang": sum(flt(d.total_janjang) for d in doc.details),
			"total_brondolan": sum(flt(d.brondolan_terkirim) for d in doc.details)
		}, notify=False)

	_resync_timbangan(doc.name)

	frappe.db.commit()

	return doc

def _apply_header(doc, args):
	doc.update({
		key: value for key, value in args.items()
		if key not in _SKIP_HEADER_FIELDS and doc.meta.has_field(key)
	})

def _apply_details(doc, details):
	existing_by_harvest_no = {d.harvest_no: d for d in doc.details if d.harvest_no}

	for d in details:
		harvest_no = d.get("harvest_no")
		row = existing_by_harvest_no.get(harvest_no) or doc.append("details", {})

		row.update({
			"harvest_no": harvest_no,
			"blok": d.get("blok"),
			"panen_date": d.get("panen_date"),
			"total_janjang": flt(d.get("total_janjang")),
			"janjang_sisa": flt(d.get("janjang_sisa")),
			"brondolan_terkirim": flt(d.get("brondolan_terkirim")),
			"brondolan_sisa": flt(d.get("brondolan_sisa")),
		})

def _resync_timbangan(spb_name):
	"""Hitung ulang data timbang di SPB kalau truknya sudah pernah ditimbang.

	Berat, jam timbang, dan BJR diisi Timbangan saat submit. Untuk SPB yang
	dibuat otomatis dari Security Check Point, janjangnya baru datang sesudah
	itu — tanpa hitung ulang, BJR-nya tertinggal 0.
	"""
	timbangan = frappe.db.get_value("Timbangan", {"spb": spb_name, "docstatus": 1}, "name")
	if not timbangan:
		return

	frappe.get_doc("Timbangan", timbangan).update_spb_weight()

@frappe.whitelist()
def get_recap_panen(blok, posting_date):
	filters = {
		"blok": blok, "posting_date": posting_date
	}
	ress = {}
	try:
		recap_panen = frappe.get_value("Recap Panen by Blok", filters, [
			"name", "jumlah_janjang", "transfered_janjang"
		], as_dict=1)

		if not recap_panen:
			message = "Recap Panen by Blok not Found for Filters"
			for key, value in filters.items():
				message += f"<br>{unscrub(key)}: {value}"
				
			frappe.throw(message)
		
		ress = { 
			"recap_panen": recap_panen.name,
			"qty": flt(recap_panen.jumlah_janjang - recap_panen.transfered_janjang)
		}
	except:
		ress = {}

	return ress