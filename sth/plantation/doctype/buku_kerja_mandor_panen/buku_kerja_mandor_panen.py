# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt, format_date, get_link_to_form, getdate
from frappe.query_builder.functions import Coalesce, Sum

from sth.controllers.buku_kerja_mandor import BukuKerjaMandorController
from sth.custom.api import (
	USER_API,
	fix_kegiatan_from_api,
	fix_mandor_from_api,
	submit_after_insert,
)
from frappe import _

# Isi baris hasil kerja yang diambil dari kiriman API waktu digabung. qty, bjr,
# status, denda, dan seluruh turunan amount sengaja tidak ikut: semuanya dihitung
# ulang oleh calculate(), dan bjr sendiri baru datang dari timbangan.
FIELD_HASIL_KERJA_API = (
	"employee", "blok", "tph", "attendance_status",
	"jumlah_janjang", "qty_brondolan", "hari_kerja", "rate",
	"buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal",
	"brondolan_tinggal", "pelepah_tidak_disusun", "tangkai_panjang",
	"buah_tidak_disusun", "pelepah_sengkleh",
	"jumlah_janjang_sesuai_kriteria", "jumlah_janjang_tidak_sesuai_kriteria",
	"jumlah_output", "satuan", "jumlah_hektar",
)


# Kolom peran yang preminya dihitung dari isi BKM. Buku Kerja Mandor Premi
# menjumlahkan qty seluruh baris BKM sebulan yang kolom perannya menunjuk orang
# itu, jadi dokumen dengan pemegang peran berbeda tidak boleh disatukan.
FIELD_PEMEGANG_PREMI = ("kode_mandor", "mandor1", "kerani_panen")


def kunci_baris(hk):
	"""Penanda satu baris hasil kerja panen.

	Beda dari Perawatan yang cukup memakai employee: satu pemanen bisa mengisi
	beberapa baris dalam sehari untuk blok — dan TPH — yang berbeda. Kalau TPH
	tidak ikut jadi kunci, baris TPH kedua terbuang diam-diam dan janjangnya
	hilang dari BKM padahal buahnya tetap berangkat lewat SPB. Di data yang TPH-nya
	memang tidak pernah terisi, kunci ini dengan sendirinya jatuh ke employee + blok.
	"""
	return (hk.employee, hk.blok, hk.tph or "")


def cari_bkm_setrans_no(kiriman):
	"""BKM Panen yang sudah ada untuk trans_no kiriman ini, atau None.

	Company dan posting_date ikut dicocokkan seperti di Perawatan. is_kontanan
	ditambahkan karena bedanya bukan soal isi: kontanan dan non-kontanan punya
	jalur payroll sendiri-sendiri, jadi keduanya harus tetap dokumen terpisah
	sekalipun trans_no-nya kebetulan sama.

	Begitu juga ketiga pemegang premi. Di produksi ada trans_no yang dipakai dua
	kerani sekaligus — pembagiannya 11 lawan 4 dokumen, bukan satu yang nyasar.
	Premi mereka dihitung dari jumlah qty seluruh baris BKM sebulan yang kolom
	perannya menunjuk mereka, jadi menggabung dua kerani ke satu dokumen
	memindahkan premi dari satu orang ke orang lain tanpa ada yang memutuskan.

	Dokumen batal (docstatus 2) sengaja dilewat. Kiriman sesudahnya harus
	membentuk dokumen baru, bukan menghidupkan yang sudah dibatalkan.
	"""
	if not kiriman.trans_no:
		return None

	filters = {
		"trans_no": kiriman.trans_no,
		"company": kiriman.company,
		"posting_date": getdate(kiriman.posting_date),
		"is_kontanan": cint(kiriman.is_kontanan),
		"docstatus": ("<", 2),
	}

	for field in FIELD_PEMEGANG_PREMI:
		filters[field] = kiriman.get(field) or ""

	return frappe.db.get_value(
		"Buku Kerja Mandor Panen",
		filters,
		"name",
		order_by="creation",
	)


