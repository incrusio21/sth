# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe


def get_komponen_pph21_ter(fieldname="pph21_ter_component"):
	"""Komponen PPh21 TER dipasang per Salary Structure, jadi namanya bisa berbeda-beda.

	Selalu mengembalikan list yang tidak kosong supaya aman dipakai di klausa IN.
	"""
	komponen = frappe.get_all(
		"Salary Structure",
		filters={fieldname: ["is", "set"]},
		pluck=fieldname,
	)

	return sorted(set(komponen)) or [""]


def get_komponen_pph21_ter_gross_up():
	return get_komponen_pph21_ter("pph21_ter_gross_up_component")
