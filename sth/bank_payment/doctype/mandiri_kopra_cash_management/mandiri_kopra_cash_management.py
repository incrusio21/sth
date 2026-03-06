# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt
import os
import io
import pandas as pd
from openpyxl import load_workbook

import gnupg
import paramiko

import frappe
from frappe.model.document import Document

from sth.utils import generate_duplicate_key

class MandiriKopraCashManagement(Document):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._extension_name = ".txt"

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

		mpk = frappe.get_value("Mandiri Public Key", self.public_key, ['mft_server', "recipient_email", "public_key"], as_dict=1)

		if mpk.public_key:
			# 2. Enkripsi ke PGP di memori
			content = self.encrypt_in_memory(content, mpk.public_key, mpk.recipient_email)
			self._extension_name += ".pgp"
		
		self.upload_to_sftp(content, mpk.mft_server)

	def create_content(self):
		content = """\
		M;1;;1;;;;1020011824312;1270014263220;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;IBU;;;;;;;Y;mco.phang@bankmandiri.co.id;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;E;Testing 1
		M;1;;2;;;;1020011824312;90340034508;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;BAU;2130101;SMBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 2
		M;2;20251217;3;;;;1020011824312;5470835321;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;OBU;0140397;BCA;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 3
		M;3;20251217;4;1;2;20260131;1020011824312;693814208833;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;LBU;0280024;OCBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 4
		"""

		return content

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
			frappe.trhow(f"Status : {encrypted.status} Stderr : {encrypted.stderr}")

		return encrypted.data  # bytes hasil enkripsi
	
	def upload_to_sftp(self, data, sftp_server) -> None:
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

		connect_kwargs = frappe.get_value("Mandiri MFT", sftp_server, 
			["hostname", "port", "username", "password"], 
			as_dict=1
		)

		ssh.connect(**connect_kwargs)

		path = f"Upload/Users/{self.path}"
		try:
			with ssh.open_sftp() as sftp:
				try:
					sftp.stat(path)
				except FileNotFoundError:
					frappe.throw(f"Folder {path} Not Found")

				remote_path = f"{path}/{self.name}{self._extension_name}"
				sftp.putfo(io.BytesIO(data), remote_path)
		finally:
			ssh.close()  # ✅ selalu dieksekusi meski frappe.throw() dipanggil