def kunci_baris_terpakai(kiriman):
	"""Kunci baris yang sudah ada di seluruh BKM ber-trans_no sama.

	Bukan cuma dokumen yang akan digabung. Data yang masuk sebelum penggabungan
	ini ada sudah telanjur terpecah jadi banyak BKM, dan kiriman susulan untuk
	trans_no lama tetap datang. Tanpa menyisir dokumen saudaranya, baris yang
	sudah tercatat di sana akan masuk lagi ke dokumen paling awal dan janjangnya
	terhitung dua kali di Recap Panen by Blok.
	"""
	rows = frappe.db.sql(
		"""
		SELECT hk.employee, hk.blok, hk.tph
		FROM `tabDetail BKM Hasil Kerja Panen` hk
		INNER JOIN `tabBuku Kerja Mandor Panen` b ON b.name = hk.parent
		WHERE b.trans_no = %(trans_no)s
			AND b.company = %(company)s
			AND b.posting_date = %(posting_date)s
			AND b.is_kontanan = %(is_kontanan)s
			AND b.docstatus < 2
		""",
		{
			"trans_no": kiriman.trans_no,
			"company": kiriman.company,
			"posting_date": getdate(kiriman.posting_date),
			"is_kontanan": cint(kiriman.is_kontanan),
		},
		as_dict=True,
	)

	return {(r.employee, r.blok, r.tph or "") for r in rows}


def baris_hasil_kerja_baru(doc, kiriman):
	"""Baris hasil kerja kiriman yang kuncinya belum ada di mana pun.

	Baris yang sudah ada dilewati, bukan ditolak: satu buku kerja dikirim sebagai
	beberapa request terpisah, dan request yang diulang karena jaringan harus
	berakhir tanpa menambah apa-apa — bukan jadi error di sisi pengirim.
	"""
	sudah_ada = {kunci_baris(hk) for hk in doc.hasil_kerja} | kunci_baris_terpakai(kiriman)

	baris = []
	for hk in kiriman.hasil_kerja:
		if not hk.employee:
			continue

		kunci = kunci_baris(hk)
		if kunci in sudah_ada:
			continue

		sudah_ada.add(kunci)
		baris.append({field: hk.get(field) for field in FIELD_HASIL_KERJA_API})

	return baris


def gabung_ke_bkm(nama, kiriman):
	"""Satukan hasil kerja kiriman API ke BKM Panen yang sudah ada.

	Balikan None berarti kirimannya harus jadi dokumen baru.
	"""
	doc = frappe.get_doc("Buku Kerja Mandor Panen", nama)

	baris_baru = baris_hasil_kerja_baru(doc, kiriman)
	if not baris_baru:
		# kiriman ulang: dokumennya sudah memuat semua baris kiriman ini
		return doc

	if doc.is_posted():
		# BKM susulan nyata adanya — di produksi ada yang baru datang berhari-hari
		# sesudah dokumen pertama, kadang sesudah dokumen itu dijurnal. Menolaknya
		# berarti janjangnya tidak pernah masuk sama sekali, dan Recap Panen by
		# Blok tetap kurang. Biarkan berdiri sebagai dokumen sendiri seperti
		# perilaku lama: barisnya sudah dipastikan bukan pengulangan.
		return None

	if doc.docstatus == 0:
		# masih draft, jadi jalur biasa masih terbuka: validate ikut jalan dan
		# on_submit belum pernah jalan sama sekali
		for baris in baris_baru:
			doc.append("hasil_kerja", baris)

		doc.save()
		return doc

	doc.tambah_hasil_kerja_setelah_submit(baris_baru)

	return doc


