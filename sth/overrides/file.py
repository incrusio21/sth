# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

"""Unggahan tidak lagi disatukan hanya karena isinya kebetulan sama.

Frappe menyatukan dua unggahan berisi identik ke satu berkas di disk: yang kedua
tidak ditulis sama sekali, `file_url`-nya diarahkan ke berkas yang pertama, dan
yang terunduh jadi nama lama meski `file_name` barisnya sendiri berbeda. Hemat
disk, tapi di sini nama berkas ikut jadi informasi — dokumen dengan isi sama
milik periode atau unit yang berbeda tidak boleh saling menimpa namanya.

Tabrakan nama juga tidak lagi diberi akhiran hash isi (`laporan3f9a1c.pdf`) yang
tidak bisa dikenali. Lampiran dokumen modul Legal menimpa berkas lama: akta atau
sertifikat yang diunggah ulang adalah versi baru dari berkas yang sama, jadi isinya
diganti dan baris File lain yang menunjuk berkas itu dihapus supaya tinggal satu
baris. Di luar Legal nama yang sama tidak berarti berkas yang sama — `depan.jpeg`
atau `1.jpg` dipakai banyak dokumen Security Check Point dan Driver sekaligus —
jadi unggahan baru diberi nomor seperti Windows: `laporan (1).pdf`, `laporan (2).pdf`.
"""

import mimetypes
import os
import re

import frappe
from frappe.core.doctype.file.file import File as FrappeFile
from frappe.core.doctype.file.utils import get_content_hash
from frappe.utils import cint, get_files_path, get_hook_method

MODUL_TIMPA = "Legal"


def nama_aman(file_name):
	"""Nama berkas di disk, sama dengan yang ditulis save_file_on_filesystem."""
	return re.sub(r"[/\\%?#]", "_", file_name)


def url_berkas(file_name, is_private):
	return f"{'/private' if cint(is_private) else ''}/files/{nama_aman(file_name)}"


def path_berkas(file_name, is_private):
	return get_files_path(nama_aman(file_name), is_private=cint(is_private))


def dari_modul_timpa(doctype):
	return bool(doctype) and frappe.db.get_value("DocType", doctype, "module", cache=True) == MODUL_TIMPA


def boleh_menimpa(doctype, file_url):
	"""Berkas di url itu boleh ditimpa unggahan baru untuk doctype ini.

	Semua baris yang sudah menunjuk url itu juga harus milik modul Legal: akta yang
	kebetulan bernama sama dengan foto Security Check Point tidak boleh mengganti
	foto itu.
	"""
	return dari_modul_timpa(doctype) and all(
		dari_modul_timpa(dt)
		for dt in frappe.get_all(
			"File", filters={"file_url": file_url, "is_folder": 0}, pluck="attached_to_doctype"
		)
	)


def nama_bernomor(file_name, is_private):
	"""Nama bebas pertama dengan pola `nama (1).ext`, `nama (2).ext`, dan seterusnya."""
	dasar, ekstensi = os.path.splitext(file_name)
	nomor = 1
	while os.path.exists(path_berkas(f"{dasar} ({nomor}){ekstensi}", is_private)):
		nomor += 1
	return f"{dasar} ({nomor}){ekstensi}"


