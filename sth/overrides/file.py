# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Unggahan tidak lagi disatukan hanya karena isinya kebetulan sama.

Frappe menyatukan dua unggahan berisi identik ke satu berkas di disk: yang kedua
tidak ditulis sama sekali, `file_url`-nya diarahkan ke berkas yang pertama, dan
yang terunduh jadi nama lama meski `file_name` barisnya sendiri berbeda. Hemat
disk, tapi di sini nama berkas ikut jadi informasi — dokumen dengan isi sama
milik periode atau unit yang berbeda tidak boleh saling menimpa namanya.
"""

import frappe
from frappe.core.doctype.file.file import File as FrappeFile


class File(FrappeFile):
	def save_file(self, content=None, decode=False, ignore_existing_file_check=False, overwrite=False):
		"""Selalu tulis berkasnya sendiri, jangan menumpang berkas yang sudah ada.

		`generate_file_name` milik frappe tetap yang menjaga tabrakan nama: nama yang
		sudah terpakai di disk diberi akhiran hash isinya.
		"""
		return super().save_file(
			content=content,
			decode=decode,
			ignore_existing_file_check=True,
			overwrite=overwrite,
		)

	def validate_duplicate_entry(self):
		"""Pencarian duplikatnya dibuang, perhitungan content_hash-nya dipertahankan.

		Core memakai method ini untuk dua hal sekaligus. Yang diarahkan ulang ke
		berkas lama cuma bagian `file_url`-nya; `content_hash` tetap harus terisi
		karena dipakai di tempat lain, termasuk baris File yang dibuat dari url
		tanpa membawa isi.
		"""
		if self.is_folder:
			return

		if not self.content_hash:
			self.generate_content_hash()

	def _delete_file_on_disk(self):
		"""Patokan berbagi berkas jadi file_url, bukan content_hash.

		Core beranggapan dua baris berisi sama pasti menempati satu berkas, benar
		selama dedup menyala. Di sini tidak lagi, jadi patokan lama membuat berkas
		yang dihapus tertinggal di disk selamanya hanya karena ada baris lain yang
		isinya kebetulan sama. file_url menjawab persis yang ditanya: masih ada baris
		lain yang menunjuk berkas ini atau tidak. Baris lama yang memang berbagi
		url — peninggalan sebelum dedup dimatikan — tetap terlindungi.
		"""
		berkas_tidak_dipakai_baris_lain = self.file_url and not frappe.get_all(
			"File",
			filters={
				"file_url": self.file_url,
				"name": ["!=", self.name],
			},
			limit=1,
		)

		if berkas_tidak_dipakai_baris_lain:
			self.delete_file_data_content()
		else:
			self.delete_file_data_content(only_thumbnail=True)
