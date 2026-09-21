# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import contextlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, now
from frappe.model.mapper import get_mapped_doc

from sth.mill.utils import buat_ulang_ste, izinkan_stock_minus

DOCTYPE = "Data TBS"

class DataTBS(Document):
	def validate(self):
		self.validate_duplikat()
		self.jumlah_tbs_restan = get_restan_awal(self.unit, self.tanggal_produksi, self.name, self.creation)
		self.calculate_totals()

	def validate_duplikat(self):
		"""Satu unit cuma boleh punya satu Data TBS per tanggal proses.

		Restan awal dirantai dari dokumen sebelumnya, jadi dua dokumen di hari
		yang sama membuat TBS diterima hari itu terhitung dua kali di restan.
		Dokumen yang dibatalkan tidak ikut dihitung, supaya amend tetap bisa.
		"""
		if not (self.unit and self.tanggal_produksi):
			return

		kembar = frappe.db.get_value("Data TBS", {
			"name": ("!=", self.name),
			"unit": self.unit,
			"tanggal_produksi": self.tanggal_produksi,
			"docstatus": ("<", 2),
		})

		if kembar:
			frappe.throw(
				"Data TBS {0} sudah memakai tanggal proses {1} untuk unit {2}.".format(
					frappe.bold(kembar), frappe.bold(self.tanggal_produksi), frappe.bold(self.unit)
				)
			)

	def on_submit(self):
		self.create_ste()
		self.hitung_ulang_dokumen_sesudahnya()
	
	def on_cancel(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.cancel()

		self.hitung_ulang_dokumen_sesudahnya()

	def hitung_ulang_dokumen_sesudahnya(self):
		"""Data TBS sesudah dokumen ini ikut dihitung ulang.

		Restan awal sebuah dokumen adalah Total TBS Restan dokumen sebelumnya,
		jadi begitu dokumen ini disubmit atau dibatalkan seluruh hari sesudahnya
		di unit yang sama ikut bergeser. Selama ini tidak ada yang mengerjakannya:
		pemicu yang ada cuma Timbangan dan tombol Hitung Ulang, sehingga Data TBS
		bertanggal mundur, amend, maupun pembatalan meninggalkan hari-hari
		sesudahnya memakai restan awal yang sudah basi — dan angkanya baru
		ketahuan berhari-hari kemudian waktu dicari.

		Dikerjakan langsung, bukan di latar belakang seperti pemicu Timbangan:
		orang yang menekan submit memang sedang menunggu angkanya, dan rantainya
		biasanya pendek. Larangan stok minus tidak dimatikan dan tidak ada commit
		di tengah — keduanya akan merusak transaksi submit yang sedang berjalan.
		Sejajar dengan hitung_ulang_dokumen_sesudahnya di kedua doctype sounding.
		"""
		if not (self.unit and self.tanggal_produksi):
			return

		hitung_ulang_rantai(
			self.unit,
			add_days(self.tanggal_produksi, 1),
			izinkan_minus=False,
			commit=False,
		)
	
	def on_trash(self):
		ste = frappe.db.get_all("Stock Entry",{"references": self.name})
		for row in ste:
			doc = frappe.get_doc("Stock Entry",row)
			doc.delete()

	@frappe.whitelist()
	def get_data(self):
		# Cuma selagi draft. Angka yang diisi method ini — TBS diterima, restan,
		# dan seluruh turunannya — menentukan qty Stock Entry yang dibuat waktu
		# submit, dan Stock Entry itu tidak ikut berubah kalau angkanya dihitung
		# ulang belakangan. Tombolnya sendiri sudah disembunyikan lewat
		# depends_on di doctype-nya; ini penjaga untuk jalur lain, karena
		# methodnya whitelisted dan bisa dipanggil dari API.
		if self.docstatus != 0:
			frappe.throw(
				"Get Data hanya bisa dipakai selagi {0} masih draft.".format(frappe.bold(self.name))
			)

		data_lori = frappe.db.sql("""
			select 
				tbs_olah as jumlah_lori_olah,
				tbs_mentah as jumlah_lori_mentah,
				jumlah_restan_tbs_masak as jumlah_lori_masak,
				jumlah_loading_ramp as lori_estimasi_loading_ramp
			from `tabMonitoring TBS Olah` mto
			where mto.docstatus = 1 and tgl = %s and pabrik = %s
		""",(self.tanggal_produksi,self.pabrik),as_dict=True)

		# Tanpa Monitoring TBS Olah lorinya dinolkan, bukan dibiarkan memakai
		# angka Get Data sebelumnya yang tanggalnya sudah lain.
		self.update(data_lori[0] if data_lori else {
			"jumlah_lori_olah": 0,
			"jumlah_lori_mentah": 0,
			"jumlah_lori_masak": 0,
			"lori_estimasi_loading_ramp": 0,
		})

		self.jumlah_tbs_restan = get_restan_awal(self.unit, self.tanggal_produksi, self.name, self.creation)
		self.jumlah_tbs_diterima = get_total_tbs(self.tanggal_produksi,self.unit)
		self.total_jam_olah = frappe.db.get_value("CBC Monitoring",{"docstatus": 1, "posting_date": self.tanggal_produksi},"total_hour_meter") or 0

		self.calculate_totals()

	@frappe.whitelist()
	def hitung_ulang(self):
		"""Hitung ulang dokumen ini dan hari-hari sesudahnya di unit yang sama.

		Dipakai sesudah Timbangan bertanggal mundur masuk atau dibatalkan:
		Jumlah TBS Diterima cuma ditulis waktu Get Data ditekan, jadi dokumen
		yang sudah disubmit tidak akan pernah menyusul sendiri.
		"""
		# Yang dikerjakan method ini membatalkan dan membuat ulang Stock Entry,
		# jadi izin write atas Data TBS saja tidak cukup.
		self.check_permission("submit")

		hasil = hitung_ulang_rantai(self.unit, self.tanggal_produksi)
		self.reload()

		return hasil

	def calculate_totals(self):
		"""Bagi TBS hari ini ke olah, restan, dan loading ramp menurut porsi lorinya."""
		self.grand_total_lori = (
			cint(self.jumlah_lori_olah)
			+ cint(self.jumlah_lori_mentah)
			+ cint(self.jumlah_lori_masak)
			+ cint(self.lori_estimasi_loading_ramp)
		)
		self.grand_total_tbs = flt(self.jumlah_tbs_restan) + flt(self.jumlah_tbs_diterima)

		if self.grand_total_lori:
			self.berat_rata_rata_tbs = self.grand_total_tbs / self.grand_total_lori
			self.tbs_olah = self.berat_rata_rata_tbs * cint(self.jumlah_lori_olah)
			self.tbs_restan = self.berat_rata_rata_tbs * (cint(self.jumlah_lori_mentah) + cint(self.jumlah_lori_masak))
			self.tbs_loading_ramp = self.berat_rata_rata_tbs * cint(self.lori_estimasi_loading_ramp)
		else:
			# Tidak ada lori berarti tidak ada yang diolah, jadi seluruh TBS —
			# restan awal maupun yang diterima hari itu — jadi restan hari
			# berikutnya. Membiarkan berat rata-rata nol memakainya sebagai
			# pengali bikin restannya ikut nol dan TBS-nya hilang dari rantai.
			self.berat_rata_rata_tbs = 0
			self.tbs_olah = 0
			self.tbs_restan = self.grand_total_tbs
			self.tbs_loading_ramp = 0

		self.total_tbs_restan = flt(self.tbs_restan) + flt(self.tbs_loading_ramp)
		self.kapasitas_pabrik = self.tbs_olah / self.total_jam_olah / 1000 if self.total_jam_olah else 0

	def create_ste(self):
		# Pergerakan stok TBS hari itu: yang diterima dikurangi yang diolah.
		# Sengaja tidak dibulatkan ke presisi field — total_tbs_restan presisinya
		# 0 supaya tampil bulat di form, dan memakainya di sini bikin stok
		# meleset sampai setengah kilo tiap hari. Pembulatannya diserahkan ke
		# presisi qty Stock Entry.
		selisih = flt(self.total_tbs_restan) - flt(self.jumlah_tbs_restan)

		if not flt(selisih, 3):
			return

		def postprocess(source,target):
			target.set_posting_time = 1
			target.posting_date = self.tanggal_produksi
			target.posting_time = "23:59:59"
			target.stock_entry_type = "Material Receipt" if selisih > 0 else "Material Issue"
			
			update_fields = (
				"item_name",
				"stock_uom",
				"description",
				"expense_account",
				"cost_center",
				"conversion_factor",
				"barcode",
				"uom"
			)

			item = target.append("items")
			item.item_code = frappe.db.get_value("Item",{"tipe_barang": "TBS"})
			item.qty = abs(selisih)
			gudang = get_warehouse_tbs(self.unit)
			if selisih > 0:
				item.t_warehouse = gudang
			else:
				item.s_warehouse = gudang

			item_details = target.get_item_details(
				frappe._dict(
					{
						"item_code": item.item_code,
						"company": target.company,
						"project": target.project,
					}
				),
				for_update=True,
			)

			for field in update_fields:
				if not item.get(field):
					item.set(field, item_details.get(field))
				if field == "conversion_factor" and item.uom == item_details.get("stock_uom"):
					item.set(field, item_details.get(field))
			
			
			target.run_method("set_missing_values")
			

		mapper = {
			"Data TBS": {
				"doctype": "Stock Entry",
				"field_map": {
					"name":"references",
					"doctype": "reference_doctype",
				}
			},
		}

		doc = get_mapped_doc(self.doctype,self.name,mapper,None,postprocess,True)
		doc.insert()
		doc.submit()

def get_total_tbs(tanggal,unit):
	query = frappe.db.sql("""
		SELECT sum(netto) as qty
		FROM `tabTimbangan` t
		WHERE receive_type IN ('TBS Internal', 'TBS Eksternal') AND docstatus = 1 AND posting_date = %s AND unit = %s
	""",(tanggal,unit),as_dict=True)

	return query[0].qty if query else 0

def get_restan_awal(unit, tanggal_produksi, name=None, creation=None):
	"""Restan awal hari ini adalah Total TBS Restan dokumen sebelumnya.

	Diambil dari dokumennya, bukan dari saldo Bin, supaya angkanya tidak
	tergantung kapan dokumen kemarin disubmit. Bin baru bergerak waktu Data TBS
	disubmit, jadi selama dokumen kemarin masih draft saldo Bin masih saldo
	beberapa hari lalu — itu yang bikin serangkaian dokumen memakai restan awal
	yang sama waktu disubmit borongan.

	Draft ikut dihitung dengan alasan yang sama: dokumen hari ini biasanya
	disiapkan sebelum dokumen kemarin disubmit. Yang dibatalkan dilewati, jadi
	sesudah amend yang terbaca dokumen penggantinya.
	"""
	if not (unit and tanggal_produksi):
		return 0

	sebelumnya = frappe.db.sql("""
		select total_tbs_restan
		from `tabData TBS`
		where unit = %(unit)s and docstatus < 2 and name != %(name)s
			and (tanggal_produksi < %(tanggal_produksi)s
				or (tanggal_produksi = %(tanggal_produksi)s and creation < %(creation)s))
		order by tanggal_produksi desc, creation desc
		limit 1
	""", {
		"unit": unit,
		"name": name or "",
		"tanggal_produksi": tanggal_produksi,
		"creation": creation or now(),
	})

	return flt(sebelumnya[0][0]) if sebelumnya else 0

def get_warehouse_tbs(unit):
	return frappe.db.get_value("Warehouse",{"unit":unit,"warehouse_category": "TBS"})

def hitung_ulang_setelah_timbangan(doc, method=None):
	"""Antrikan hitung ulang Data TBS sesudah Timbangan TBS disubmit atau dibatalkan.

	Yang dikejar Timbangan yang jatuh ke hari yang Data TBS-nya sudah disubmit —
	timbangan bertanggal mundur, tapi juga timbangan hari ini yang masuk sesudah
	Data TBS hari ini ditutup. Jumlah TBS Diterima cuma ditulis waktu Get Data
	ditekan, jadi tanpa ini angkanya berhenti di keadaan waktu tombol itu
	ditekan, dan Stock Entry harian ikut tertinggal.

	Selama hari itu dan hari-hari sesudahnya masih draft semua, tidak ada yang
	diantrikan: angkanya akan terbaca sendiri waktu Get Data ditekan dan belum
	ada Stock Entry yang bisa meleset.

	Dikerjakan di latar belakang, bukan di dalam transaksi submit. Fase Stock
	Entry membatalkan lalu membuat ulang dokumen stok dan sempat mematikan
	larangan stok minus — pekerjaan yang tidak boleh menumpang di request orang
	yang cuma menimbang truk.
	"""
	if doc.type != "Receive" or doc.receive_type not in ("TBS Internal", "TBS Eksternal"):
		return

	if not (doc.unit and doc.posting_date):
		return

	if not frappe.db.exists(DOCTYPE, {
		"unit": doc.unit,
		"docstatus": 1,
		"tanggal_produksi": (">=", doc.posting_date),
	}):
		return

	# Sengaja tidak di-deduplicate: kalau satu job sedang jalan, enqueue
	# berikutnya akan dilewati frappe, dan timbangan yang baru saja masuk ikut
	# hilang dari hitungan. Jobnya idempoten, jadi jalan dua kali lebih murah
	# daripada tidak jalan sama sekali.
	frappe.enqueue(
		"sth.mill.doctype.data_tbs.data_tbs.hitung_ulang_rantai",
		queue="long",
		timeout=3600,
		# Wajib: tanpa ini jobnya bisa mulai sebelum submit-nya ter-commit, dan
		# yang dibaca get_total_tbs masih keadaan sebelum timbangan ini.
		enqueue_after_commit=True,
		unit=doc.unit,
		sejak=doc.posting_date,
	)

	frappe.msgprint(
		_("Data TBS unit {0} sejak {1} dihitung ulang di latar belakang, termasuk Stock Entry-nya.").format(
			doc.unit, frappe.format(doc.posting_date, {"fieldtype": "Date"})),
		alert=True,
		indicator="blue",
	)

def hitung_ulang_rantai(unit, sejak, posting_ulang=True, lapor=None, izinkan_minus=True, commit=True):
	"""Baca ulang TBS diterima dan rantai restan satu unit sejak satu tanggal.

	Yang diperbaiki terutama dokumen yang sudah disubmit. Jumlah TBS Diterima
	cuma ditulis di `get_data`, yaitu waktu tombolnya ditekan, jadi Timbangan
	yang baru masuk — atau dibatalkan — sesudah itu tidak pernah terbaca lagi.
	Timbangan bertanggal mundur, misalnya yang baru dibuat hari ini untuk 1
	September, selalu jatuh ke kasus ini.

	Hari-hari sesudahnya ikut dihitung karena Jumlah TBS Diterima masuk ke Grand
	Total TBS, yang membagi diri jadi tbs olah, tbs restan, dan tbs loading ramp,
	dan Total TBS Restan-nya jadi restan awal hari berikutnya.

	Restan awal dokumen pertama tidak ditetapkan sendiri, tapi diambil dari
	dokumen terakhir sebelumnya lewat `get_restan_awal`, jadi rantai sebelum
	`sejak` tidak ikut bergerak.

	Dua fase: angka dokumennya dulu, lalu Stock Entry harian yang qty atau
	arahnya jadi tidak cocok lagi diposting ulang. Dipisah supaya kalau
	pembatalan STE tertahan periode akuntansi yang sudah tutup, angka dokumennya
	tetap sudah benar. `posting_ulang=False` menjalankan fase pertama saja.

	`izinkan_minus` dan `commit` dua-duanya harus mati waktu dipanggil dari dalam
	transaksi submit orang lain — itu yang dipakai hitung_ulang_dokumen_sesudahnya.
	Penjaga stok minus me-rollback pekerjaan yang belum di-commit waktu selesai,
	dan commit di tengah menutup transaksi submit yang sedang berjalan sebelum
	dokumennya sendiri tuntas.

	Aman dijalankan ulang: dokumen yang angkanya sudah cocok dan STE yang sudah
	benar sama-sama dilewati. Dari konsol:

	    bench --site NAMA execute sth.mill.doctype.data_tbs.data_tbs.hitung_ulang_rantai \
	        --kwargs "{'unit': 'TPRM', 'sejak': '2026-09-01'}"
	"""
	sejak = getdate(sejak)

	dokumen = frappe.get_all(
		DOCTYPE,
		filters={"unit": unit, "docstatus": ("<", 2), "tanggal_produksi": (">=", sejak)},
		fields=["name", "unit", "tanggal_produksi"],
		order_by="tanggal_produksi asc, creation asc",
		limit_page_length=0,
	)

	hasil = frappe._dict(dokumen=len(dokumen), angka=0, ste=0, kembar=[])

	if not dokumen:
		return hasil

	kembar = cari_kembar(dokumen)
	hasil.kembar = sorted(nama for daftar in kembar.values() for nama in daftar)

	hasil.angka = hitung_ulang_dokumen(dokumen, kembar)

	# Harus di-commit sebelum fase STE: izinkan_stock_minus me-rollback sisa
	# pekerjaan yang belum di-commit waktu selesai, dan itu akan ikut membuang
	# angka dokumen yang baru saja dibetulkan. Waktu penjaganya tidak dipakai,
	# tidak ada yang me-rollback dan commitnya tidak perlu.
	if commit:
		frappe.db.commit()

	if posting_ulang:
		dikerjakan = [row for row in dokumen if kunci(row) not in kembar]
		hasil.ste = posting_ulang_ste(
			dikerjakan, lapor=lapor, izinkan_minus=izinkan_minus, commit=commit
		)

	# Dicatat juga waktu dipanggil dari background job, yang tidak punya tempat
	# lain untuk melapor: log jobnya cuma menyimpan sukses atau gagal.
	frappe.logger("data_tbs").info(
		"hitung_ulang_rantai {0} sejak {1}: {2} dokumen, {3} angka berubah, {4} Stock Entry dibuat ulang".format(
			unit, sejak, hasil.dokumen, hasil.angka, hasil.ste))

	return hasil


def kunci(row):
	return (row.unit, str(row.tanggal_produksi))


def cari_kembar(dokumen):
	"""unit + tanggal yang punya lebih dari satu dokumen hidup.

	Hari kembar tidak ikut dihitung ulang. `get_total_tbs` menjumlahkan seluruh
	timbangan sehari penuh tanpa tahu dokumen mana yang seharusnya memikulnya,
	jadi dua dokumen di hari yang sama akan sama-sama diberi total penuh dan hari
	itu masuk dua kali ke rantai restan.

	Dokumen seperti ini tidak bisa dibuat lagi — `validate_duplikat` menolaknya —
	tapi yang telanjur ada sejak sebelum penjagaan itu masih tertinggal. Mana
	yang harus dibatalkan adalah keputusan orang, bukan tebakan fungsi ini.
	"""
	hitung = {}

	for row in dokumen:
		hitung.setdefault(kunci(row), []).append(row.name)

	return {k: v for k, v in hitung.items() if len(v) > 1}


def hitung_ulang_dokumen(dokumen, kembar):
	"""Isi ulang TBS diterima tiap dokumen, lalu rantai restan awalnya."""
	restan = None
	diperbaiki = 0

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)

		if restan is None:
			# Sambungan ke rantai sebelum rentang ini, dibaca sekali dari dokumen
			# terakhir sebelum dokumen pertama yang dikerjakan.
			restan = get_restan_awal(doc.unit, doc.tanggal_produksi, doc.name, doc.creation)

		if kunci(row) in kembar:
			# Dilewati, tapi rantainya tetap diteruskan dari angka tersimpannya:
			# hari sesudahnya tidak boleh ikut hilang cuma karena hari ini kembar.
			restan = flt(doc.total_tbs_restan)
			continue

		# Dibulatkan dulu sebelum dibanding: nilai yang dibaca dari kolom decimal
		# selalu beda di digit terakhir dari hasil hitungan float.
		sebelum = angka_turunan(doc)

		# flt: get_total_tbs memulangkan None kalau tidak ada timbangan sama
		# sekali di hari itu — SUM atas nol baris itu NULL, bukan 0.
		doc.jumlah_tbs_diterima = flt(get_total_tbs(doc.tanggal_produksi, doc.unit))
		doc.jumlah_tbs_restan = flt(restan)
		doc.calculate_totals()
		restan = flt(doc.total_tbs_restan)

		if angka_turunan(doc) == sebelum:
			continue

		# db_update, bukan save: dokumennya sudah disubmit dan yang diubah cuma
		# angka turunan yang seluruhnya read only di form.
		doc.db_update()
		diperbaiki += 1

	return diperbaiki


