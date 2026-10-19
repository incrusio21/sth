import json
import os

import frappe
from frappe.utils import cint, now_datetime

KOLOM = ("account", "akun_potongan")


def cadangkan():
	"""Simpan isi tabel Accounts semua Salary Component ke berkas JSON.

	Dijalankan sebelum akun komponen diganti massal, supaya bisa dikembalikan
	dengan pulihkan(). Berkasnya di private/backups site, satu berkas per
	panggilan, namanya bercap waktu:

	    bench --site <site> execute sth.patches.cadangan_akun_salary_component.cadangkan
	"""
	kolom = ["name", "parent", "company"] + [k for k in KOLOM if frappe.db.has_column("Salary Component Account", k)]
	rows = frappe.get_all(
		"Salary Component Account",
		filters={"parenttype": "Salary Component"},
		fields=kolom,
		order_by="parent, company, idx",
	)

	folder = frappe.get_site_path("private", "backups")
	os.makedirs(folder, exist_ok=True)
	berkas = os.path.join(
		folder, "salary_component_account_{0}.json".format(now_datetime().strftime("%Y%m%d_%H%M%S"))
	)
	with open(berkas, "w") as f:
		json.dump({"dibuat": str(now_datetime()), "kolom": kolom, "rows": rows}, f, indent=1, default=str)

	print(f"{len(rows)} baris dari {len({r.parent for r in rows})} komponen disimpan ke:\n  {os.path.abspath(berkas)}")
	return berkas


def pulihkan(berkas, terapkan=0):
	"""Kembalikan akun tabel Accounts Salary Component dari berkas cadangkan().

	Baris dicocokkan lewat komponen + company, bukan nama baris: Data Import
	atau tabel yang disusun ulang di form melahirkan baris baru bernama lain.
	Kalau satu komponen punya lebih dari satu baris untuk company yang sama,
	nama barisnya yang dipakai. Cuma kolom akun yang dikembalikan; baris yang
	ditambahkan sesudah cadangan dibuat tidak dihapus, hanya dilaporkan.

	Tanpa terapkan=1 cuma melaporkan:

	    bench --site <site> execute sth.patches.cadangan_akun_salary_component.pulihkan --kwargs "{'berkas': '<path>', 'terapkan': 1}"
	"""
	with open(berkas) as f:
		data = json.load(f)

	kolom = [k for k in KOLOM if k in data["kolom"] and frappe.db.has_column("Salary Component Account", k)]
	sekarang = frappe.get_all(
		"Salary Component Account",
		filters={"parenttype": "Salary Component"},
		fields=["name", "parent", "company"] + kolom,
	)

	per_nama = {r.name: r for r in sekarang}
	per_kunci = {}
	for r in sekarang:
		per_kunci.setdefault((r.parent, r.company), []).append(r)

	diubah, hilang = [], []
	terpakai = set()
	for lama in data["rows"]:
		kandidat = per_kunci.get((lama["parent"], lama["company"]), [])
		if len(kandidat) == 1:
			baris = kandidat[0]
		else:
			baris = per_nama.get(lama["name"])

		if not baris:
			hilang.append(f"{lama['parent']} / {lama['company']}")
			continue

		terpakai.add(baris.name)
		beda = {k: lama.get(k) for k in kolom if (baris.get(k) or None) != (lama.get(k) or None)}
		if not beda:
			continue

		diubah.append("{0} / {1}: {2}".format(
			lama["parent"], lama["company"],
			", ".join(f"{k} {baris.get(k)} -> {v}" for k, v in beda.items()),
		))
		if cint(terapkan):
			frappe.db.set_value("Salary Component Account", baris.name, beda, update_modified=False)

	baru = [f"{r.parent} / {r.company}" for r in sekarang if r.name not in terpakai]

	print(f"Cadangan {data['dibuat']}, {len(data['rows'])} baris")
	cetak("Dikembalikan" if cint(terapkan) else "Akan dikembalikan", diubah)
	cetak("Baris di cadangan yang sudah tidak ada, dilewati", hilang)
	cetak("Baris yang tidak ada di cadangan, dibiarkan", baru)

	if cint(terapkan):
		frappe.clear_cache(doctype="Salary Component")
		frappe.db.commit()
	else:
		print("\nBelum ada yang diubah. Jalankan dengan terapkan=1 untuk mengembalikan.")


def cetak(judul, daftar):
	print(f"\n{judul}: {len(daftar)}")
	for d in daftar:
		print(f"  {d}")
