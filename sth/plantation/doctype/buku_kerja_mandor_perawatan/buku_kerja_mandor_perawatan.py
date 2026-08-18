# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController
from sth.custom.api import (
	USER_API,
	fix_item_from_api,
	fix_kegiatan_from_api,
	fix_mandor_from_api,
	submit_after_insert,
)

# Isi baris hasil kerja yang diambil dari kiriman API waktu digabung. Sisanya —
# amount, premi_amount, sub_total, dan dua Link Employee Payment Log — dihitung
# ulang atau dipasang sistem, jadi tidak pernah ikut disalin.
FIELD_HASIL_KERJA_API = ("employee", "attendance_status", "qty", "hari_kerja", "rate")


def cari_bkm_setrans_no(kiriman):
	"""BKM Perawatan yang sudah ada untuk trans_no kiriman ini, atau None.

	Company dan posting_date ikut dicocokkan: kalau sistem luar sampai memakai
	ulang trans_no untuk data yang berbeda, kirimannya jadi dokumen baru seperti
	dulu — bukan digabung diam-diam ke dokumen yang bukan pasangannya.

	Dokumen batal (docstatus 2) sengaja dilewat. Kiriman sesudahnya harus
	membentuk dokumen baru, bukan menghidupkan yang sudah dibatalkan.
	"""
	if not kiriman.trans_no:
		return None

	return frappe.db.get_value(
		"Buku Kerja Mandor Perawatan",
		{
			"trans_no": kiriman.trans_no,
			"company": kiriman.company,
			"posting_date": getdate(kiriman.posting_date),
			"docstatus": ("<", 2),
		},
		"name",
		order_by="creation",
	)


def cari_bkm_baris_pertama(kiriman):
	"""BKM Perawatan lain yang sudah memuat baris pertama kiriman ini, atau None.

	Kuncinya trans_no + karyawan, sama seperti pemeriksaan duplikat yang sudah
	ada: dua dokumen dengan kunci itu menghitung hari kerja orang yang sama dua
	kali.

	Dokumen batal dilewat, sama seperti cari_bkm_setrans_no: kiriman sesudah
	pembatalan memang harus membentuk dokumen baru.

	Nama dokumen sendiri dikeluarkan dari pencarian. Waktu dipanggil dari
	insert() namanya belum ada, jadi dipakai string kosong — bukan None, yang
	akan membuat seluruh perbandingannya jadi NULL dan tidak pernah cocok.
	"""
	if not kiriman.trans_no or not kiriman.hasil_kerja:
		return None

	baris = kiriman.hasil_kerja[0]

	duplikat = frappe.db.sql("""
		SELECT bkmp.name
		FROM `tabBuku Kerja Mandor Perawatan` bkmp
		INNER JOIN `tabDetail BKM Hasil Kerja Perawatan` hk ON hk.parent = bkmp.name
		WHERE bkmp.trans_no = %(trans_no)s
			AND hk.employee = %(employee)s
			AND bkmp.name != %(name)s
			AND bkmp.docstatus < 2
		ORDER BY bkmp.creation
		LIMIT 1
	""", {
		"trans_no": kiriman.trans_no,
		"employee": baris.employee,
		"name": kiriman.name or "",
	})

	return duplikat[0][0] if duplikat else None


def baris_hasil_kerja_baru(doc, kiriman):
	"""Baris hasil kerja kiriman yang employee-nya belum ada di dokumen.

	Employee yang sudah ada dilewati, bukan ditolak: satu buku kerja dikirim
	sebagai beberapa request terpisah, dan request yang diulang karena jaringan
	harus berakhir tanpa menambah apa-apa — bukan jadi error di sisi pengirim.
	"""
	sudah_ada = {hk.employee for hk in doc.hasil_kerja}

	baris = []
	for hk in kiriman.hasil_kerja:
		if not hk.employee or hk.employee in sudah_ada:
			continue

		sudah_ada.add(hk.employee)
		baris.append({field: hk.get(field) for field in FIELD_HASIL_KERJA_API})

	return baris