def angka_turunan(doc):
	# Presisi field tidak dipakai: total_tbs_restan presisinya 0 supaya tampil
	# bulat di form, padahal selisih setengah kilo tetap harus ikut dibetulkan.
	return tuple(flt(doc.get(field), 3) for field in (
		"jumlah_tbs_diterima", "jumlah_tbs_restan", "grand_total_tbs",
		"berat_rata_rata_tbs", "tbs_olah", "tbs_restan", "tbs_loading_ramp",
		"total_tbs_restan",
	))


def posting_ulang_ste(dokumen, lapor=None, izinkan_minus=True, commit=True):
	"""Buat ulang Stock Entry dokumen submitted yang STE-nya belum sesuai.

	`lapor` dipanggil tiap satu dokumen selesai, supaya patch bisa mencetak
	kemajuannya. Memulangkan jumlah Stock Entry yang jadi dibuat.

	`izinkan_minus` dan `commit` dimatikan waktu dipanggil dari dalam transaksi
	submit orang lain; alasannya di hitung_ulang_rantai.
	"""
	lapor = lapor or (lambda pesan: None)
	perlu = []

	for row in dokumen:
		doc = frappe.get_doc(DOCTYPE, row.name)
		if doc.docstatus == 1 and not ste_sudah_benar(doc):
			perlu.append(doc)

	if not perlu:
		lapor("Stock Entry Data TBS sudah sesuai semua, dilewati.")
		return 0

	perlu.sort(key=lambda doc: (getdate(doc.tanggal_produksi), doc.creation))
	dibuat = 0

	penjaga = izinkan_stock_minus() if izinkan_minus else contextlib.nullcontext()

	with penjaga:
		for urutan, doc in enumerate(perlu, 1):
			dibuat += buat_ulang_ste(doc)

			if commit:
				frappe.db.commit()

			lapor("[{0}/{1}] {2} selesai.".format(urutan, len(perlu), doc.name))

	lapor("{0} Stock Entry Data TBS diposting ulang ke tanggal prosesnya.".format(dibuat))

	antri = antrian_repost()
	if antri:
		lapor("{0} Repost Item Valuation mengantre, nilai stok menyesuaikan setelah scheduler selesai.".format(antri))

	return dibuat


