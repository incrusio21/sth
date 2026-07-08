# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt
import os
import io,time
import pandas as pd
from openpyxl import load_workbook

import gnupg
import paramiko

import frappe
from frappe.model.document import Document
from frappe.model.naming import parse_naming_series
from frappe.utils import format_date
from frappe.utils import now_datetime
from datetime import timedelta

from sth.utils import generate_duplicate_key

from sth.bank_payment.doctype.mandiri_kopra_cash_management import kcm_template

template_function = {
	"MCM_SingleMix": kcm_template.mtfu_separated,
	"MCM_BatchUpload": kcm_template.mtfu_consolidated,
	"MCM_BillPaymentSingle": kcm_template.mtfu_bill_separated,
	"MCM_PayrollMix": kcm_template.mtfu_payroll
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
		
		parts = self.naming_series.split(".")
		self.name = parse_naming_series(parts)

	# def before_submit(self):
	# 	for d in self.items:
	# 		generate_duplicate_key(d, "duplicate_key", [self.voucher_type, self.voucher_no])

	def on_submit(self):
		self.update_payment_entry_status()
		self.upload_mft_file()

	def validate(self):
		if self.is_new():
			self.raw_response = None
			self.payment_status = "In Progress"

		if self.path not in template_function:
			frappe.msgprint(f"Path {self.path} belum ada templatenya")

		if self.path == "MCM_BatchUpload":
			debit_accounts = {d.debit_account for d in self.detail if d.debit_account}

			if len(debit_accounts) > 1:
				frappe.msgprint("Batch Upload (Consolidated) hanya boleh 1 debit account")

		# content = self.create_content()
		# self.raw_content = content

	# def before_cancel(self):
	# 	for d in self.items:
	# 		generate_duplicate_key(d, "duplicate_key", cancel=1)

	def on_cancel(self):
		self.update_payment_entry_status()

	def update_payment_entry_status(self):
		pass

	def upload_mft_file(self):
		# 1. Buat konten TXT di memori
		content = self.create_content()
		print("CONTENT RAW:", content[:100])
		# self.raw_content = content

		mpk = frappe.get_value("Mandiri Public Key", self.public_key, ["recipient_email", "public_key"], as_dict=1)

		if mpk.public_key:
			# 2. Enkripsi ke PGP di memori
			content = self.encrypt_in_memory(content, mpk.public_key, mpk.recipient_email)
			print("TYPE:", type(content))
			print("AFTER ENCRYPT SAMPLE:", content[:100]) 
			self.raw_content = content
			self._extension_name = ".pgp"
		
		self.upload_to_sftp(content)

	def create_content(self):

		if self.test_request:
			return self.test_request
		
		if not template_function.get(self.path):
			frappe.msgprint(f"{self.path} doesn't have Template")
		
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
			frappe.msgprint(f"Status : {encrypted.status} Stderr : {encrypted.stderr}")

		return encrypted.data  # bytes hasil enkripsi
	
	# def upload_to_sftp(self, data) -> None:
	# 	ssh = ssh_connect(self.mft_server)
		
	# 	if not ssh:
	# 		frappe.throw(f"Gagal konek ke MFT server: {self.mft_server}")
		
	# 	path = f"Upload/Users/{self.path}"
	# 	try:
	# 		with ssh.open_sftp() as sftp:
	# 			try:
	# 				sftp.stat(path)
	# 			except FileNotFoundError:
	# 				frappe.throw(f"Folder {path} Not Found")

	# 			remote_path = f"{path}/{self.name}{self._extension_name}"
	# 			with sftp.open(remote_path, 'wb') as remote_file:
	# 				remote_file.set_pipelined(True)
	# 				remote_file.write(data)
	# 	finally:
	# 		ssh.close()  # ✅ selalu dieksekusi meski frappe.throw() dipanggil

	def upload_to_sftp(self, data) -> None:
		ssh = ssh_connect(self.mft_server)

		if not ssh:
			frappe.msgprint(f"Gagal konek ke MFT server: {self.mft_server}")

		path = f"Upload/Users/{self.path}"
		remote_path = f"{path}/{self.name}{self._extension_name}"

		try:
			with ssh.open_sftp() as sftp:
				f = sftp.open(remote_path, 'wb')
				f.write(data)
				f.flush()
				f.close()
		finally:
			ssh.close()

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

@frappe.whitelist()
def get_payment_status():
	
	progress_payment = frappe.get_all(
		"Mandiri Kopra Cash Management",
		filters={
			"payment_status": "In Progress",
			"docstatus": 1,
		},
		fields=["name", "mft_server", "creation"]
	)

	if not progress_payment:
		return

	mft_server = {}
	for row in progress_payment:
		mft_server.setdefault(row.mft_server, []).append(row)

	kcm_to_update = {}

	dirs = [
		"/Downloads/Unread Files",
		"/Downloads/Read Files",
		"/Downloads"
	]

	for server, rows in mft_server.items():
		ssh = None

		try:
			ssh = ssh_connect(server)
			if not ssh:
				continue

			with ssh.open_sftp() as sftp:

				for remote_dir in dirs:
					try:
						files = sftp.listdir(remote_dir)
					except:
						continue

					for file in files:

						if not (file.endswith(".ack") or file.endswith(".nack")):
							continue

						for row in rows:
							kcm_name = row.name

							if kcm_name in kcm_to_update:
								continue

							if not file.startswith(kcm_name):
								continue

							remote_path = f"{remote_dir}/{file}"

							try:
								buffer = io.BytesIO()
								sftp.getfo(remote_path, buffer)
								buffer.seek(0)
								data = buffer.read()
							except:
								continue

							try:
								decoded = data.decode("utf-8", errors="ignore")
							except:
								decoded = str(data)

							status = "Success" if file.endswith(".ack") else "Failed"

							kcm_to_update[kcm_name] = {
								"payment_status": status,
								"raw_response": decoded
							}

		finally:
			if ssh:
				ssh.close()

	now = now_datetime()

	for rows in mft_server.values():
		for row in rows:
			if row.name in kcm_to_update:
				continue

			created_time = row.creation
			if created_time and (now - created_time) > timedelta(minutes=30):
				kcm_to_update[row.name] = {
					"payment_status": "Failed",
					"raw_response": "Timeout: No response from bank after 30 minutes"
				}

	# ==============================

	if not kcm_to_update:
		return

	status_case = ""
	response_case = ""
	kcm_list = []

	for name, val in kcm_to_update.items():
		status_case += f" WHEN name = {frappe.db.escape(name)} THEN {frappe.db.escape(val['payment_status'])} "
		response_case += f" WHEN name = {frappe.db.escape(name)} THEN {frappe.db.escape(val['raw_response'])} "
		kcm_list.append(name)

	frappe.db.sql(f"""
		UPDATE `tabMandiri Kopra Cash Management`
		SET
			payment_status = CASE {status_case} END,
			raw_response = CASE {response_case} END
		WHERE name in %(kcm)s
	""", {"kcm": kcm_list})

	# # UPDATE PAYMENT ENTRY STATUS
	# for kcm_name, val in kcm_to_update.items():

	# 	payment_entries = frappe.get_all(
	# 		"Mandiri Kopra Detail",
	# 		filters={
	# 			"parent": kcm_name
	# 		},
	# 		fields=["payment_entry"]
	# 	)

	# 	for pe in payment_entries:

	# 		if pe.payment_entry:

	# 			frappe.db.set_value(
	# 				"Payment Entry",
	# 				pe.payment_entry,
	# 				"payment_status",
	# 				val["payment_status"]
	# 			)

	# UPDATE PAYMENT ENTRY STATUS
	for kcm_name, val in kcm_to_update.items():

		payment_entries = []

		payment_entries.extend(
			frappe.get_all(
				"Mandiri Kopra Detail",
				filters={
					"parent": kcm_name
				},
				fields=["idx", "payment_entry"],
				order_by="idx asc"
			)
		)

		payment_entries.extend(
			frappe.get_all(
				"Mandiri Kopra Cash Bill Detail",
				filters={
					"parent": kcm_name
				},
				fields=["idx", "payment_entry"],
				order_by="idx asc"
			)
		)

		payment_entries = sorted(payment_entries, key=lambda x: x.idx)

		responses = []

		for line in val.get("raw_response", "").splitlines():
			line = line.strip()

			if not line:
				continue

			delimiter = ";" if ";" in line else ","

			parts = [p.strip() for p in line.split(delimiter)]

			if "SUCCESS" in parts:
				responses.append("SUCCESS")

			elif "ERROR" in parts:
				error_idx = parts.index("ERROR")

				if error_idx + 1 < len(parts) and parts[error_idx + 1]:
					responses.append(
						f"ERROR;{parts[error_idx + 1]}"
					)
				else:
					responses.append("ERROR")

		for idx, pe in enumerate(payment_entries):

			if not pe.payment_entry:
				continue

			kcm_response = ""

			if idx < len(responses):
				kcm_response = responses[idx]

			frappe.db.set_value(
				"Payment Entry",
				pe.payment_entry,
				{
					"payment_status": val["payment_status"],
					"kcm_response": kcm_response
				}
			)

@frappe.whitelist()
def get_payment_entry_details(payment_entry):
    if not payment_entry:
        return {}

    pe = frappe.get_doc("Payment Entry", payment_entry)

    debit_account_number = frappe.db.get_value(
        "Bank Account",
        {"account": pe.paid_from},
        "bank_account_no"
    )

    beneficiary_data = frappe.db.get_value(
        "Bank Account",
        {"account": pe.paid_to},
        ["bank_account_no", "account_name"],
        as_dict=1
    )

    beneficiary_account_number = (
        pe.no_rekening_tujuan
        or (beneficiary_data.get("bank_account_no") if beneficiary_data else None)
    )

    beneficiary_name = (
        beneficiary_data.get("account_name")
        if beneficiary_data else None
    )

    return {
        "paid_from": pe.paid_from,
        "paid_to": pe.paid_to,
        "debit_account": pe.no_rekening or debit_account_number,
        "beneficiary_account": beneficiary_account_number,
        "beneficiary_name": beneficiary_name,
        "currency": pe.paid_from_account_currency,
        "amount": pe.paid_amount,
        "customer_reference": pe.reference_no,
        "remarks": pe.remarks
    }

def test():
	doc = frappe.get_doc("Mandiri Kopra Cash Management", "TMTL0011404052026000006")
	content = doc.create_content()
	print(content)