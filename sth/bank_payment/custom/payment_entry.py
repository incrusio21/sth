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

def is_mandiri_kcm(account):

	if not account:
		return False

	bank = frappe.db.get_value(
		"Bank Account",
		{
			"account": account
		},
		"bank"
	)

	if not bank:
		return False

	return bool(
		frappe.db.get_value(
			"Bank",
			bank,
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
        "beneficiary_name": beneficiary_name,
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
        }
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

    if doc.payment_type not in [
        "Pay",
        "Internal Transfer"
    ]:
        return

    if not is_mandiri_kcm(
        doc.paid_from
    ):
        return

    existing = frappe.db.sql("""
        SELECT kcm.name
        FROM `tabMandiri Kopra Detail` d
        INNER JOIN `tabMandiri Kopra Cash Management` kcm
            ON kcm.name = d.parent
        WHERE
            d.payment_entry = %s
            AND kcm.payment_status = 'Success'
            AND kcm.docstatus = 1
        LIMIT 1
    """, doc.name, as_dict=True)

    # if existing:
    #     frappe.throw(
    #         f"Payment Entry {doc.name} sudah pernah berhasil dikirim ke bank melalui KCM {existing[0].name}"
    #     )

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
        doc.reference_no
    )

    row.remarks = (
        doc.remarks
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

    row.amount = doc.paid_amount
    row.currency = doc.paid_from_account_currency
    row.remarks = doc.remarks

    kcm.insert(ignore_permissions=True)
    # kcm.submit()

    doc.db_set("kcm_reference", kcm.name)
    doc.db_set("payment_status", "In Progress")

    return kcm.name


def get_next_day():

    return (
        datetime.now() +
        timedelta(days=1)
    ).strftime("%Y%m%d")