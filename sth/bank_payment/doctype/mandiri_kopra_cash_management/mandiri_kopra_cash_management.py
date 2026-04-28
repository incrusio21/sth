# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt
import os
import io
import time
import pandas as pd
from openpyxl import load_workbook

import gnupg
import paramiko

import frappe
from frappe.model.document import Document
from frappe.model.naming import parse_naming_series
from frappe.utils import format_date

from sth.utils import generate_duplicate_key

from sth.bank_payment.doctype.mandiri_kopra_cash_management import kcm_template

template_function = {
	"MCM_SingleMix": kcm_template.mtfu_separated
}

class MandiriKopraCashManagement(Document):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._extension_name = ".txt"

	def autoname(self):
		company_alias = frappe.get_cached_value("Mandiri Public Key", self.public_key, "mft_server")
		path_alias = frappe.get_cached_value("Kopra File Path", self.path, "naming_path")
		date_naming = format_date(self.posting_date, "ddmmyyyy")

		self.naming_series = f"{company_alias}{path_alias}{date_naming}.######"
		
		parts = self.series.split(".")
		self.name = parse_naming_series(parts)

	def before_submit(self):
		for d in self.items:
			generate_duplicate_key(d, "duplicate_key", [self.voucher_type, self.voucher_no])

	def on_submit(self):
		self.update_payment_entry_status()
		self.upload_mft_file()

	def before_cancel(self):
		for d in self.items:
			generate_duplicate_key(d, "duplicate_key", cancel=1)

	def on_cancel(self):
		self.update_payment_entry_status()

	def update_payment_entry_status(self):
		pass

	def upload_mft_file(self):
		# 1. Buat konten TXT di memori
		content = self.create_content()
		# print("CONTENT RAW:", content)

		mpk = frappe.get_value("Mandiri Public Key", self.public_key, ["recipient_email", "public_key"], as_dict=1)

		if mpk.public_key:
			# 2. Enkripsi ke PGP di memori
			content = self.encrypt_in_memory(content, mpk.public_key, mpk.recipient_email)
			# print("TYPE:", type(content))
			self._extension_name = ".pgp"
		
		self.upload_to_sftp(content)

	def create_content(self):
		if not template_function.get(self.path):
			frappe.throw(f"{self.path} doesn't have Template")
		
		return template_function[self.path](self)

	def encrypt_in_memory(self, content, public_key, recipient_email):
		gpg = gnupg.GPG()
		gpg.encoding = "utf-8"

		
		gpg.import_keys(public_key)
		
		# ✅ gpg.encrypt() langsung menerima string — tidak perlu io.BytesIO
		encrypted = gpg.encrypt(
			content,
			recipients=[recipient_email],
			always_trust=True,  # percaya key tanpa konfirmasi manual
			armor=True,         # output format ASCII .pgp
		)

		if not encrypted.ok:
			frappe.throw(f"Status : {encrypted.status} Stderr : {encrypted.stderr}")

		return encrypted.data  # bytes hasil enkripsi
	
	def upload_to_sftp(self, data) -> None:
		ssh = ssh_connect(self.mft_server)
		
		if not ssh:
			frappe.throw(f"Gagal konek ke MFT server: {self.mft_server}")
		
		path = f"/Upload/Users/{self.path}"
		try:
			with ssh.open_sftp() as sftp:
				try:
					sftp.stat(path)
				except FileNotFoundError:
					frappe.throw(f"Folder {path} Not Found")

				print("BEFORE UPLOAD:", sftp.listdir(path))
				remote_path = f"{path}/{self.name}{self._extension_name}"
				
				# with sftp.open(remote_path, 'wb') as remote_file:
				# 	remote_file.set_pipelined(True)
				# 	remote_file.write(data)

				with ssh.open_sftp() as sftp:

					print("CHECK /Upload:", sftp.listdir("/Upload"))
					print("CHECK /Upload/Users:", sftp.listdir("/Upload/Users"))
					print("CHECK TARGET:", sftp.listdir(path))

					remote_path = f"{path}/{self.name}{self._extension_name}"
					print("UPLOAD TO:", remote_path)

					with sftp.open(remote_path, 'wb') as f:
						f.write(data)
						f.flush()

					time.sleep(2)

					try:
						print("AFTER:", sftp.listdir(path))
						print("SIZE:", sftp.stat(remote_path).st_size)
					except Exception as e:
						print("ERROR:", str(e))
				
				print("AFTER UPLOAD:", sftp.listdir(path))
		finally:
			ssh.close()  # ✅ selalu dieksekusi meski frappe.throw() dipanggil

def ssh_connect(sftp_server):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

	connect_kwargs = frappe.get_value("Mandiri MFT", sftp_server, 
		["hostname", "port", "username", "password"], 
		as_dict=1
	)

	# return ssh.connect(**connect_kwargs)
	ssh.connect(**connect_kwargs)

	return ssh


