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

# def ssh_connect(sftp_server):
# 	ssh = paramiko.SSHClient()
# 	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# 	connect_kwargs = frappe.get_value("Mandiri MFT", sftp_server, 
# 		["hostname", "port", "username", "password"], 
# 		as_dict=1
# 	)

# 	# return ssh.connect(**connect_kwargs)
# 	ssh.connect(**connect_kwargs)

# 	return ssh


def ssh_connect(sftp_server, hostname_override=None):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

	connect_kwargs = frappe.get_value(
			"Mandiri MFT", sftp_server,
			["hostname", "port", "username", "password"],
			as_dict=1
	)

	if hostname_override:
			connect_kwargs.hostname = hostname_override

	ssh.connect(**connect_kwargs)

	return ssh



@frappe.whitelist()
def process_mt940_pending_release():
    payment_entries = frappe.get_all(
        "Payment Entry",
        filters={
            "docstatus": 0,
            "workflow_state": "Pending Release",
            "payment_status": "Pending Approval",
        },
        fields=["name", "kcm_reference"]
    )

    results = []

    for row in payment_entries:
        try:
            if not row.kcm_reference:
                continue

            kcm_status = frappe.db.get_value(
                "Mandiri Kopra Cash Management",
                row.kcm_reference,
                "payment_status"
            )

            if kcm_status != "Success":
                continue

            pe = frappe.get_doc("Payment Entry", row.name)

            preview = preview_mt940_payment_entry(pe.name)

            if not preview.get("bank_payment"):
                continue

            if abs(preview["difference"]) > 0.01:
                continue

            account = frappe.db.get_value(
                "Bank Admin Charges Account",
                {"company": pe.company},
                "account"
            )

            if not account:
                continue

            cost_center = frappe.db.get_value(
                "Company", pe.company, "cost_center"
            )

            for fee in preview.get("bank_fees", []):
                description = fee["narrative"].strip()

                exists = any(
                    tax.account_head == account
                    and tax.description == description
                    and abs((tax.tax_amount or 0) - fee["amount"]) < 0.01
                    for tax in pe.taxes
                )

                if exists:
                    continue

                pe.append("taxes", {
                    "charge_type": "Actual",
                    "add_deduct_tax": "Add",
                    "account_head": account,
                    "description": description,
                    "cost_center": cost_center,
                    "tax_amount": fee["amount"],
                    "included_in_paid_amount": 0
                })

            if preview.get("bank_fees"):
                pe.calculate_taxes()

            # pe.workflow_state = "Approved"
            pe.submit()

            frappe.db.set_value(
                "Payment Entry",
                pe.name,
                "payment_status",
                "Success"
            )

            results.append({
                "payment_entry": pe.name,
                "status": "Success"
            })

        except Exception as e:
            results.append({
                "payment_entry": row.name,
                "status": "Failed",
                "error": str(e)
            })

    return results



