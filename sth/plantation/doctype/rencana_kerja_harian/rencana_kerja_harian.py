# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _, unscrub
from frappe.utils import cint, flt

from sth.controllers.plantation_controller import PlantationController, fetch_kegiatan_company

force_item_fields = (
	"voucher_type",
	"voucher_no"
)

# Tarif dan basis upah tidak ikut dikirim sistem luar maupun diisi tangan: semuanya
# diambil dari master Kegiatan Company tiap kali dokumen disimpan.
FIELD_BASIS_KEGIATAN = ["volume_basis", "rupiah_basis"]


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

			basis = fetch_kegiatan_company(row.kegiatan, self.company, list(FIELD_BASIS_KEGIATAN))
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
