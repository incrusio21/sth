import frappe
from frappe import _


class RenameKodeMixin:
	"""Master yang name-nya selalu sama dengan field kode (lihat autoname
	Customer dan Supplier). Kalau kodenya diubah di dokumen yang sudah
	tersimpan, dokumen di-rename ke kode baru beserta semua Link-nya.

	self.name ikut diganti sesudah rename supaya hook on_update sesudahnya dan
	respons simpan membawa nama baru, lalu form pindah ke sana lewat after_save
	di JS masing-masing doctype.
	"""

	kode_field = None

	def kode_baru(self):
		if self.is_new() or self.flags.in_rename:
			return None

		kode = (self.get(self.kode_field) or "").strip()
		if not kode or kode == self.name:
			return None

		return kode

	def validate_kode_baru(self):
		kode = self.kode_baru()
		if kode and frappe.db.exists(self.doctype, kode):
			frappe.throw(
				_("{0} {1} sudah dipakai {2} lain.").format(
					_(self.meta.get_label(self.kode_field)), frappe.bold(kode), _(self.doctype)
				),
				title=_("Kode Dobel"),
			)

	def rename_ke_kode(self):
		kode = self.kode_baru()
		if not kode:
			return

		self.set(self.kode_field, kode)
		frappe.rename_doc(self.doctype, self.name, kode, show_alert=False)

		self.name = kode
		for d in self.get_all_children():
			d.parent = kode

	def after_rename(self, olddn, newdn, merge=False):
		# Bawaan ERPNext menimpa customer_name/supplier_name dengan name baru
		# kalau penamaan master memakai nama. Di sini name adalah kode, bukan
		# nama, jadi nama pelanggan/supplier dibiarkan.
		pass
