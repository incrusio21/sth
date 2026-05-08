import frappe
import csv
import os

def run():
	csv_path = os.path.join(os.path.dirname(__file__), "hasil_data_with_ktp.csv")

	success = []
	failed = []

	with open(csv_path, newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			old_name = row['NIP'].strip()
			new_name = row['No KTP'].strip()
			nama = row['Nama Lengkap'].strip()

			if not old_name or not new_name:
				failed.append((old_name, new_name, nama, "NIP or No KTP kosong"))
				continue

			try:
				# Cek apakah employee dengan NIP ini ada
				if not frappe.db.exists("Employee", old_name):
					failed.append((old_name, new_name, nama, "Employee tidak ditemukan"))
					continue

				# Cek apakah nama baru sudah dipakai
				if frappe.db.exists("Employee", new_name):
					failed.append((old_name, new_name, nama, f"No KTP {new_name} sudah ada di sistem"))
					continue

				frappe.rename_doc("Employee", old_name, new_name, force=True)
				success.append((old_name, new_name, nama))
				print(f"[OK]  {old_name} -> {new_name}  ({nama})")

			except Exception as e:
				failed.append((old_name, new_name, nama, str(e)))
				print(f"[FAIL] {old_name} -> {new_name}  ({nama}) | Error: {e}")

	print()
	print(f"=== SELESAI ===")
	print(f"Berhasil : {len(success)}")
	print(f"Gagal    : {len(failed)}")

	if failed:
		print()
		print("=== YANG GAGAL ===")
		for old, new, nama, reason in failed:
			print(f"  {old} -> {new} ({nama}) | {reason}")