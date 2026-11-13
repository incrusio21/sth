# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime, timedelta

# def make_entry(self, method=None):
#     if self.payment_type not in ("Pay"):
#         return

#     mkcm = frappe.new_doc("Mandiri Kopra Cash Management")
#     mkcm.posting_date = self.request_release_date
#     mkcm.company = self.company
#     mkcm.status = "In Progress"
#     mkcm.public_key = ""
#     mkcm.path =  ""

#     mkcm.flags.ignore_permissions = 1
#     mkcm.flags.notify_update = False
#     mkcm.submit()

def set_requires_mandiri_kcm(doc, method=None):
    doc.requires_mandiri_kcm = int(
        doc.mode_of_payment == "Bank Draft"
        and doc.payment_type in ["Pay", "Internal Transfer"]
        and is_mandiri_kcm(doc.paid_from)
    )

def is_mandiri_kcm(account):

    if not account:
        return False

    bank_account = frappe.db.get_value(
        "Bank Account",
        {"account": account},
        ["bank", "intergrated_bank"],
        as_dict=True
    )

    if not bank_account:
        return False

    if not bank_account.intergrated_bank:
        return False

    if not bank_account.bank:
        return False

    return bool(
        frappe.db.get_value(
            "Bank",
            bank_account.bank,
            "is_mandiri_kca"
        )
    )


def get_mandiri_kcm_data(doc):

    FT_SERVICE_MAPPING = {
        "InHouse Transfer": "IBU",
        "LLG Domestic Transfer": "LBU",
        "RTGS Domestic Transfer": "RBU",
        "International Transfer": "INU",
        "Online Domestic Transfer": "OBU",
        "BI FAST by Proxy ID": "BPU",
        "BI FAST by Account Number": "BAU",
        "Virtual Account": "VIA",
        "UBP": "UBP"
    }

    ft_service_code = FT_SERVICE_MAPPING.get(
        doc.ft_service
    )

    beneficiary_name = (
        doc.party_name
        or doc.party
    )

    beneficiary_bank_code = None
    beneficiary_bank_name = None

    if doc.beneficary_bank:

        bank_data = frappe.db.get_value(
            "Bank",
            doc.beneficary_bank,
            ["bank_code", "bank_name"],
            as_dict=True
        )

        if bank_data:

            beneficiary_bank_code = (
                bank_data.bank_code
            )

            beneficiary_bank_name = (
                bank_data.bank_name
            )

    return {
        "ft_service_code": ft_service_code,
        "beneficiary_name": beneficiary_name or beneficiary_bank_name,
        "beneficiary_bank_code": beneficiary_bank_code,
        "beneficiary_bank_name": beneficiary_bank_name
    }

