# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from sth.hr_customize.doctype.daftar_bpjs.daftar_bpjs import samakan_komponen_dengan_master


class SetUpBPJSPT(Document):
	def on_update(self):
		"""Jalarkan perbaikan komponen ke dokumen yang sudah membekukan salinannya.

		Daftar BPJS menyalin komponen dari sini waktu divalidasi, lalu
		membekukannya ke Employee Payment Log waktu disubmit. Tanpa penjalaran di
		sini, membetulkan master tidak berpengaruh apa-apa pada periode yang
		daftarnya sudah disubmit — slip gajinya tetap memakai komponen lama,
		lengkap dengan akun lamanya.

		Yang sudah dipakai salary slip tersubmit tidak disentuh dan disebut di
		peringatan, karena mengubahnya berarti GL-nya tidak lagi cocok.
		"""
		hasil = samakan_komponen_dengan_master(self.name)

		if not (hasil["detail"] or hasil["log"] or hasil["log_terkunci"]):
			return

		pesan = [
			_("{0} baris Daftar BPJS dan {1} Employee Payment Log ikut disesuaikan.").format(
				hasil["detail"], hasil["log"]
			)
		]

		slip = sorted({nama for nama, _lama, _baru in hasil["slip_draft"]})
		if slip:
			pesan.append(
				_(
					"{0} Salary Slip draft masih memuat komponen lama: {1}. "
					"Jangan disimpan ulang — penyimpanan ulang menambah baris baru tanpa "
					"membuang yang lama. Jalankan patch "
					"<b>samakan_komponen_bpjs_dengan_master</b> untuk menggantinya di tempat."
				).format(len(slip), ", ".join(slip))
			)

		if hasil["log_terkunci"]:
			pesan.append(
				_(
					"{0} Employee Payment Log sudah dipakai salary slip tersubmit, jadi "
					"dibiarkan: {1}"
				).format(len(hasil["log_terkunci"]), ", ".join(hasil["log_terkunci"]))
			)

		frappe.msgprint(
			"<br><br>".join(pesan),
			title=_("Komponen BPJS Disesuaikan"),
			indicator="orange" if (hasil["log_terkunci"] or slip) else "green",
		)
