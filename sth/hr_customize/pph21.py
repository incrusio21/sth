# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe


def get_komponen_pph21_ter(tipe="Deduction"):
	"""Komponen PPh21 TER dinamai sendiri-sendiri per Salary Structure, jadi dicari dari namanya.

	Potongan dan gross up dibedakan dari tipe komponen, karena
	'PPH21 TER Gross Up' ikut mengandung 'PPH21 TER'.

	Selalu mengembalikan list yang tidak kosong supaya aman dipakai di klausa IN.
	"""
	komponen = frappe.get_all(
		"Salary Component",
		filters={"name": ["like", "%PPH21 TER%"], "type": tipe},
		pluck="name",
	)

	return sorted(set(komponen)) or [""]


def get_komponen_pph21_ter_gross_up():
	return get_komponen_pph21_ter("Earning")