@frappe.whitelist()
def get_payment_status():

	process_mt940_pending_release()
	
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
				filters={"parent": kcm_name},
				fields=["idx", "payment_entry"],
				order_by="idx asc"
			)
		)

		payment_entries.extend(
			frappe.get_all(
				"Mandiri Kopra Cash Bill Detail",
				filters={"parent": kcm_name},
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
					responses.append(f"ERROR;{parts[error_idx + 1]}")
				else:
					responses.append("ERROR")

		for idx, pe in enumerate(payment_entries):

			if not pe.payment_entry:
				continue

			kcm_response = ""

			if idx < len(responses):
				kcm_response = responses[idx]

			# Status internal Payment Entry
			# if val["payment_status"] == "Success":
			# 	payment_entry_status = "Pending Approval"
			# else:
			# 	payment_entry_status = val["payment_status"]

			# frappe.db.set_value(
			# 	"Payment Entry",
			# 	pe.payment_entry,
			# 	{
			# 		"payment_status": payment_entry_status,
			# 		"kcm_response": kcm_response
			# 	}
			# )

			# Status internal Payment Entry
			if val["payment_status"] == "Success":
				payment_entry_status = "Pending Approval"
			else:
				payment_entry_status = "Failed"

			update_values = {
				"payment_status": payment_entry_status,
				"kcm_response": kcm_response
			}

			# Jika NACK atau Timeout, kembalikan workflow ke state sebelumnya
			if val["payment_status"] == "Failed":
				previous_workflow_state = frappe.db.get_value(
					"Payment Entry",
					pe.payment_entry,
					"kcm_previous_workflow_state"
				)

				if previous_workflow_state:
					update_values["workflow_state"] = previous_workflow_state

			frappe.db.set_value(
				"Payment Entry",
				pe.payment_entry,
				update_values
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
	doc = frappe.get_doc("Mandiri Kopra Cash Management", "TMTL0011507082026000011")
	content = doc.create_content()
	print(str(content))


@frappe.whitelist()
def generate_mft_file(kcm_name):
	import os

	# Fungsi untuk generate ulang file TXT dan PGP
	# bila pihak Mandiri meminta file untuk pengecekan
	# bench execute sth.bank_payment.doctype.mandiri_kopra_cash_management.mandiri_kopra_cash_management.generate_mft_file --kwargs "{'kcm_name':'TMTL0011531072026000004'}"
	doc = frappe.get_doc("Mandiri Kopra Cash Management", kcm_name)

	folder = os.path.dirname(os.path.abspath(__file__))

	# ==========================
	# Generate Plain TXT
	# ==========================
	plain_content = doc.create_content()

	txt_path = os.path.join(folder, f"{doc.name}.txt")
	with open(txt_path, "w", encoding="utf-8") as f:
		f.write(plain_content)

	# ==========================
	# Generate PGP
	# ==========================
	pgp_path = None

	mpk = frappe.get_value(
		"Mandiri Public Key",
		doc.public_key,
		["recipient_email", "public_key"],
		as_dict=1
	)

	if mpk and mpk.public_key:
		encrypted_content = doc.encrypt_in_memory(
			plain_content,
			mpk.public_key,
			mpk.recipient_email
		)

		pgp_path = os.path.join(folder, f"{doc.name}.pgp")

		with open(pgp_path, "wb") as f:
			f.write(encrypted_content)

	frappe.msgprint(
		f"""
		TXT : {txt_path}<br>
		PGP : {pgp_path or 'Public Key tidak tersedia'}
		"""
	)

	return {
		"txt": txt_path,
		"pgp": pgp_path
	}



@frappe.whitelist()
def get_mandiri_mt940_files():
    server = "TMTL001"
    remote_dir = "/My Subscriptions/TMTL001#AccountStatement"
    cutoff = time.time() - (7 * 24 * 60 * 60)

    ssh = None
    result = []

    try:
        ssh = ssh_connect(server)

        with ssh.open_sftp() as sftp:
            files = sftp.listdir_attr(remote_dir)

            for file in files:
                if file.st_mtime < cutoff:
                    continue

                if not file.st_mode or not __import__("stat").S_ISREG(file.st_mode):
                    continue

                result.append({
                    "file_name": file.filename,
                    "size": file.st_size,
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(file.st_mtime)
                    )
                })

        result.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "server": server,
            "folder": remote_dir,
            "total_files": len(result),
            "files": result
        }

    finally:
        if ssh:
            ssh.close()



@frappe.whitelist()
def read_mandiri_mt940_files():
    server = "TMTL001"
    remote_dir = "/My Subscriptions/TMTL001#AccountStatement"
    cutoff = time.time() - (7 * 24 * 60 * 60)

    ssh = None
    result = []

    try:
        ssh = ssh_connect(server, "103.139.82.26")

        with ssh.open_sftp() as sftp:
            files = sftp.listdir_attr(remote_dir)

            for file in files:
                if file.st_mtime < cutoff:
                    continue

                if not file.st_mode or not __import__("stat").S_ISREG(file.st_mode):
                    continue

                remote_path = f"{remote_dir}/{file.filename}"

                with sftp.open(remote_path, "rb") as remote_file:
                    content = remote_file.read().decode("utf-8", errors="replace")

                result.append({
                    "file_name": file.filename,
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(file.st_mtime)
                    ),
                    "content": content
                })

        result.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "total_files": len(result),
            "files": result
        }

    finally:
        if ssh:
            ssh.close()


def parse_mandiri_mt940_files():
    data = read_mandiri_mt940_files()
    transactions = []

    for file_data in data.get("files", []):
        current = None

        for line in file_data.get("content", "").splitlines():
            line = line.strip()

            if line.startswith(":61:"):
                if current:
                    transactions.append(current)

                raw = line[4:]
                match = __import__("re").match(
                    r"^(\d{6})(?:\d{4})?([DC])([\d,]+)([A-Z]{4})?",
                    raw
                )

                if not match:
                    current = None
                    continue

                date, direction, amount, transaction_type = match.groups()

                current = {
                    "file_name": file_data["file_name"],
                    "date": "20" + date[:2] + "-" + date[2:4] + "-" + date[4:6],
                    "direction": direction,
                    "amount": float(amount.replace(",", ".")),
                    "transaction_type": transaction_type or "",
                    "narrative": "",
                    "raw_61": line,
                }

            elif line.startswith(":86:") and current:
                current["narrative"] = line[4:].strip()

            elif current and line and not line.startswith(":"):
                current["narrative"] += " " + line

        if current:
            transactions.append(current)

    return transactions