def get_payment_status():
	import io

	print("=== MASUK FUNCTION get_payment_status ===")

	progress_payment = frappe.get_all(
		"Mandiri Kopra Cash Management",
		filters={"status": "In Progress"},
		fields=["name", "mft_server"]
	)

	print("DATA progress_payment:", progress_payment)

	if not progress_payment:
		print("TIDAK ADA DATA")
		return

	mft_server = {}
	for kcm in progress_payment:
		print(f"Mapping KCM: {kcm.name} -> {kcm.mft_server}")
		mft_server.setdefault(kcm.mft_server, []).append(kcm.name)

	print("MFT SERVER RESULT:", mft_server)

	if not mft_server:
		print("mft_server kosong")
		return

	kcm_to_update = {}
	remote_dir = '/Downloads/Unread Files'

	for server, kcm_names in mft_server.items():
		print(f"\n=== CONNECT KE SERVER: {server} ===")

		ssh = None

		try:
			ssh = ssh_connect(server)

			if not ssh:
				print(f"SSH RETURN NONE: {server}")
				continue

			print("SSH CONNECTED:", server)

		except Exception as e:
			print("SSH ERROR:", e)
			continue

		try:
			with ssh.open_sftp() as sftp:
				print("OPEN SFTP SUCCESS")

				try:
					files = sftp.listdir(remote_dir)
					print(f"FILES di {remote_dir}: {files}")
				except Exception as e:
					print("ERROR LISTDIR:", e)
					continue

				for kcm_name in kcm_names:
					print(f"\nCEK FILE UNTUK: {kcm_name}")

					matched_file = None

					for file in files:
						print(f"   - compare: {file}")
						if file.startswith(kcm_name) and file.endswith(('.ack', '.nack')):
							matched_file = file
							break

					if not matched_file:
						print(f"TIDAK KETEMU FILE untuk {kcm_name}")
						continue

					print(f"KETEMU FILE: {matched_file}")

					remote_path = f"{remote_dir}/{matched_file}"
					print(f"DOWNLOAD: {remote_path}")

					try:
						buffer = io.BytesIO()
						sftp.getfo(remote_path, buffer)
						buffer.seek(0)
						data = buffer.read()
					except Exception as e:
						print("ERROR DOWNLOAD FILE:", e)
						continue

					try:
						decoded = data.decode("utf-8", errors="ignore")
					except Exception as e:
						print("ERROR DECODE:", e)
						decoded = str(data)

					print(f"\n===== BANK RESPONSE =====")
					print(f"{kcm_name}")
					print(decoded)
					print(f"========================\n")

					kcm_to_update[kcm_name] = {
						"status": "Completed" if matched_file.endswith(".ack") else "Error",
						"callback": decoded
					}

		finally:
			if ssh:
				print("🔌 CLOSE SSH:", server)
				ssh.close()

	# DEBUG sementara
	print("HASIL AKHIR:", kcm_to_update)

	# if not kcm_to_update:
	if True:
		print("TIDAK ADA DATA YANG DIUPDATE")
		return

	print("DATA YANG AKAN DIUPDATE:", kcm_to_update)

	status_update = ""
	callback_update = ""
	kcm_list = []

	for kcm_name, value in kcm_to_update.items():
		status_update += """ WHEN name = {} THEN {} """.format(
			frappe.db.escape(kcm_name),
			frappe.db.escape(value["status"]),
		)

		callback_update += """ WHEN name = {} THEN {} """.format(
			frappe.db.escape(kcm_name),
			frappe.db.escape(value["callback"]),
		)

		kcm_list.append(kcm_name)

	print("KCM LIST:", kcm_list)

	frappe.db.sql(
		f"""
		UPDATE `tabMandiri Kopra Cash Management`
		SET
			status = CASE {status_update} END,
			callback = CASE {callback_update} END
		WHERE
			name in %(kcm)s
		""",
		{"kcm": kcm_list}
	)

	print("UPDATE DATABASE SELESAI")

# def get_payment_status():
# 	progress_payment = frappe.get_all("Mandiri Kopra Cash Management", filters={"docstatus": 1, "status": "In Progress"}, fields=["name", "mft_server"])

# 	mft_server = {}
# 	for kcm in progress_payment:
# 		mft = mft_server.setdefault(kcm.mft_server, [])
# 		mft.append(kcm.name)

# 	kcm_to_update = {}
# 	remote_dir = '/Downloads/Unread Files'
# 	for server, kcm in mft_server:
# 		ssh = ssh_connect(server)
		
# 	for kcm in progress_payment:
		
# 		try:
# 			with ssh.open_sftp() as sftp:
# 				files = sftp.listdir(remote_dir)

# 				matched_file = None
# 				for file in files:
# 					if file.startswith(kcm.name) and file.endswith(('.ack', '.nack')):
# 						matched_file = file
# 						break
				
# 				if matched_file:
# 					remote_path = f"{remote_dir}/{matched_file}"

# 					buffer = io.BytesIO()
# 					sftp.getfo(remote_path, buffer)
# 					buffer.seek(0)
# 					data = buffer.read()

# 					decoded = data.decode("utf-8", errors="ignore")

# 					print(f"{kcm.name} => {decoded}")

# 					kcm_to_update[kcm.name] = {
# 						"status": "Completed" if matched_file.endswith(".ack") else "Error",
# 						"callback": data
# 					}
# 		finally:
# 			ssh.close()  # ✅ selalu dieksekusi meski frappe.throw() dipanggil

# 	if not kcm_to_update:
# 		return
	
# 	status_update = callback_update = ""
# 	kcm_list = []
# 	for kcm_name, value in kcm_to_update.items():
# 		status_update += """ WHEN name = {} THEN {}
# 			""".format(
# 			frappe.db.escape(kcm_name),
# 			value.status,
# 		)
		
# 		callback_update += """ WHEN name = {} THEN {}
# 			""".format(
# 			frappe.db.escape(kcm_name),
# 			value.status,
# 		)

# 		kcm_list.append(kcm_name)
		
# 	frappe.db.sql(
# 		f""" UPDATE `tabMandiri Kopra Cash Management`
# 		SET
# 			status = CASE {status_update} END,
# 			callback = CASE {callback_update} END
# 		WHERE
# 			name in %(kcm)s """,
# 		{"kcm": kcm_list}
# 	)

def test():
    print("STEP 1")

    doc = frappe.get_doc("Mandiri Kopra Cash Management", "TMTL0011522042026000006")
    print("STEP 2")

    doc.upload_mft_file()
    print("STEP 3 DONE")