class File(FrappeFile):
	def before_insert(self):
		"""Tandai unggahan sebelum core memanggil save_file.

		Yang dianggap unggahan hanya baris yang membawa isinya sendiri. Baris yang
		dibuat dari `file_url` saja — salinan lampiran waktu amend, atau lampiran yang
		dipilih dari library — juga melewati save_file dengan isi yang dibaca dari
		berkasnya, dan kalau ikut dianggap unggahan, baris aslinya akan terhapus di
		after_insert. Baris seperti itu justru ditandai supaya tetap menunjuk berkas
		asalnya.
		"""
		if not self.is_folder and not self.is_remote_file:
			if self.get("content"):
				self.flags.unggahan_baru = True
			elif self.file_url and self.exists_on_disk():
				self.flags.pakai_berkas_url = True

		super().before_insert()

	def save_file(self, content=None, decode=False, ignore_existing_file_check=False, overwrite=False):
		"""Unggahan selalu menulis berkasnya sendiri, jangan menumpang berkas yang sudah ada.

		Baris dari `file_url` yang berkasnya ada di disk tidak menulis apa pun dan
		tetap menunjuk url itu. Dengan pencarian duplikat dimatikan, core akan
		menyalinnya ke berkas baru berakhiran hash — lampiran hasil amend jadi
		`akta2246c9.pdf`, bukan `akta.pdf`.

		Unggahan yang namanya sudah terpakai di disk ditulis dengan overwrite kalau
		boleh_menimpa, dan diberi nama bernomor kalau tidak. Akhiran hash dari
		`generate_file_name` milik frappe tinggal untuk pemanggil lain.

		Isi lama disimpan dulu dan ditulis balik kalau transaksinya di-rollback —
		core hanya tahu menghapus berkas unggahan yang gagal, yang di sini berarti
		berkas milik baris lama ikut hilang.
		"""
		if self.flags.pop("pakai_berkas_url", False):
			# Yang diisi core sebelum ia memutuskan menulis berkas; isinya sudah dibaca
			# before_insert lewat get_content.
			self.is_private = cint(self.is_private)
			self.content_type = mimetypes.guess_type(self.file_name)[0]
			self.file_size = self.check_max_file_size()
			self.content_hash = get_content_hash(self._content)
			return

		unggahan = self.flags.pop("unggahan_baru", False) and not get_hook_method("write_file")
		path_lama = isi_lama = None

		if unggahan and self.file_name and os.path.isfile(path_berkas(self.file_name, self.is_private)):
			if boleh_menimpa(self.attached_to_doctype, url_berkas(self.file_name, self.is_private)):
				path_lama = path_berkas(self.file_name, self.is_private)
				with open(path_lama, "rb") as f:
					isi_lama = f.read()
			else:
				self.file_name = nama_bernomor(self.file_name, self.is_private)

		hasil = super().save_file(
			content=content,
			decode=decode,
			ignore_existing_file_check=True,
			overwrite=overwrite or isi_lama is not None,
		)

		if isi_lama is not None and self.get("_content"):
			self.flags.berkas_ditimpa = True

			def pulihkan_isi_lama():
				# Didaftarkan sesudah on_rollback milik core, jadi berjalan sesudahnya:
				# berkas yang barusan mungkin dihapus core ditulis kembali.
				with open(path_lama, "wb") as f:
					f.write(isi_lama)
					os.fsync(f.fileno())

			frappe.db.after_rollback.add(pulihkan_isi_lama)

		return hasil

	def after_insert(self):
		super().after_insert()

		if self.flags.pop("berkas_ditimpa", False):
			self.hapus_baris_lain_berkas_yang_sama()

	def hapus_baris_lain_berkas_yang_sama(self):
		"""Baris lama yang berkasnya baru ditimpa dihapus, di dokumen Legal mana pun.

		Lewat delete_doc supaya tetap tercatat di Deleted Document dan dokumen
		asalnya mendapat komentar "Attachment Removed". Berkas di disk aman: baris
		ini sudah tersimpan dengan url yang sama, jadi _delete_file_on_disk di bawah
		hanya membuang thumbnail lama. Lampiran di dokumen yang protect_attached_files
		dan sudah submit tetap ditolak core — seluruh unggahan batal dan isi lama
		dipulihkan oleh rollback di save_file.
		"""
		for nama in frappe.get_all(
			"File",
			filters={"file_url": self.file_url, "name": ["!=", self.name], "is_folder": 0},
			pluck="name",
		):
			frappe.delete_doc("File", nama, ignore_permissions=True)


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