@frappe.whitelist()
def preview_mt940_payment_entry(payment_entry):
    pe = frappe.get_doc("Payment Entry", payment_entry)

    transactions = parse_mandiri_mt940_files()
    matched = []

    for tx in transactions:
        if tx["direction"] != "D":
            continue

        if payment_entry not in tx["narrative"]:
            continue

        matched.append(tx)

    payment = next(
        (
            tx for tx in matched
            if "Fee" not in tx["narrative"]
            and "Charge" not in tx["narrative"]
        ),
        None
    )

    fees = [
        tx for tx in matched
        if any(
            keyword in tx["narrative"].lower()
            for keyword in ("fee", "charge")
        )
    ]

    return {
        "payment_entry": payment_entry,
        "company": pe.company,
        "paid_amount": pe.paid_amount,
        "bank_payment": payment,
        "difference": (
            round(pe.paid_amount - payment["amount"], 2)
            if payment else None
        ),
        "bank_fees": fees,
        "total_bank_fees": sum(tx["amount"] for tx in fees),
    }


@frappe.whitelist()
def apply_mt940_bank_fees(payment_entry):
    pe = frappe.get_doc("Payment Entry", payment_entry)

    if pe.docstatus != 0:
        frappe.throw("Payment Entry harus berstatus Draft.")

    preview = preview_mt940_payment_entry(payment_entry)

    if not preview.get("bank_payment"):
        frappe.throw("Transaksi pembayaran tidak ditemukan.")

    if abs(preview["difference"]) > 0.01:
        frappe.throw("Nominal rekening koran tidak cocok.")

    if not preview.get("bank_fees"):
        frappe.throw("Biaya bank tidak ditemukan.")

    account = frappe.db.get_value(
        "Bank Admin Charges Account",
        {"company": pe.company},
        "account"
    )

    if not account:
        frappe.throw("Akun Bank Admin Charges belum dikonfigurasi.")

    cost_center = frappe.db.get_value(
        "Company", pe.company, "cost_center"
    )

    for fee in preview["bank_fees"]:
        description = fee["narrative"].strip()

        exists = any(
            row.account_head == account
            and row.description == description
            and abs((row.tax_amount or 0) - fee["amount"]) < 0.01
            for row in pe.taxes
        )

        if exists:
            continue

        pe.append("taxes", {
            "charge_type": "Actual",
            "add_deduct_tax": "Add",
            "account_head": account,
            "description": description,
            "cost_center": cost_center,
            "tax_amount": fee["amount"],
            "included_in_paid_amount": 0
        })

    pe.calculate_taxes()
    pe.save()

    return {
        "payment_entry": pe.name,
        "taxes": [
            {
                "description": row.description,
                "account_head": row.account_head,
                "tax_amount": row.tax_amount,
                "cost_center": row.cost_center
            }
            for row in pe.taxes
        ],
        "paid_amount": pe.paid_amount,
        "docstatus": pe.docstatus
    }



def reset_pe_for_mt940_test():
    pe_name = "ACC-PAY-2026-00341"
    kcm_name = "TMTL0011509112026000001"

    pe = frappe.get_doc("Payment Entry", pe_name)

    if pe.docstatus != 1:
        frappe.throw("Payment Entry harus berstatus Submitted.")

    if pe.kcm_reference != kcm_name:
        frappe.throw("Referensi KCM tidak sesuai.")

    kcm_status = frappe.db.get_value(
        "Mandiri Kopra Cash Management",
        kcm_name,
        "payment_status",
    )

    if kcm_status != "Success":
        frappe.throw("KCM harus berstatus Success.")

    frappe.db.savepoint("before_pe_repair")

    try:
        # Hapus GL Entry
        frappe.db.sql("""
            DELETE FROM `tabGL Entry`
            WHERE voucher_type = 'Payment Entry'
              AND voucher_no = %s
        """, pe_name)

        # Hapus Payment Ledger Entry
        frappe.db.sql("""
            DELETE FROM `tabPayment Ledger Entry`
            WHERE voucher_type = 'Payment Entry'
              AND voucher_no = %s
        """, pe_name)

        # Kembalikan PE menjadi Draft
        frappe.db.sql("""
            UPDATE `tabPayment Entry`
            SET docstatus = 0,
                status = 'Draft',
                workflow_state = 'Pending Release'
            WHERE name = %s
        """, pe_name)

        frappe.clear_document_cache("Payment Entry", pe_name)

        return {
            "payment_entry": pe_name,
            "docstatus": 0,
            "workflow_state": "Pending Release",
            "gl_deleted": True,
            "payment_ledger_deleted": True,
            "kcm_status": kcm_status,
        }

    except Exception:
        frappe.db.rollback(save_point="before_pe_repair")
        raise