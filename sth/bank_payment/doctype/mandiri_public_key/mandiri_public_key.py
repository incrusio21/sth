# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import gnupg
# import frappe

from frappe.model.document import Document


class MandiriPublicKey(Document):
	def validate(self):
		gpg = gnupg.GPG()

		gpg.import_keys(self.public_key)
		result = gpg.import_keys(self.public_key)
    
		# Ambil fingerprint dari hasil import
		fingerprint = result.fingerprints[0]
		
		# Gunakan fingerprint untuk ambil detail key
		keys = gpg.list_keys()
		for key in keys:
			if key["fingerprint"] == fingerprint:
				# uid formatnya: "Nama <email@example.com>"
				uid = key["uids"][0]  # contoh: "Raja Fitha Samudra <mco.phang@bankmandiri.co.id>"
				
				# Ekstrak email dari uid
				email = uid.split("<")[1].split(">")[0]  # → "mco.phang@bankmandiri.co.id"
				name  = uid.split("<")[0].strip()         # → "Raja Fitha Samudra"
				
				# Simpan ke field document (sesuaikan nama field di doctype)
				self.recipient_email = email
				self.recipient_name  = name
				self.fingerprint     = fingerprint
				
				break