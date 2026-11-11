import frappe
from frappe.utils import cint

from sth.custom.employee import buat_finger_id


def execute(terapkan=0, nama=None):
	"""Ganti finger_id semua Employee dengan 9 digit acak, yang lama ke old_finger_id.

	finger_id lama diambil dari 14 digit pertama no_ktp: bisa kembar antar
	employee dan terlalu panjang untuk PIN mesin. Yang lama disimpan apa adanya di
	old_finger_id untuk arsip; Employee tanpa finger_id cukup dibuatkan yang baru.

	Hanya sekali jalan: ditolak kalau sudah ada Employee yang punya old_finger_id,
	karena menjalankan ulang akan menimpa arsip dengan ID acak sebelumnya. Satu
	employee saja tetap bisa lewat 'nama' — dilewati kalau old_finger_id-nya sudah
	terisi.

	Jalankan sesudah migrate (old_finger_id dibuat oleh sync customization).

	    bench --site <site> execute sth.patches.ganti_finger_id_acak.execute
	    bench --site <site> execute sth.patches.ganti_finger_id_acak.execute \\
	        --kwargs "{'terapkan': 1}"
	    bench --site <site> execute sth.patches.ganti_finger_id_acak.execute \\
	        --kwargs "{'terapkan': 1, 'nama': '3174033105930004'}"

	Setelah diterapkan, ID baru harus didaftarkan ulang di mesin. Sementara itu log
	mesin yang masih membawa ID lama tetap dicocokkan lewat old_finger_id.
	"""
	terapkan = cint(terapkan)
	print("Mode {0}\n".format("TERAPKAN" if terapkan else "LAPORAN SAJA"))

	if not frappe.db.has_column("Employee", "old_finger_id"):
		print("Kolom old_finger_id belum ada — jalankan bench migrate dulu")
		return

	filters = {}
	if nama:
		filters["name"] = nama
	elif frappe.db.exists("Employee", {"old_finger_id": ("is", "set")}):
		print("Sudah pernah diterapkan: ada Employee yang punya old_finger_id. Batal.")
		return

	employees = frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name", "employee_name", "status", "finger_id", "old_finger_id"],
		order_by="name",
	)

	sudah_dipakai = set()
	diganti = 0
	for emp in employees:
		if emp.old_finger_id:
			print("{0}: dilewati, old_finger_id sudah {1}".format(emp.name, emp.old_finger_id))
			continue

		baru = buat_finger_id(sudah_dipakai)
		diganti += 1
		if diganti <= 20:
			print("{0} {1} ({2}): {3} -> {4}".format(
				emp.name, emp.employee_name, emp.status, emp.finger_id or "-", baru
			))

		if terapkan:
			frappe.db.set_value(
				"Employee", emp.name,
				{"finger_id": baru, "old_finger_id": emp.finger_id or None},
				update_modified=False,
			)

	if diganti > 20:
		print("... dan {0} lainnya".format(diganti - 20))

	print("\n{0} Employee {1}".format(diganti, "diganti" if terapkan else "akan diganti"))
	if terapkan:
		frappe.db.commit()
