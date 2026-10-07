# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _, unscrub
from frappe.utils import cint, cstr, flt

from sth.controllers.plantation_controller import PlantationController, fetch_kegiatan_company

force_item_fields = (
	"voucher_type",
	"voucher_no"
)

# Tarif dan basis upah tidak ikut dikirim sistem luar maupun diisi tangan: semuanya
# diambil dari master Kegiatan Company tiap kali dokumen disimpan.
FIELD_BASIS_KEGIATAN = ["volume_basis", "rupiah_basis"]

PPB = "Permintaan Pengeluaran Barang"


class RencanaKerjaHarian(PlantationController):
	def update_rate_or_qty_value(self, item, precision):
		if item.parentfield == "kegiatan_detail":
			# Panen dibayar per volume, sisanya per orang — sama seperti waktu
			# kegiatan masih satu per dokumen di calculate_kegiatan_amount().
			item.rate = flt(item.rupiah_basis)
			item.qty = flt(item.target_volume) if item.tipe_kegiatan == "Panen" else cint(item.qty_tenaga_kerja)

		if item.parentfield == "material" and self.total_luas:
			# Pembaginya total luas seluruh baris kegiatan, bukan luas satu kegiatan:
			# tabel material berdiri sendiri di level dokumen dan tidak menunjuk
			# baris kegiatan mana pun.
			item.qty = flt(item.dosis / self.total_luas, precision)

	def validate(self):
		# Urutannya penting. calculate() di super().validate() membaca rupiah_basis
		# tiap baris dan total_luas dokumen, jadi keduanya harus sudah terisi
		# sebelum sampai ke sana.
		self.isi_data_kegiatan()
		self.hitung_total_kegiatan()
		self.isi_rencana_kerja_bulanan()
		self.isi_rate_material()
		self.buang_material_tanpa_perawatan()
		self.validate_duplicate_rkh()

		super().validate()

	def on_submit(self):
		self.buat_permintaan_pengeluaran_barang()

	def on_cancel(self):
		self.batalkan_permintaan_pengeluaran_barang()

	def buat_permintaan_pengeluaran_barang(self):
		"""Ajukan material RKH ini ke gudang central sebagai Permintaan Pengeluaran Barang.

		RKH tidak boleh gagal karena permintaannya. Yang bisa dilengkapi langsung
		disubmit; yang terganjal — stok kurang, penerima atau akun belum ada —
		ditinggal di draft untuk dibereskan gudang, dan alasannya dicatat di RKH.
		"""
		if frappe.db.exists(PPB, {"rencana_kerja_harian": self.name, "docstatus": ["<", 2]}):
			return

		items = self.susun_item_permintaan_pengeluaran()
		if not items:
			return

		ppb = frappe.new_doc(PPB)
		ppb.update({
			"pt_pemilik_barang": self.company,
			"gudang": self.gudang_central,
			"tanggal": self.posting_date,
			"nama_karyawan": self.nik_penerima_material or self.mandor,
			"catatan": _("Material RKH {0}").format(self.name)
				+ (" / Trans No {0}".format(self.trans_no) if self.trans_no else ""),
			"rencana_kerja_harian": self.name,
		})
		ppb.set("items", items)

		ppb.flags.ignore_permissions = True
		# submit diputuskan di sini, bukan oleh approve_api yang menyubmit semua
		# dokumen milik user API begitu di-insert
		ppb.flags.lewati_submit_otomatis = True

		# Pesan validasi PPB yang ditangkap di bawah jangan sampai muncul sebagai
		# popup error di RKH yang sebenarnya berhasil disubmit.
		mute_messages = frappe.flags.mute_messages
		frappe.flags.mute_messages = True

		try:
			frappe.db.savepoint("rkh_buat_ppb")
			try:
				# field wajib yang kosong tidak boleh menggagalkan draft-nya;
				# baru ditagih waktu submit
				ppb.flags.ignore_mandatory = True
				ppb.insert()
			except Exception as e:
				frappe.db.rollback(save_point="rkh_buat_ppb")
				frappe.log_error(
					title=_("Permintaan Pengeluaran Barang RKH {0} gagal dibuat").format(self.name),
					reference_doctype=self.doctype, reference_name=self.name,
				)
				self.add_comment("Comment", _(
					"Permintaan Pengeluaran Barang tidak bisa dibuat otomatis: {0}"
				).format(pesan_error(e)))
				return

			frappe.db.savepoint("rkh_submit_ppb")
			try:
				ppb.flags.ignore_mandatory = False
				ppb.submit()
			except Exception as e:
				frappe.db.rollback(save_point="rkh_submit_ppb")
				self.add_comment("Comment", _(
					"Permintaan Pengeluaran Barang {0} ditinggal di Draft: {1}"
				).format(frappe.bold(ppb.name), pesan_error(e)))
		finally:
			frappe.flags.mute_messages = mute_messages

	def susun_item_permintaan_pengeluaran(self):
		"""Baris Permintaan Pengeluaran Barang dari tabel material.

		Material RKH tidak menunjuk blok, padahal blok yang menentukan cost center
		waktu barangnya keluar. Total dosis tiap barang dibagi ke baris kegiatan
		Perawatan sebanding luasnya — sama dengan anggapan qty = dosis / total_luas
		di update_rate_or_qty_value. Sisa pembulatan jatuh ke baris terakhir supaya
		jumlahnya tetap sama dengan dosis.
		"""
		perawatan = [r for r in self.kegiatan_detail if r.tipe_kegiatan == "Perawatan"]
		if not perawatan:
			return []

		kebutuhan = {}
		for m in self.material:
			if m.item and flt(m.dosis):
				kebutuhan.setdefault((m.item, m.uom), 0)
				kebutuhan[(m.item, m.uom)] += flt(m.dosis)

		luas = sum(flt(r.target_volume) for r in perawatan)
		precision = cint(frappe.get_meta(PPB + " Item").get_field("jumlah").precision) or 2
		akun = {}
		items = []

		for (item, uom), dosis in kebutuhan.items():
			sisa = dosis

			for i, row in enumerate(perawatan):
				if i == len(perawatan) - 1:
					jumlah = flt(sisa, precision)
				elif luas:
					jumlah = flt(dosis * flt(row.target_volume) / luas, precision)
				else:
					jumlah = flt(dosis / len(perawatan), precision)

				sisa -= jumlah
				if not jumlah:
					continue

				if row.kegiatan not in akun:
					akun[row.kegiatan] = (fetch_kegiatan_company(
						row.kegiatan, self.company, self.unit, ["account"]
					) or {}).get("account")

				items.append({
					"kode_barang": item,
					"satuan": uom or frappe.db.get_value("Item", item, "stock_uom"),
					"jumlah": jumlah,
					"sub_unit": self.divisi,
					"blok": row.blok,
					"kegiatan": row.kegiatan,
					"account": akun[row.kegiatan],
				})

		return items

	def batalkan_permintaan_pengeluaran_barang(self):
		"""Tarik permintaan barang yang lahir dari RKH ini.

		Draft dihapus, yang sudah disubmit dibatalkan. Kalau barangnya sudah ada
		yang keluar, RKH tidak boleh batal sebelum Pengeluaran Barang-nya dibatalkan.
		"""
		for nama in frappe.get_all(
			PPB, filters={"rencana_kerja_harian": self.name, "docstatus": ["<", 2]}, pluck="name"
		):
			ppb = frappe.get_doc(PPB, nama)

			if ppb.docstatus == 0:
				frappe.delete_doc(PPB, nama, ignore_permissions=True)
				continue

			if flt(ppb.outgoing) > 0:
				frappe.throw(
					_("Barang di Permintaan Pengeluaran Barang {0} sudah dikeluarkan. Batalkan "
					  "dulu Pengeluaran Barang-nya.").format(frappe.bold(nama)),
					title=_("Barang Sudah Keluar")
				)

			ppb.flags.ignore_permissions = True
			ppb.cancel()

	def isi_data_kegiatan(self):
		"""Lengkapi tiap baris kegiatan dari master: kategori, tipe, dan basis upah.

		fetch_from di baris memang sudah menunjuk field yang benar, tapi hanya jalan
		untuk dokumen yang lewat form. Kiriman API mengirim kode kegiatannya saja,
		dan tanpa isian ini seluruh baris berakhir dengan rupiah_basis 0 — biayanya
		nol tanpa ada yang salah kelihatan.
		"""
		for row in self.kegiatan_detail:
			kegiatan = frappe.db.get_value(
				"Kegiatan", row.kegiatan, ["kategori_kegiatan", "tipe_kegiatan"], as_dict=True
			)

			if not kegiatan:
				frappe.throw(
					_("Baris {0}: Kegiatan {1} tidak ditemukan.").format(row.idx, frappe.bold(row.kegiatan)),
					title=_("Kegiatan Tidak Dikenali")
				)

			row.kategori_kegiatan = kegiatan.kategori_kegiatan
			row.tipe_kegiatan = kegiatan.tipe_kegiatan
			row.is_bibitan = cint(
				frappe.db.get_value("Kategori Kegiatan", row.kategori_kegiatan, "is_bibitan")
			) if row.kategori_kegiatan else 0

			basis = fetch_kegiatan_company(row.kegiatan, self.company, self.unit, list(FIELD_BASIS_KEGIATAN))
			if not basis:
				frappe.throw(
					_("Baris {0}: Kegiatan {1} belum punya baris untuk Company {2} di tabel "
					  "Kegiatan Company. Lengkapi dulu di master Kegiatan — tarif upahnya "
					  "diambil dari situ.").format(
						row.idx, frappe.bold(row.kegiatan), frappe.bold(self.company)
					),
					title=_("Kegiatan Belum Diatur untuk Company Ini")
				)

			row.update(basis)

			# Jumlah tenaga kerja diturunkan dari rincian laki-laki + perempuan kalau
			# keduanya dikirim; kalau tidak, jatuh ke hitungan basis seperti dulu.
			rincian = cint(row.jumlah_tk_laki_laki) + cint(row.jumlah_tk_perempuan)
			if rincian:
				row.qty_tenaga_kerja = rincian
			elif not row.qty_tenaga_kerja:
				row.qty_tenaga_kerja = cint(flt(row.target_volume / row.volume_basis)) if row.volume_basis else 0

	def hitung_total_kegiatan(self):
		self.total_luas = flt(sum(flt(r.target_volume) for r in self.kegiatan_detail))
		self.total_tenaga_kerja = sum(cint(r.qty_tenaga_kerja) for r in self.kegiatan_detail)
		self.total_tk_laki_laki = sum(cint(r.jumlah_tk_laki_laki) for r in self.kegiatan_detail)
		self.total_tk_perempuan = sum(cint(r.jumlah_tk_perempuan) for r in self.kegiatan_detail)

	def isi_rencana_kerja_bulanan(self):
		"""Tempelkan Rencana Kerja Bulanan yang menaungi tiap baris kegiatan.

		Sengaja tidak menggagalkan dokumen kalau RKB-nya tidak ketemu. Pencarian ini
		dulu memang dimatikan — get_rencana_kerja_bulanan dipanggil dari validate lalu
		dikomentari, begitu juga get_rkb_data di sisi form — jadi menyalakannya
		sebagai syarat akan menolak dokumen yang selama ini lolos. Yang ketemu
		dipakai, yang tidak dibiarkan kosong, persis seperti keadaan sekarang.

		Referensinya turun ke baris karena satu RKH sekarang bisa memuat kegiatan
		dari beberapa RKB sekaligus. Rencana Kerja Bulanan menjumlahkan pemakaian
		anggarannya dari baris-baris ini, lihat calculate_used_and_realized.
		"""
		for row in self.kegiatan_detail:
			if row.voucher_no:
				continue

			rkb = cari_rencana_kerja_bulanan(
				row.kegiatan, row.tipe_kegiatan, self.divisi,
				row.batch if row.is_bibitan else row.blok, self.posting_date,
				row.is_bibitan
			)

			if rkb:
				row.voucher_type, row.voucher_no = rkb

	def isi_rate_material(self):
		"""Ambil tarif material dari baris Rencana Kerja Bulanan Perawatan yang menaunginya.

		Sistem luar cuma mengirim kode material dan jumlahnya — tarifnya tidak ada di
		payload mana pun, dan tanpa isian ini seluruh baris material dari API
		ber-amount nol. Yang sudah punya tarif tidak disentuh, supaya angka yang
		sengaja diketik di form tidak tertimpa master.

		prevdoc_detail ikut dipasang karena Rencana Kerja Bulanan Perawatan
		mencocokkan pemakaian materialnya lewat kolom itu, bukan lewat kode item.
		"""
		kosong = [d for d in self.material if not flt(d.rate)]
		if not kosong:
			return

		rkb = [
			r.voucher_no for r in self.kegiatan_detail
			if r.voucher_type == "Rencana Kerja Bulanan Perawatan" and r.voucher_no
		]
		if not rkb:
			return

		per_item = {}
		for r in frappe.get_all(
			"Detail Material RK",
			filters={"parent": ["in", rkb]},
			fields=["item", "rate", "name"],
			order_by="parent, idx",
		):
			per_item.setdefault(r.item, r)

		for d in kosong:
			ref = per_item.get(d.item)
			if not ref:
				continue

			d.rate = ref.rate
			if not d.prevdoc_detail:
				d.prevdoc_detail = ref.name

	def buang_material_tanpa_perawatan(self):
		"""Material hanya berlaku untuk RKH yang memuat kegiatan Perawatan.

		Aturan yang sama seperti dulu, cuma sekarang dilihat dari seluruh baris:
		satu saja baris Perawatan sudah cukup untuk menahan tabelnya.
		"""
		if not any(r.tipe_kegiatan == "Perawatan" for r in self.kegiatan_detail):
			self.material = []

	def validate_duplicate_rkh(self):
		"""Tahan kegiatan yang blok dan tanggalnya sudah direncanakan di tempat lain.

		Dua lapis: sesama baris di dokumen ini, lalu ke dokumen lain yang sudah
		disubmit. Pengecekan lama membandingkan kolom `kode_kegiatan` yang sudah
		tidak ada lagi di RKH — namanya `kegiatan` sejak lama — sehingga yang
		tersaring sebenarnya kolom sisa yang tidak pernah terisi.
		"""
		terpakai = {}

		for row in self.kegiatan_detail:
			kunci = (row.kegiatan, row.blok or "", row.batch or "")
			if kunci in terpakai:
				frappe.throw(
					_("Baris {0} mengulang kegiatan {1} untuk {2} yang sudah ada di baris {3}.").format(
						row.idx, frappe.bold(row.kegiatan),
						frappe.bold(row.batch if row.is_bibitan else row.blok), terpakai[kunci]
					),
					title=_("Kegiatan Kembar")
				)

			terpakai[kunci] = row.idx

			kembar = frappe.db.sql(
				"""
				SELECT rkh.name
				FROM `tabRencana Kerja Harian` rkh
				INNER JOIN `tabDetail RKH Kegiatan` k ON k.parent = rkh.name
				WHERE rkh.docstatus = 1
					AND rkh.name != %(name)s
					AND rkh.divisi = %(divisi)s
					AND rkh.posting_date = %(posting_date)s
					AND k.kegiatan = %(kegiatan)s
					AND COALESCE(k.blok, '') = %(blok)s
					AND COALESCE(k.batch, '') = %(batch)s
				LIMIT 1
				""",
				{
					"name": self.name or "",
					"divisi": self.divisi,
					"posting_date": self.posting_date,
					"kegiatan": row.kegiatan,
					"blok": row.blok or "",
					"batch": row.batch or "",
				},
			)

			if kembar:
				frappe.throw(
					_("Baris {0}: Rencana Kerja Harian untuk kegiatan ini sudah ada di {1}.").format(
						row.idx, frappe.bold(kembar[0][0])
					),
					title=_("Rencana Kerja Harian Kembar")
				)