def gabung_ke_bkm(nama, kiriman):
	"""Satukan hasil kerja kiriman API ke BKM Perawatan yang sudah ada.

	Tabel `material` kiriman sengaja tidak ikut. Sistem luar mengulang seluruh
	isi header — termasuk material — di tiap request, sedangkan Stock Entry-nya
	sudah dibuat request yang pertama. Menggabungkannya berarti mengeluarkan
	barang yang sama berkali-kali.
	"""
	doc = frappe.get_doc("Buku Kerja Mandor Perawatan", nama)

	baris_baru = baris_hasil_kerja_baru(doc, kiriman)
	if not baris_baru:
		# kiriman ulang: dokumennya sudah memuat semua employee kiriman ini
		return doc

	if doc.docstatus == 0:
		# masih draft, jadi jalur biasa masih terbuka: validate ikut jalan dan
		# on_submit belum pernah jalan sama sekali
		for baris in baris_baru:
			doc.append("hasil_kerja", baris)

		doc.save()
		return doc

	doc.tambah_hasil_kerja_setelah_submit(baris_baru)

	return doc


class BukuKerjaMandorPerawatan(BukuKerjaMandorController):
	# draft ikut dihitung ulang oleh tombol Re-calculate Premi
	# repair_include_draft = True

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.plantation_setting_def.extend([
			["salary_component", "bkm_perawatan_component"],
			["premi_salary_component", "premi_sc"],
		])
		
		self.fieldname_total.extend(["premi_amount"])

		self.kegiatan_fetch_fieldname.extend(["min_basis_premi", "rupiah_premi"])

		self.payment_log_updater.extend([
			{
				"target_amount": "premi_amount",
				"target_salary_component": "premi_salary_component",
                "component_type": "Premi",
				"removed_if_zero": True
			}
		])

		self._mandor_dict = []

	def insert(self, *args, **kwargs):
		"""Kiriman API dengan trans_no yang sudah ada digabung, bukan jadi dokumen baru.

		Sistem luar mengirim satu request per employee dengan trans_no yang sama
		untuk semuanya. Tanpa ini tiap employee jadi satu BKM Perawatan sendiri,
		padahal yang dimaksud satu buku kerja berisi beberapa employee — dan
		validate() tidak menangkapnya karena yang dicek trans_no *dan* employee.

		Kiriman yang karyawannya sudah tercatat tapi dokumennya tidak bisa digabung
		dibalas dengan dokumen yang sudah ada itu, bukan ditolak sebagai duplikat.
		Pengirimnya tidak punya cara membedakan "sudah masuk" dari "gagal": yang
		dilihat cuma request yang error, jadi kirimannya diulang terus tanpa ada
		yang berubah di sini. Membalasnya dengan dokumennya membuat pengulangan itu
		berhenti dengan sendirinya.

		Sengaja dibatasi ke user API. Dari UI dan data import dokumen baru tetap
		dokumen baru; di sana trans_no memang read-only dan tidak pernah terisi.
		"""
		if frappe.session.user != USER_API:
			return super().insert(*args, **kwargs)

		nama = cari_bkm_setrans_no(self)
		if nama:
			return gabung_ke_bkm(nama, self)

		# Trans_no yang sama tapi company atau tanggalnya berbeda tidak digabung —
		# dan memang tidak boleh. Kalau karyawannya ternyata sudah tercatat di
		# dokumen itu, kirimannya pengulangan: dokumennya dikembalikan apa adanya,
		# tidak ada yang ditambahkan dan tidak ada dokumen baru yang lahir.
		duplikat = cari_bkm_baris_pertama(self)
		if duplikat:
			return frappe.get_doc(self.doctype, duplikat)

		return super().insert(*args, **kwargs)

	def before_insert(self):
		fix_mandor_from_api(self)
		fix_kegiatan_from_api(self)
		fix_item_from_api(self)

		# Data dari API kadang masuk dengan docstatus=1 langsung, sehingga
		# proses insert tidak pernah melewati siklus submit (on_submit tidak jalan).
		# Di sini docstatus dipaksa jadi draft dulu, lalu submit() dipanggil manual
		# di after_insert supaya validate/before_submit/on_submit tetap dieksekusi.
		if self.docstatus == 1:
			self.flags.submit_after_insert = True
			self.docstatus = 0

	def after_insert(self):
		if self.flags.get("submit_after_insert"):
			submit_after_insert(self)

	def validate(self):
		# Lewat API duplikatnya sudah ditangani insert() dengan mengembalikan
		# dokumen yang sudah ada, jadi yang sampai ke sini tinggal jalur UI dan
		# data import — di situ tidak ada yang bisa dikembalikan, dan dokumen
		# kembar harus ditahan sebelum hari kerjanya terhitung dua kali.
		duplikat = cari_bkm_baris_pertama(self)
		if duplikat:
			frappe.throw(
				f"Data sudah ada dengan Trans No <b>{self.trans_no}</b>, "
				f"Karyawan <b>{self.hasil_kerja[0].employee}</b>. "
				f"Referensi: {duplikat}"
			)

		self.validate_hasil_kerja_harian()
		super().validate()

	def tambah_hasil_kerja_setelah_submit(self, baris_baru):
		"""Sisipkan baris hasil kerja ke dokumen yang sudah disubmit.

		save() tidak bisa dipakai — `hasil_kerja` bukan allow_on_submit — jadi
		barisnya ditulis lewat db_update_all, cara yang sama dipakai
		update_hasil_kerja_bjr di BKM Panen waktu BJR menyusul setelah submit.

		Karena jalur save() dan submit() dilewati, yang biasanya dikerjakan
		validate dan on_submit dipanggil sendiri di sini — dan hanya sekali,
		untuk baris yang benar-benar baru:

		    Employee Payment Log  cuma untuk baris baru, lewat daftar nama.
		                          Baris lama sudah punya log dan nilainya tidak
		                          berubah — upah dan premi perawatan dihitung
		                          per baris, tidak bergantung baris lain.
		    Premi mandor          dicari dulu baru disimpan, aman diulang.
		                          Untuk Perawatan _mandor_dict memang kosong,
		                          jadi ini no-op — dipanggil supaya tetap sejalan
		                          kalau nanti perannya diisi.
		    Attendance            hanya untuk employee baru. Employee lama sudah
		                          punya Attendance dari kiriman sebelumnya.
		    GL Entry              diperbaiki, bukan ditambah. repair_gl_entry
		                          tidak menyentuh dokumen yang belum berjurnal —
		                          di site ber-workflow jurnalnya menyusul saat
		                          Posted.
		"""
		if self.is_posted():
			frappe.throw(
				_("{0} sudah Posted, hasil kerja baru tidak bisa ditambahkan lagi").format(
					frappe.bold(self.name)
				)
			)

		baris_ditambah = []
		for baris in baris_baru:
			hk = self.append("hasil_kerja", baris)
			# append selalu memberi docstatus draft; barisnya harus seragam dengan
			# induknya supaya cancel dan laporan yang menyaring docstatus melihatnya
			hk.docstatus = self.docstatus
			baris_ditambah.append(hk)

		self.calculate()
		# hasil_kerja_qty sekarang total gabungan, jadi batas luas blok diperiksa
		# ulang terhadap seluruh isi dokumen, bukan cuma baris yang baru masuk
		self.validate_hasil_kerja_harian()

		# baris baru belum punya nama sampai di sini: db_update_all yang
		# menyisipkannya, karena db_update jatuh ke db_insert untuk baris lokal
		self.db_update_all()

		for hk in baris_ditambah:
			# barisnya sudah ada di database, jadi tandanya dilepas — db_update_all
			# berikutnya harus meng-update, bukan menyisipkan baris kembar
			hk.set("__islocal", 0)

		self.create_or_update_payment_log([hk.name for hk in baris_ditambah])
		self.create_or_update_mandor_premi()
		self.make_attendance(baris_ditambah)
		self.check_emp_hari_kerja()

		self.repair_gl_entry()

	def get_cost_center(self):
		"""Cost center dokumen ini: dari batch, blok, atau tahun tanam sesuai kategori.

		Satu tempat untuk dua pemakai — GL Entry dan Stock Entry material — supaya
		biaya upah dan biaya materialnya tidak bisa jatuh ke cost center berbeda.

		Balikan "" kalau sumbernya belum terisi. make_gl_entry memang tidak membuat
		jurnal untuk keadaan itu, dan Stock Entry dibiarkan memakai default company.
		"""
		abbr = frappe.get_cached_value("Company", self.company, "abbr")

		if self.kategori_kegiatan == "BBT":
			return "{} - {}".format(self.batch, abbr) if self.batch else ""

		if self.kategori_kegiatan == "TM":
			deskripsi = frappe.get_cached_value("Blok", self.blok, "deskripsi") if self.blok else None
			return "{} - {}".format(deskripsi, abbr) if deskripsi else ""

		if self.kategori_kegiatan == "TBM":
			return "{} - {}".format(self.tahun_tanam, abbr) if self.tahun_tanam else ""

		return ""

	def validate_hasil_kerja_harian(self):
		if self.get("is_bibitan"):
			return
		
		if self.uom == "HA" and self.hasil_kerja_qty > self.luas_blok:
			frappe.throw("Hasil Kerja exceeds Luas Blok")

	def calculate(self):
		# have_premi diisi lewat fetch_from, yang hanya jalan saat save(). re-calculate
		# memakai db_update_all sehingga nilainya perlu diambil ulang dari master Kegiatan.
		if self.flags.re_calculate and self.kegiatan:
			self.have_premi = frappe.get_cached_value("Kegiatan", self.kegiatan, "have_premi")

		super().calculate()

	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		# saat re-calculate, upah diambil ulang dari master kegiatan supaya perubahan
		# rupiah_basis ikut terpakai. penyimpanan biasa tetap menghormati input manual.
		if self.flags.re_calculate and self.rupiah_basis:
			item.rate = self.rupiah_basis
		else:
			item.rate = item.get("rate") or self.rupiah_basis

		item.premi_amount = 0

		if not self.manual_hk:
			item.hari_kerja = min(flt(item.qty / (self.volume_basis or 1)), 1)
		
		if self.have_premi and item.qty >= self.min_basis_premi:
			item.premi_amount = self.rupiah_premi

	def update_value_after_amount(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		# Hitung total brondolan
		item.sub_total = flt(item.amount + item.premi_amount, precision)
		
	def on_submit(self, update_realization=True):

		super().on_submit(update_realization=False)
		if not self.material:
			pass
			# self.update_rkb_realization()
		else:
			self.create_ste_issue()

		# GL Entry baru dibuat saat dokumen Posted, lihat BukuKerjaMandorController
		self.make_gl_entry_on_submit()

	def create_ste_issue(self):
		ste = frappe.new_doc("Stock Entry")
		ste.company = self.company
		ste.stock_entry_type = "Material Used"
		ste.posting_date = self.posting_date
		ste.set_purpose_for_stock_entry()
		account_kegiatan = ""
		if self.kegiatan_account:
			account_kegiatan = self.kegiatan_account
		else:
			frappe.throw("Account Kegiatan tidak boleh kosong.")

		ada_item = 0

		# Cost center dibawa ke baris Stock Entry, bukan ke headernya: di ERPNext
		# cost_center memang milik Stock Entry Detail dan itu yang dipakai saat
		# menjurnal expense_account.
		cost_center = self.get_cost_center()

		for d in self.material:
			if d.item:
				ada_item = 1

			item = {
				"s_warehouse": d.warehouse,
				"item_code": d.item,
				"qty": d.qty,
				"expense_account": account_kegiatan
			}

			# kalau kosong, biarkan ERPNext memakai default company seperti sebelumnya
			if cost_center:
				item["cost_center"] = cost_center

			ste.append("items", item)
		if ada_item == 1:
			ste.submit()
			self.stock_entry = ste.name
			for index, item in enumerate(ste.items):
				self.material[index].update({
					"stock_entry_detail": item.name,
					"rate": item.basic_rate,
				})

			self.set_material_rate(get_valuation_rate=False)

	def set_material_rate(self, get_valuation_rate=True):
		if get_valuation_rate:
			for d in self.material:
				d.rate = frappe.get_value("Stock Entry Detail", d.stock_entry_detail, "basic_rate")
				
		self.calculate_item_table_values()
		self.calculate_grand_total()

		self.db_update_all()

		# self.update_rkb_realization()

	def on_cancel(self):
		self.delete_ste()

		super().on_cancel()
		self.make_reverse_gl_entry()

	def delete_ste(self):
		if not self.stock_entry:
			return
			
		ste = frappe.get_doc("Stock Entry", self.stock_entry)
		if ste.docstatus == 1:
			ste.cancel()

		self.db_set("stock_entry", "")

		ste.delete()

	def get_nilai_gl_entry(self):
		"""Nilai jurnal BKM: upah dan preminya saja, tanpa material.

		Bukan grand_total. Material sudah dijurnal Stock Entry "Material Used" ke
		akun kegiatan yang sama, sedangkan calculate_grand_total menjumlahkan semua
		field ber-"amount" termasuk material_amount — memakai grand_total membuat
		akun kegiatan terdebit dua kali sebesar nilai materialnya.
		"""
		return flt(self.hasil_kerja_amount) + flt(self.hasil_kerja_premi_amount)

	def make_gl_entry(self, method=None):
		gl_entries = []
		akun_debit = self.kegiatan_account
		akun_kredit = ""

		single_doc = frappe.get_single("Plantation Settings")
		for row in single_doc.plantation_settings_akun_kredit_bkm:
			if row.company == self.company:
				akun_kredit = row.account

		if not akun_kredit:
			frappe.throw(
				_("Account Kredit BKM untuk company <b>{0}</b> tidak ditemukan. "
				  "Pastikan akun tersebut sudah dipasang di Plantation Settings").format(self.company)
			)

		cost_center = self.get_cost_center()
		nilai = self.get_nilai_gl_entry()

		if nilai and cost_center:

			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_debit,
					"debit": nilai,
					"credit": 0.0,
					"debit_in_account_currency": nilai,
					"credit_in_account_currency": 0.0,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Perawatan - {self.name}",
					"cost_center": cost_center
				})
			)

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_kredit,
					"debit": 0.0,
					"credit": nilai,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": nilai,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Perawatan - {self.name}",
					"cost_center": cost_center
				})
			)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		self.show_gl_alert(_("GL Entry berhasil dibuat."))

	def make_reverse_gl_entry(self, method=None):
		"""
		Buat GL Entry pembalik (reverse) dengan membalik debit/credit dari entry asli.
		"""
		original_entries = frappe.get_all(
			"GL Entry",
			filters={
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"is_cancelled": 0
			},
			fields=[
				"account", "debit", "credit",
				"debit_in_account_currency", "credit_in_account_currency",
				"cost_center", "remarks", "company"
			]
		)

		if not original_entries:
			return

		for entry in original_entries:
			reverse_gl = frappe.get_doc({
				"doctype": "GL Entry",
				"posting_date": self.posting_date,
				"account": entry.account,
				"debit": entry.credit,
				"credit": entry.debit,
				"debit_in_account_currency": entry.credit_in_account_currency,
				"credit_in_account_currency": entry.debit_in_account_currency,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"company": entry.company,
				"remarks": f"Reverse: {entry.remarks}",
				"cost_center": entry.cost_center,
			})
			reverse_gl.flags.ignore_permissions = True
			reverse_gl.insert()

		frappe.db.sql(
			"""
			UPDATE `tabGL Entry`
			SET is_cancelled = 1
			WHERE voucher_type = %s
			  AND voucher_no   = %s
			  AND is_cancelled = 0
			""",
			(self.doctype, self.name),
		)

		frappe.msgprint(_("GL Entry berhasil di-reverse."), indicator="orange", alert=True)