def ste_sudah_benar(doc):
	"""Benar kalau tanggal, arah, dan qty STE-nya sudah cocok dengan dokumennya."""
	selisih = flt(doc.total_tbs_restan) - flt(doc.jumlah_tbs_restan)

	ste = frappe.get_all(
		"Stock Entry",
		filters={"references": doc.name, "docstatus": 1},
		fields=["name", "posting_date", "stock_entry_type"],
	)

	if not flt(selisih, 3):
		return not ste

	if len(ste) != 1:
		return False

	ste = ste[0]

	if getdate(ste.posting_date) != getdate(doc.tanggal_produksi):
		return False

	arah = "Material Receipt" if selisih > 0 else "Material Issue"
	if ste.stock_entry_type != arah:
		return False

	qty = frappe.db.get_value("Stock Entry Detail", {"parent": ste.name}, "sum(qty)")

	# Toleransi sekilo per seratus, di bawah presisi qty Stock Entry, supaya STE
	# yang cuma beda pembulatan tidak ikut diposting ulang.
	return abs(flt(qty) - abs(selisih)) < 0.01


def antrian_repost():
	"""Penilaian stok dihitung ulang scheduler, bukan di sini.

	STE bertanggal mundur bikin ERPNext mengantrikan Repost Item Valuation.
	Menjalankannya langsung bisa memakan waktu berjam-jam dan menahan
	pemanggilnya.
	"""
	return frappe.db.count("Repost Item Valuation", {"status": ("in", ("Queued", "In Progress"))})