def pesan_error(e):
	return frappe.utils.strip_html(cstr(e)).strip() or type(e).__name__


def cari_rencana_kerja_bulanan(kegiatan, tipe_kegiatan, divisi, blok, posting_date, is_bibitan=0):
	"""(voucher_type, nama RKB) yang menaungi kegiatan ini, atau None.

	Bedanya dengan get_rencana_kerja_bulanan di bawah: yang ini diam saja kalau
	tidak ketemu. Dipakai waktu menyimpan dokumen, di mana RKB yang belum ada tidak
	boleh menghentikan RKH-nya.
	"""
	if not (kegiatan and tipe_kegiatan and divisi and blok and posting_date):
		return None

	voucher_type = frappe.db.get_value("Tipe Kegiatan", tipe_kegiatan, "rkb_voucher_type")
	if not voucher_type:
		return None

	fieldname = "batch" if cint(is_bibitan) else "blok"

	rkb = frappe.db.get_value(voucher_type, {
		"kode_kegiatan": kegiatan, "divisi": divisi, fieldname: blok,
		"from_date": ["<=", posting_date], "to_date": [">=", posting_date],
		"docstatus": 1
	}, "name")

	return (voucher_type, rkb) if rkb else None


@frappe.whitelist()
def get_material(kode_kegiatan):
	item_kegiatan = frappe.get_all("Kegiatan Material", filters={
		"parent": kode_kegiatan
	}, fields=["item_code as item", "item_group", "uom"])

	return {"material": item_kegiatan}