@frappe.whitelist()
def get_mandiri_kcm_warnings(payment_entry):

    doc = frappe.get_doc(
        "Payment Entry",
        payment_entry
    )

    if (
        doc.payment_type not in [
            "Pay",
            "Internal Transfer"
        ]
        or not is_mandiri_kcm(
            doc.paid_from
        )
    ):
        return {
            "has_warning": False,
            "missing_fields": []
        }

    data = get_mandiri_kcm_data(
        doc
    )

    ft_service_code = (
        data["ft_service_code"]
    )

    if not ft_service_code:

        return {
            "has_warning": True,
            "missing_fields": [
                f"FT Service mapping ({doc.ft_service})"
            ]
        }

    required_fields = {

        "IBU": {
            "debit_account": doc.no_rekening_asal,
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
            "amount": doc.paid_amount,
            "currency": doc.paid_from_account_currency,
        },

        "OBU": {
            "debit_account": doc.no_rekening_asal,
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
            "bank_code": data["beneficiary_bank_code"],
            "amount": doc.paid_amount,
            "currency": doc.paid_from_account_currency,
        },

        "LBU": {
            "debit_account": doc.no_rekening_asal,
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
            "bank_code": data["beneficiary_bank_code"],
            "amount": doc.paid_amount,
            "currency": doc.paid_from_account_currency,
        },

        "RBU": {
            "debit_account": doc.no_rekening_asal,
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
            "bank_code": data["beneficiary_bank_code"],
            "amount": doc.paid_amount,
            "currency": doc.paid_from_account_currency,
        },

        "BAU": {
            "debit_account": doc.no_rekening_asal,
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
            "bank_code": data["beneficiary_bank_code"],
            "amount": doc.paid_amount,
            "currency": doc.paid_from_account_currency,
        },

        "BPU": {
            "bank_code": data["beneficiary_bank_code"],
            "beneficiary_account": doc.beneficary_account,
            "beneficiary_name": data["beneficiary_name"],
        },

        "INU": {},

        "VIA": {
            "beneficiary_account": doc.beneficary_account,
        },

        "UBP": {
            "debit_account": doc.no_rekening_asal,
            "bill_code": doc.bill_code,
            "bill_no": doc.bill_no,
        },
    }

    fields = required_fields.get(
        ft_service_code,
        {}
    )

    missing_fields = [
        fieldname
        for fieldname, value in fields.items()
        if not value
    ]

    return {
        "has_warning": bool(
            missing_fields
        ),
        "missing_fields": (
            missing_fields
        )
    }

def create_kcm_from_pe(doc, method=None):

    # Hanya proses Bank Draft
    if doc.mode_of_payment != "Bank Draft":
        return

    if doc.payment_type not in [
        "Pay",
        "Internal Transfer"
    ]:
        return

    if not is_mandiri_kcm(
        doc.paid_from
    ):
        return

    if doc.kcm_reference:
        previous_status = frappe.db.get_value(
            "Mandiri Kopra Cash Management",
            doc.kcm_reference,
            "payment_status"
        )

        if previous_status in ("In Progress", "Success"):
            frappe.throw(
                f"KCM {doc.kcm_reference} masih berstatus {previous_status}. "
                "Pengiriman ulang tidak diizinkan."
            )

    data = get_mandiri_kcm_data(
        doc
    )

    ft_service_code = (
        data["ft_service_code"]
    )

    if not ft_service_code:
        frappe.throw(
            f"FT Service {doc.ft_service} belum memiliki mapping"
        )

    if ft_service_code == "UBP":
        return create_kcm_ubp(doc, data)

    kcm = frappe.new_doc(
        "Mandiri Kopra Cash Management"
    )

    kcm.posting_date = doc.posting_date
    kcm.company = doc.company

    kcm.path = doc.path
    kcm.public_key = doc.public_key

    kcm.mft_server = frappe.db.get_value(
        "Mandiri Public Key",
        doc.public_key,
        "mft_server"
    )

    kcm.payment_status = "In Progress"

    row = kcm.append(
        "detail",
        {}
    )

    row.ft_service = (
        ft_service_code
    )

    row.instruction_date = (
        get_next_day()
    )

    row.payment_entry = (
        doc.name
    )

    row.debit_account = (
        doc.no_rekening_asal
    )

    row.beneficiary_account = (
        doc.beneficary_account
    )

    row.beneficiary_name = (
        data["beneficiary_name"]
    )

    row.currency = (
        doc.paid_from_account_currency
    )

    row.amount = (
        doc.paid_amount
    )

    row.customer_reference = (
        doc.name
    )

    row.remarks = (
        doc.name    
    )

    if ft_service_code in [
        "OBU",
        "LBU",
        "RBU",
        "BAU",
        "BPU"
    ]:

        row.bank_code = (
            data["beneficiary_bank_code"]
        )

        row.beneficiary_bank_name = (
            data["beneficiary_bank_name"]
        )

    if ft_service_code == "INU":

        row.country_code = (
            doc.country_code
        )

        row.purpose_code = (
            doc.purpose_code
        )

        row.transaction_description = (
            doc.transaction_description
        )

    if ft_service_code == "BPU":

        row.proxy_type = (
            doc.proxy_type
        )

    kcm.insert(
        ignore_permissions=True
    )

    kcm.submit()

    doc.db_set(
        "kcm_reference",
        kcm.name
    )

    doc.db_set(
        "payment_status",
        "In Progress"
    )

    doc.db_set(
        "kcm_response",
        ""
    )

    return kcm.name

