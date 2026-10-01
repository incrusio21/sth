"""Lampiran Legal berakhiran hash digabung kembali ke nama aslinya.

Sebelum override File menimpa berkas bernama sama di modul Legal, akta yang
diunggah ulang mendapat nama `akta2246c9.pdf` dan tertinggal berdampingan dengan
`akta.pdf`. Di sini keduanya digabung seperti yang sekarang terjadi saat
unggah: satu isi dipakai di nama asli, field lampiran dokumen Legal diarahkan ke
url nama asli, dan baris File lain dihapus supaya tinggal satu baris.

Isi yang dipakai adalah versi yang dirujuk field lampiran dokumen tersimpan, baru
kalau tidak ada yang dirujuk diambil unggahan terbaru. Unggahan terbaru saja tidak
cukup: banyak lampiran diunggah ke form `new-anggaran-dasar-...` yang tidak pernah
disimpan, dan versi itu bisa lebih baru dari yang benar-benar dipakai dokumennya.

Yang dianggap berakhiran hash adalah nama dengan enam karakter hex sebelum
ekstensinya, kalau karakter itu sama dengan ujung content_hash isinya — itu yang
ditulis generate_file_name milik frappe — atau kalau nama tanpa akhiran itu memang
ada. Syarat kedua perlu karena hash saja meleset: generate_file_name memakai
akhiran acak kalau akhiran hashnya sudah terpakai, dan versi yang dirujuk dokumen
bisa justru yang itu. Satu kelompok dilewati utuh kalau ada satu saja
baris di salah satu url-nya yang bukan milik modul Legal, sama dengan aturan
boleh_menimpa di override.

Versi lama dibuang dan tidak bisa dikembalikan; jalankan dengan dry_run dulu:
`bench --site <site> execute sth.patches.gabung_berkas_akhiran_hash_legal.execute --kwargs "{'dry_run': 1}"`.
"""

import os
import re

import frappe
from frappe.core.doctype.file.utils import get_content_hash

from sth.overrides.file import dari_modul_timpa, path_berkas, url_berkas

POLA_AKHIRAN_HASH = re.compile(r"^(.*)([0-9a-f]{6})(\.[^.]+)?$")


def execute(dry_run=False):
	per_url = {}
	for r in frappe.get_all(
		"File",
		filters={"is_folder": 0, "file_url": ["not like", "http%"]},
		fields=["name", "file_name", "file_url", "is_private", "content_hash", "attached_to_doctype", "creation"],
	):
		per_url.setdefault(r.file_url, []).append(r)

	kelompok = {}
	for url, rows in per_url.items():
		for r in rows:
			m = POLA_AKHIRAN_HASH.match(r.file_name or "")
			if not m or url != url_berkas(r.file_name, r.is_private):
				continue  # baris yang menumpang berkas lain bukan pemilik nama berakhiran hash
			asal = m.group(1) + (m.group(3) or "")
			akhiran_hash = r.content_hash and r.content_hash[-6:] == m.group(2)
			if not akhiran_hash and url_berkas(asal, r.is_private) not in per_url:
				continue
			kelompok.setdefault((r.is_private, asal), set()).add(url)

	fields = field_lampiran_legal()
	digabung = 0
	for (is_private, asal), urls in sorted(kelompok.items(), key=lambda k: k[0][1]):
		url_asal = url_berkas(asal, is_private)
		rows = [r for u in urls | {url_asal} for r in per_url.get(u, [])]
		if not all(dari_modul_timpa(r.attached_to_doctype) for r in rows):
			continue

		dirujuk = url_dirujuk(fields, urls | {url_asal})
		pemenang = max([r for r in rows if r.file_url in dirujuk] or rows, key=lambda r: r.creation)
		if not os.path.isfile(frappe.get_doc("File", pemenang.name).get_full_path()):
			print(f"{asal}: DILEWATI, berkas {pemenang.file_name} tidak ada di disk")
			continue

		print(
			f"{asal}: {len(rows)} baris, isi dari {pemenang.file_name} ({pemenang.creation}, "
			f"{'dirujuk dokumen' if pemenang.file_url in dirujuk else 'tidak dirujuk, terbaru'})"
		)
		digabung += 1
		if dry_run:
			continue

		try:
			gabungkan(fields, asal, is_private, url_asal, urls - {url_asal}, rows, pemenang)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			print(f"  GAGAL, dilewati:\n{frappe.get_traceback()}")

	print(f"{digabung} kelompok {'akan ' if dry_run else ''}digabung")


def gabungkan(fields, asal, is_private, url_asal, url_lain, rows, pemenang):
	path_asal = path_berkas(asal, is_private)
	path_pemenang = frappe.get_doc("File", pemenang.name).get_full_path()
	with open(path_pemenang, "rb") as f:
		isi = f.read()

	isi_lama = None
	if os.path.isfile(path_asal):
		with open(path_asal, "rb") as f:
			isi_lama = f.read()

	try:
		with open(path_asal, "wb") as f:
			f.write(isi)
			os.fsync(f.fileno())

		arahkan_field_lampiran(fields, url_lain, url_asal)
		frappe.db.set_value(
			"File",
			pemenang.name,
			{"file_name": asal, "file_url": url_asal, "content_hash": get_content_hash(isi), "file_size": len(isi)},
			update_modified=False,
		)
		# Sesudah pemenang pindah ke url asal, _delete_file_on_disk tiap baris yang
		# dihapus ikut membuang berkas berakhiran hash yang tidak dipakai lagi.
		for r in rows:
			if r.name != pemenang.name:
				frappe.delete_doc("File", r.name, ignore_permissions=True, force=True)
	except Exception:
		if isi_lama is None:
			os.remove(path_asal)
		else:
			with open(path_asal, "wb") as f:
				f.write(isi_lama)
		raise

	if path_pemenang != path_asal and os.path.isfile(path_pemenang):
		os.remove(path_pemenang)


def field_lampiran_legal():
	"""Field Attach di doctype Legal, termasuk tabel anaknya."""
	doctype_legal = frappe.get_all("DocType", filters={"module": "Legal"}, pluck="name")
	return frappe.get_all(
		"DocField",
		filters={"parent": ["in", doctype_legal], "fieldtype": ["in", ["Attach", "Attach Image"]]},
		fields=["parent as dt", "fieldname"],
	) + frappe.get_all(
		"Custom Field",
		filters={"dt": ["in", doctype_legal], "fieldtype": ["in", ["Attach", "Attach Image"]]},
		fields=["dt", "fieldname"],
	)


def url_dirujuk(fields, urls):
	dirujuk = set()
	for f in fields:
		dirujuk.update(
			frappe.db.sql_list(
				f"select distinct `{f.fieldname}` from `tab{f.dt}` where `{f.fieldname}` in %s", (tuple(urls),)
			)
		)
	return dirujuk


def arahkan_field_lampiran(fields, url_lain, url_asal):
	"""Field lampiran Legal yang masih menunjuk url berakhiran hash."""
	if not url_lain:
		return

	for f in fields:
		frappe.db.sql(
			f"update `tab{f.dt}` set `{f.fieldname}` = %s where `{f.fieldname}` in %s",
			(url_asal, tuple(url_lain)),
		)
