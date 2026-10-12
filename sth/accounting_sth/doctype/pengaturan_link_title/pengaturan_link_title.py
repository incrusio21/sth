# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

# Satu tempat untuk mengatur Link Title — field link yang menampilkan judul
# dokumen (mis. nama barang) alih-alih nama dokumennya (kode barang).
#
# Tabel pertama dipasang sebagai Property Setter show_title_field_in_link dan
# title_field, sama seperti yang dibuat Customize Form, jadi server (load form,
# pencarian link) dan desk membacanya dengan cara yang sama. Bedanya, master ini
# yang memegang nilainya: setelah setiap migrate semua barisnya dipasang ulang,
# sehingga Property Setter yang hilang — direset dari Customize Form, tertimpa
# ekspor customization dari site lain, atau DocType yang dimuat ulang dari JSON
# app-nya — kembali sendiri tanpa ada yang perlu ingat.
#
# Tabel kedua menggantikan pembungkus frappe.utils.get_link_title yang dulu ada
# di JS Material Request, Sales Invoice, dan Pertanggungjawaban Perjalanan Dinas.
# Lihat public/js/override/link_title.js.

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.document import Document
from frappe.utils import cint, cstr


class PengaturanLinkTitle(Document):
	def validate(self):
		self.validate_doctype_link_title()
		self.validate_pengecualian()

	def on_update(self):
		# Baris yang dibuang dari tabel dikembalikan ke bawaan doctype-nya, supaya
		# Property Setter-nya tidak tertinggal tanpa ada yang mengurus. title_field
		# dibiarkan: Property Setter-nya bisa saja sudah ada sebelum master ini.
		sebelum = self.get_doc_before_save()
		if sebelum:
			sekarang = {d.document_type for d in self.doctype_link_title}
			for d in sebelum.doctype_link_title:
				if d.document_type not in sekarang and frappe.db.exists("DocType", d.document_type):
					atur_property(d.document_type, "show_title_field_in_link", None)

		terapkan(self)

		# Daftar link_title_doctypes dan aturan pengecualian ikut di boot, yang
		# di-cache per user. Tanpa ini perubahan baru terlihat sesudah logout.
		frappe.cache.delete_key("bootinfo")

	def validate_doctype_link_title(self):
		sudah = set()
		for d in self.doctype_link_title:
			if d.document_type in sudah:
				frappe.throw(_("Baris {0}: Doctype {1} sudah ada di tabel").format(d.idx, d.document_type))
			sudah.add(d.document_type)

			meta = frappe.get_meta(d.document_type)
			if meta.istable or meta.issingle:
				frappe.throw(_("Baris {0}: {1} tidak bisa dituju field Link").format(d.idx, d.document_type))

			if d.title_field and not meta.has_field(d.title_field):
				frappe.throw(
					_("Baris {0}: {1} tidak punya field {2}").format(d.idx, d.document_type, d.title_field)
				)

			# title_field kosong berarti ikut title field doctype-nya sekarang, dan
			# tanpa itu tidak ada judul yang bisa ditampilkan.
			if cint(d.tampilkan) and not (d.title_field or meta.title_field):
				frappe.throw(
					_("Baris {0}: {1} belum punya title field, isi Title Field-nya").format(
						d.idx, d.document_type
					)
				)

	def validate_pengecualian(self):
		sudah = set()
		for d in self.pengecualian:
			kunci = (d.di_doctype, d.document_type or "")
			if kunci in sudah:
				frappe.throw(_("Baris {0}: pengecualian ini sudah ada di tabel").format(d.idx))
			sudah.add(kunci)


def terapkan(doc=None):
	"""Samakan Property Setter tiap doctype dengan baris master."""
	doc = doc or frappe.get_single("Pengaturan Link Title")

	for d in doc.doctype_link_title:
		# Doctype dari app yang sudah dilepas: barisnya dibiarkan, tidak ada yang
		# bisa dipasangi.
		if not frappe.db.exists("DocType", d.document_type):
			continue

		# title_field dulu: show_title_field_in_link tidak ada artinya tanpa itu.
		if d.title_field:
			atur_property(d.document_type, "title_field", d.title_field, "Data")

		atur_property(d.document_type, "show_title_field_in_link", cint(d.tampilkan), "Check")


def atur_property(doctype, prop, nilai, property_type="Check"):
	"""Pasang Property Setter `prop` doctype ke `nilai`, atau hapus kalau sama dengan bawaan.

	Bawaannya dibaca dari baris DocType, yang tidak pernah diubah Property Setter.
	Nilai yang sama dengan bawaan tidak perlu Property Setter, dan `nilai` None
	berarti kembali ke bawaan.
	"""
	bawaan = frappe.db.get_value("DocType", doctype, prop)
	filters = {"doc_type": doctype, "property": prop, "doctype_or_field": "DocType"}
	ada = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)

	if nilai is None or cstr(nilai) == cstr(bawaan):
		if not ada:
			return
		frappe.db.delete("Property Setter", filters)
	else:
		if ada and cstr(ada.value) == cstr(nilai):
			return
		make_property_setter(
			doctype,
			None,
			prop,
			nilai,
			property_type,
			for_doctype=True,
			validate_fields_for_doctype=False,
			is_system_generated=False,
		)

	frappe.clear_cache(doctype=doctype)


def terapkan_setelah_migrate():
	"""after_migrate: jalan sesudah sync_customizations, jadi apa pun yang dibawa
	berkas custom/*.json soal Link Title, master ini yang terakhir menentukan."""
	terapkan()


def isi_boot(bootinfo):
	"""Aturan master untuk desk, dibaca link_title.js.

	frappe mengisi bootinfo.link_title_doctypes sesudah boot_session, dan isinya
	tetap memuat doctype yang JSON-nya menyalakan show_title_field_in_link walau
	Property Setter-nya sudah mematikan. Jadi daftar doctype yang dimatikan
	dikirim terpisah dan disaring di desk.
	"""
	# Sebelum migrate pertama sesudah deploy tabelnya belum ada, dan boot yang
	# gagal berarti tidak ada yang bisa masuk desk.
	if not frappe.db.table_exists("Pengaturan Link Title Doctype"):
		return

	doc = frappe.get_cached_doc("Pengaturan Link Title")

	# Nilai None berarti semua link di doctype itu menampilkan nama dokumennya.
	disembunyikan = {}
	for d in doc.pengecualian:
		if not d.document_type:
			disembunyikan[d.di_doctype] = None
		elif disembunyikan.get(d.di_doctype, []) is not None:
			disembunyikan.setdefault(d.di_doctype, []).append(d.document_type)

	bootinfo.sth_link_title = {
		"nonaktif": [d.document_type for d in doc.doctype_link_title if not cint(d.tampilkan)],
		"disembunyikan": disembunyikan,
	}
