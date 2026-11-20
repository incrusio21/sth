"""Isi total janjang dan brondolan Timbangan TBS Internal lama, lalu Sortasi-nya.

Sebelum set_janjang_brondolan_kebun, kedua field itu cuma terisi kalau
pengirim API membawanya sendiri, jadi banyak tiket kendaraan inti kebun yang
nol dan Sortasi-nya ikut kosong. Sumbernya sama dengan validate Timbangan:
SPB dulu, catatan pos (Security Check Point) kalau SPB-nya pun nol. Angka yang
sudah ada tidak ditimpa.

Ditulis lewat db.set_value tanpa menaikkan modified: dokumennya banyak yang
sudah submit, dan cuma field informasi yang berubah.

Manual, tidak didaftarkan di patches.txt. Default-nya uji coba:
	bench --site <site> execute sth.patches.isi_janjang_brondolan_timbangan.execute
	bench --site <site> execute sth.patches.isi_janjang_brondolan_timbangan.execute --kwargs "{'terapkan': 1}"
"""

import frappe
from frappe.utils import cint, flt


def execute(terapkan=0):
	terapkan = cint(terapkan)

	rows = frappe.db.sql(
		"""
		select t.name, t.total_janjang, t.total_brondolan,
			spb.total_janjang as spb_jjg, spb.total_brondolan as spb_brd,
			scp.total_jjg as pos_jjg, scp.total_brd as pos_brd
		from `tabTimbangan` t
		left join `tabSurat Pengantar Buah` spb on spb.name = t.spb
		left join `tabSecurity Check Point` scp on scp.name = t.ticket_number
		where t.receive_type = 'TBS Internal'
			and t.docstatus < 2
			and (ifnull(t.total_janjang, 0) = 0 or ifnull(t.total_brondolan, 0) = 0)
		""",
		as_dict=True,
	)

	timbangan_berubah = 0
	for r in rows:
		values = {}
		if not flt(r.total_janjang):
			jjg = flt(r.spb_jjg) or flt(r.pos_jjg)
			if jjg:
				values["total_janjang"] = jjg
		if not flt(r.total_brondolan):
			brd = flt(r.spb_brd) or flt(r.pos_brd)
			if brd:
				values["total_brondolan"] = brd

		if not values:
			continue

		timbangan_berubah += 1
		if terapkan:
			frappe.db.set_value("Timbangan", r.name, values, update_modified=False)

	# Sortasi selalu disamakan dengan Timbangan-nya, termasuk yang Timbangan-nya
	# sudah benar sejak awal tapi Sortasi-nya dibuat sebelum field ini ada.
	sortasi = frappe.db.sql(
		"""
		select s.name, t.total_janjang, t.total_brondolan
		from `tabSortasi` s
		join `tabTimbangan` t on t.name = s.no_timbangan
		where s.docstatus < 2
			and t.receive_type = 'TBS Internal'
			and (ifnull(s.total_janjang, 0) != ifnull(t.total_janjang, 0)
				or ifnull(s.total_brondolan, 0) != ifnull(t.total_brondolan, 0))
		""",
		as_dict=True,
	)

	if terapkan:
		# dibaca ulang dari Timbangan supaya ikut angka yang baru diisi di atas
		frappe.db.sql(
			"""
			update `tabSortasi` s
			join `tabTimbangan` t on t.name = s.no_timbangan
			set s.total_janjang = ifnull(t.total_janjang, 0),
				s.total_brondolan = ifnull(t.total_brondolan, 0)
			where s.docstatus < 2
				and t.receive_type = 'TBS Internal'
			"""
		)
		frappe.db.commit()

	print(
		f"{'DITERAPKAN' if terapkan else 'UJI COBA'}: "
		f"{timbangan_berubah} Timbangan diisi dari {len(rows)} kandidat, "
		f"{len(sortasi)} Sortasi berbeda dengan Timbangan-nya (sebelum Timbangan diisi)"
	)