class BukuKerjaMandorPanen(BukuKerjaMandorController):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.plantation_setting_def.extend([
			["salary_component", "bkm_panen_component"],
			["denda_salary_component", "denda_sc"],
			["brondolan_salary_component", "brondolan_sc"],
			["kontanan_salary_component", "premi_kontanan_component"],
		])

		self.fieldname_total.extend([
			"jumlah_janjang", "qty_brondolan", "brondolan_amount", "denda", "kontanan_amount"
		])

		self.kegiatan_fetch_fieldname.extend(["upah_brondolan", "premi_kontanan_basis"])

		self.payment_log_updater.extend([
			{
				"target_amount": "kontanan_amount",
				"target_salary_component": "kontanan_salary_component",
				"component_type": "Kontanan",
				"removed_if_zero": True
			},
			{
				"target_amount": "denda",
				"target_salary_component": "denda_salary_component",
				"component_type": "Denda",
				"removed_if_zero": True
			},
			{
				"target_amount": "brondolan_amount",
				"target_salary_component": "brondolan_salary_component",
				"component_type": "Brondolan",
				"removed_if_zero": True
			}
		])

		self._clear_fields = ["blok"]
		self._mandor_dict.extend([
			{"fieldname": "mandor1"},
			{"fieldname": "kerani_panen"},
		])
		self._bkm_name = "Panen"

	def insert(self, *args, **kwargs):
		"""Kiriman API dengan trans_no yang sudah ada digabung, bukan jadi dokumen baru.

		Sistem luar mengirim satu request per pemanen dengan trans_no yang sama
		untuk semuanya — di produksi satu trans_no sampai memecah jadi 15 dokumen.
		validate() tidak menangkapnya karena yang dicek trans_no *dan* employee
		*dan* blok, sedangkan tiap request memang membawa pemanen yang berbeda.

		Akibatnya bukan cuma dokumen berserakan. Kiriman susulan untuk trans_no
		lama tetap datang berhari-hari sesudahnya, dan tiap kali jadi dokumen baru
		lagi — kalau isinya mengulang baris yang sudah tercatat, janjangnya masuk
		dua kali ke Recap Panen by Blok lewat voucher yang berbeda.

		Sengaja dibatasi ke user API. Dari UI dan data import dokumen baru tetap
		dokumen baru; di sana trans_no memang read-only dan tidak pernah terisi.
		"""
		if frappe.session.user != USER_API:
			return super().insert(*args, **kwargs)

		nama = cari_bkm_setrans_no(self)
		if not nama:
			return super().insert(*args, **kwargs)

		digabung = gabung_ke_bkm(nama, self)
		if digabung is None:
			return super().insert(*args, **kwargs)

		return digabung

	def before_insert(self):
		fix_mandor_from_api(self)
		fix_kegiatan_from_api(self)

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
		self.isi_cost_center()
		if self.trans_no:
			trans_no = self.trans_no
			karyawan = self.hasil_kerja[0].employee
			blok = self.hasil_kerja[0].blok

			duplikat = frappe.db.sql("""
				SELECT bkmp.name
				FROM `tabBuku Kerja Mandor Panen` bkmp
				INNER JOIN `tabDetail BKM Hasil Kerja Panen` hk ON hk.parent = bkmp.name
				WHERE bkmp.trans_no = %s
					AND hk.employee = %s
					AND hk.blok = %s
					AND bkmp.name != %s
				LIMIT 1
			""", (trans_no, karyawan, blok, self.name))

			if duplikat:
				frappe.throw(
					f"Data sudah ada dengan Trans No <b>{trans_no}</b>, "
					f"Karyawan <b>{karyawan}</b>, dan Blok <b>{blok}</b>. "
					f"Referensi: {duplikat[0][0]}"
				)


		self.reset_automated_data()
		
		super().validate()
	
	def isi_cost_center(self):
		# Cost Center Blok dinamai persis seperti nama Blok, dan isi field blok
		# di baris hasil kerja memang nama itu — tidak perlu dibaca ulang.
		self.cost_center = "{} - {}".format(self.hasil_kerja[0].blok, frappe.get_doc("Company",self.company).abbr)

	def reset_automated_data(self):
		self.transfered_janjang = self.transfered_brondolan = \
		self.netto_weight = self.weight_total = self.bjr = 0

	def set_payroll_date(self):
		if not self.is_kontanan:
			super().set_payroll_date()
		else:
			self.payroll_date, self.against_salary_component = frappe.db.get_value("Pengajuan Panen Kontanan", {
				"bkm_panen": self.name, "docstatus": 1
			}, ["posting_date", "against_kontanan_component"]) or ["", ""]

	def on_submit(self):
		super().on_submit()
		self.create_or_update_recap_panen_by_blok()
		# GL Entry dibuat saat dokumen Posted / saat BJR masuk, lihat update_hasil_kerja_bjr

	def on_cancel(self):
		super().on_cancel()
		self.cancel_gl_entries()
		self.remove_bkm_from_recap_panen()

	def on_trash(self):
		super().on_trash()
		self.remove_bkm_from_recap_panen()

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

		if self.grand_total:

			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_debit,
					"debit": self.grand_total,
					"credit": 0.0,
					"debit_in_account_currency": self.grand_total,
					"credit_in_account_currency": 0.0,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Panen - {self.name}",
					"cost_center": self.cost_center
				})
			)

			# --- CREDIT ---
			gl_entries.append(
				frappe.get_doc({
					"doctype": "GL Entry",
					"posting_date": self.posting_date,
					"account": akun_kredit,
					"debit": 0.0,
					"credit": self.grand_total,
					"debit_in_account_currency": 0.0,
					"credit_in_account_currency": self.grand_total,
					"voucher_type": self.doctype,
					"voucher_no": self.name,
					"company": self.company,
					"remarks": f"BKM Panen - {self.name}",
					"cost_center": self.cost_center
				})
			)

		# Simpan semua GL Entry
		for gl in gl_entries:
			gl.flags.ignore_permissions = True
			gl.insert()

		self.show_gl_alert(_("GL Entry berhasil dibuat."))

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
		frappe.msgprint(_("GL Entry berhasil dibatalkan."), indicator="orange", alert=True)

	def create_or_update_recap_panen_by_blok(self):
		blok_dict = {}
		for hk in self.hasil_kerja:
			blok = blok_dict.setdefault(hk.blok, {
				"voucher_type": self.doctype, 
				"voucher_no": self.name,
				"jumlah_janjang": 0,
				"jumlah_brondolan": 0,
			})
			
			blok["jumlah_janjang"] += hk.jumlah_janjang
			blok["jumlah_brondolan"] += hk.qty_brondolan

		# buang rekap blok yang sudah tidak dipakai lagi oleh BKM ini
		# (blok/tanggal/company diubah tanpa cancel)
		self.remove_bkm_from_recap_panen(keep_blok=blok_dict.keys())

		message = ""
		for b, value in blok_dict.items():
			rekap_panen = "create_rekap_panen"
			try:
				frappe.db.savepoint(rekap_panen)
				rpb = frappe.new_doc("Recap Panen by Blok")
				rpb.update({
					"company": self.company,
					"posting_date": self.posting_date,
					"blok": b,
					"kontanan": self.is_kontanan,
				})

				rpb.append("voucher_recap", value)
				rpb.save()
			except frappe.UniqueValidationError:
				if frappe.message_log:
					frappe.message_log.pop()

				frappe.db.rollback(save_point=rekap_panen)  # preserve transaction in postgres
				rpb = frappe.get_last_doc("Recap Panen by Blok", {"company": self.company, "posting_date": self.posting_date, "blok": b})
				for vc in rpb.voucher_recap:
					if vc.voucher_type == self.doctype and vc.voucher_no == self.name:
						vc.update(value)
						break
				else:
					rpb.append("voucher_recap", value)

				rpb.save()
				# message += f"<br>{b}"

		# if message:
		# 	frappe.throw(f"List Blok already used in {format_date(self.posting_date)}: {message}")

	def tambah_hasil_kerja_setelah_submit(self, baris_baru):
		"""Sisipkan baris hasil kerja ke dokumen yang sudah disubmit.

		save() tidak bisa dipakai — `hasil_kerja` bukan allow_on_submit — jadi
		barisnya ditulis lewat db_update_all, cara yang sama dipakai
		update_hasil_kerja_bjr waktu BJR menyusul setelah submit.

		Karena jalur save() dan submit() dilewati, yang biasanya dikerjakan
		validate dan on_submit dipanggil sendiri di sini, dan hanya sekali untuk
		baris yang benar-benar baru. Dua hal yang tidak ada di Perawatan:

		    Recap Panen by Blok   dihitung ulang, bukan ditambah. Sejak
		                          create_or_update_recap_panen_by_blok idempoten,
		                          baris voucher yang sudah ada di-update dan blok
		                          yang tidak lagi terpakai ikut dilepas.
		    BJR                   kalau timbangannya sudah masuk duluan, baris
		                          baru lahir dengan bjr 0 sehingga upahnya 0.
		                          Nilainya dipasang ulang dari recap.
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

		self.create_or_update_recap_panen_by_blok()

		bjr_blok = self.get_bjr_dari_recap({hk.blok for hk in baris_ditambah if hk.blok})
		if bjr_blok:
			# ikut membereskan payment log upah dan GL Entry untuk baris baru
			self.update_hasil_kerja_bjr(bjr_blok)
		else:
			self.repair_gl_entry()

	def get_bjr_dari_recap(self, blok_list):
		"""BJR yang sudah dihitung Recap Panen by Blok untuk blok tertentu.

		Blok yang recap-nya belum ditimbang dibiarkan di luar hasil: bjr 0 di sana
		bukan nilai, cuma tanda belum ada timbangan, dan menuliskannya cuma akan
		menyalakan hitung ulang upah tanpa mengubah apa-apa.
		"""
		bjr = {}
		for blok in blok_list:
			nilai = frappe.db.get_value("Recap Panen by Blok", {
				"blok": blok,
				"company": self.company,
				"posting_date": self.posting_date,
			}, "bjr")

			if flt(nilai):
				bjr[blok] = flt(nilai)

		return bjr

	def remove_bkm_from_recap_panen(self, keep_blok=None):
		"""Lepas BKM ini dari Recap Panen by Blok.

		keep_blok: daftar blok yang masih dipakai BKM ini. Rekap dengan blok
		tersebut (dan company/tanggal yang sama) dilewati, sisanya dibersihkan.
		"""
		keep = set()
		if keep_blok:
			keep = {(b, self.company, getdate(self.posting_date)) for b in keep_blok}

		for epl in set(frappe.get_all(
			"Rekap Panen Voucher",
			filters={"voucher_type": self.doctype, "voucher_no": self.name},
			pluck="parent"
		)):
			rpb = frappe.get_doc("Recap Panen by Blok", epl)
			if (rpb.blok, rpb.company, getdate(rpb.posting_date)) in keep:
				continue

			# hapus semua baris BKM ini, termasuk sisa duplikat lama
			for vc in list(rpb.voucher_recap):
				if vc.voucher_type == self.doctype and vc.voucher_no == self.name:
					rpb.remove(vc)

			# rekap tanpa voucher tersisa tidak perlu disimpan sebagai baris kosong
			if not rpb.voucher_recap and not flt(rpb.transfered_janjang):
				rpb.flags.transaction_panen = True
				rpb.delete()
				continue

			rpb.save()
		
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield != "hasil_kerja":
			return
		
		item.qty = flt((item.bjr or 0) * item.jumlah_janjang)
		item.rate = item.get("rate") or self.rupiah_basis
		item.brondolan = flt(self.upah_brondolan)
		item.status = "Pending" if not item.bjr else "Approved"

		if not self.manual_hk:
			item.hari_kerja = min(flt(item.qty / self.volume_basis), 1)

	def update_value_after_amount(self, item, precision):
		# Hitung total brondolan
		item.brondolan_amount = flt(item.brondolan * flt(item.qty_brondolan), precision)
		item.kontanan_amount = flt(item.qty * flt(self.premi_kontanan_basis), precision) if self.is_kontanan else 0

		# Perhitungan denda
		factors = [ 
			"buah_tidak_dipanen", "buah_mentah_disimpan", "buah_mentah_ditinggal",
			"brondolan_tinggal", "pelepah_tidak_disusun","tangkai_panjang",
			"buah_tidak_disusun", "pelepah_sengkleh"
		]

		# Hitung total denda dengan menjumlahkan rate * nilai item
		item.denda = sum(flt(item.get(field)) * flt(self.get(f"{field}_rate")) for field in factors)

		item.sub_total = flt(item.amount + item.brondolan_amount + item.kontanan_amount, precision)

	def after_calculate_grand_total(self):
		self.grand_total -= self.hasil_kerja_denda 

	def update_kontanan_used(self, cancel=0):
		self.set_payroll_date()
		self.is_rekap = not cancel
		self.db_update()
		
		self.create_or_update_payment_log()

	def update_hasil_kerja_bjr(self, block_dict=None):
		# update bjr untuk menentukan nilai upah pegawai
		update_payment_log = []
		for hk in self.hasil_kerja:
			if block_dict and not block_dict.get(hk.blok):
				continue
			
			hk.bjr = block_dict[hk.blok]
			update_payment_log.append(hk.name)

		self.calculate()
		self.db_update_all()
		
		if self.is_kontanan and self.is_rekap:
			frappe.throw(f"Document already have Pengajuan Kontanan. please cancel it first")

		self.create_or_update_payment_log(update_payment_log, "Upah")
		self.create_or_update_mandor_premi()

		# BJR bisa datang sebelum atau sesudah dokumen Posted. kalau GL Entry sudah ada
		# nilainya diperbaiki, kalau belum Posted GL Entry-nya menyusul saat posting.
		if self.has_gl_entry():
			self.repair_gl_entry()
		else:
			self.make_gl_entry_on_submit()