def create_kcm_ubp(doc, data):

    kcm = frappe.new_doc("Mandiri Kopra Cash Management")

    kcm.posting_date = doc.posting_date
    kcm.company = doc.company
    kcm.path = doc.path
    kcm.public_key = doc.public_key

    kcm.mft_server = frappe.db.get_value(
        "Mandiri Public Key",
        doc.public_key,
        "mft_server"
    )

    kcm.payment_status = "In Progress"

    row = kcm.append("bill_detail", {})

    row.ft_service = "UBP"
    row.paid_from = doc.paid_from

    # row.instruction_date = get_next_day()

    row.payment_entry = doc.name
    row.debit_account = (
        doc.no_rekening_asal
    )

    row.biller_code = doc.bill_code
    row.bill_key_1 = doc.bill_no
    row.bill_key_2 = doc.paid_amount

    row.amount = doc.paid_amount
    row.currency = doc.paid_from_account_currency
    row.remarks = doc.remarks

    kcm.insert(ignore_permissions=True)
    kcm.submit()

    doc.db_set("kcm_reference", kcm.name)
    doc.db_set("payment_status", "In Progress")

    return kcm.name


def reset_kcm_fields_before_insert(doc, method=None):
    doc.kcm_reference = None
    doc.payment_status = None
    doc.kcm_response = None


def validate_bank_admin_charges_account(doc, method=None):
    if doc.workflow_state != "Pending Release":
        return

    if not doc.requires_mandiri_kcm:
        return

    account = frappe.db.get_value(
        "Bank Admin Charges Account",
        {
            "parent": "STH Accounting Settings",
            "parentfield": "bank_admin_charges_accounts",
            "company": doc.company
        },
        "account"
    )

    if not account:
        frappe.throw(
            f"Bank Admin Charges Account untuk Company {doc.company} "
            "belum dikonfigurasi. Silakan isi terlebih dahulu di STH Accounting Settings."
        )

    if not frappe.db.exists(
        "Account",
        {"name": account, "company": doc.company, "is_group": 0}
    ):
        frappe.throw(
            f"Akun Bank Admin Charges untuk Company {doc.company} "
            "tidak valid. Periksa STH Accounting Settings."
        )


def create_kcm_when_pending_release(doc, method=None):
    if doc.workflow_state != "Pending Release":
        return

    if not doc.requires_mandiri_kcm:
        return

    previous = doc.get_doc_before_save()

    # Jangan buat KCM ulang jika masih di Pending Release
    if previous and previous.workflow_state == "Pending Release":
        return

    # Simpan workflow state sebelum masuk Pending Release
    if previous and previous.workflow_state:
        doc.kcm_previous_workflow_state = previous.workflow_state

        frappe.db.set_value(
            "Payment Entry",
            doc.name,
            "kcm_previous_workflow_state",
            previous.workflow_state,
            update_modified=False
        )

    create_kcm_from_pe(doc)


def get_next_day():

    return (
        datetime.now() +
        timedelta(days=1)
    ).strftime("%Y%m%d")

def debug_requires_mandiri_kcm(payment_entry):
    doc = frappe.get_doc("Payment Entry", payment_entry)

    return {
        "name": doc.name,
        "mode_of_payment": doc.mode_of_payment,
        "payment_type": doc.payment_type,
        "paid_from": doc.paid_from,
        "is_mandiri_kcm": is_mandiri_kcm(doc.paid_from),
        "requires_mandiri_kcm": doc.requires_mandiri_kcm,
    }