@frappe.whitelist()
def get_rencana_kerja_bulanan(kode_kegiatan, tipe_kegiatan, divisi, blok, posting_date, is_bibitan=False):
	voucher_type = frappe.get_value("Tipe Kegiatan", tipe_kegiatan, "rkb_voucher_type")
	fieldname = "batch" if cint(is_bibitan) else "blok"

	rkb = frappe.db.get_value(voucher_type, {
		"kode_kegiatan": kode_kegiatan, "divisi": divisi, fieldname: blok, "from_date": ["<=", posting_date], "to_date": [">=", posting_date],
		"docstatus": 1
	}, "name")

	if not rkb:
		frappe.throw(""" {} not Found for Filters <br>
			Kegiatan : {} <br>
			Divisi : {} <br>
			{} : {} <br>
			Date : {} """.format(voucher_type, kode_kegiatan, divisi, unscrub(fieldname), blok, posting_date))

	# no rencana kerja bualanan
	ress = { "voucher_type": voucher_type, "voucher_no": rkb}
	if voucher_type == "Rencana Kerja Bulanan Perawatan":
		ress["material"] = frappe.db.get_all("Detail Material RK",
			filters={"parent": rkb}, fields=["item", "rate", "uom", "name as prevdoc_detail"]
		)
	if voucher_type == "Rencana Kerja Bulanan Pengangkutan Panen":
		ress["kendaraan"] = frappe.db.get_all("RKB Pengangkutan Kendaraan",
			filters={"parent": rkb}, fields=["item", "uom", "kap_kg", "qty", "rate", "amount"]
		)

	return ress
