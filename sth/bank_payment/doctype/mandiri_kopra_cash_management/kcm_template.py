# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cstr
from datetime import datetime, timedelta

# def mtfu_separated(self):
# 	content = "M;1;;1;;;;1020011824312;1270014263220;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;IBU;;;;;;;Y;mco.phang@bankmandiri.co.id;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;E;Testing 1\n"
# 	content += "M;1;;2;;;;1020011824312;90340034508;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;BAU;2130101;SMBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 2\n"
# 	content += "M;2;20251217;3;;;;1020011824312;5470835321;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;OBU;0140397;BCA;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 3\n"
# 	content += "M;3;20251217;4;1;2;20260131;1020011824312;693814208833;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;;;;;;LBU;0280024;OCBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;;;;;;;;;;;;;;;;;;;;;E;Testing 4"
	
# 	return content

# def mtfu_consolidated(self):
#     return (
#         "P;20260502;1020011824312;4;40004\r\n"
#         "1270014263220;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;Contoh Trx Inhouse;Contoh Trx Inhouse;IBU;;;;;;;Y;mco.phang@bankmandiri.co.id;;;;;;;;;;;;;;;;;;;;;;;\r\n"
#         "90340034508;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;Contoh Trx BIFAST;Contoh Trx BIFAST;BAU;2130101;SMBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;Testing\r\n"
#         "5470835321;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;Contoh Trx Online;Contoh Trx Online;OBU;0140397;BCA;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;Testing\r\n"
#         "693814208833;Raja Fitha Samudra;Jakarta;Jakarta;Jakarta;IDR;10001;Contoh Trx SKN;Contoh Trx SKN;LBU;0280024;OCBC;Jakarta;Jakarta;Jakarta;;;;;;;;;;;;;;;;;;;;;;;;OUR;1;Testing"
#     )

def mtfu_separated(self):
    lines = []

    def safe(v, default=""):
        return default if v is None else v

    for row in self.detail:
        lines.append(build_mtfu_separated({
            "instruction_mode": "1",
            "session": safe(row.session, "1"),
            "debit_account": safe(row.debit_account),
            "beneficiary_account": safe(row.beneficiary_account),
            "beneficiary_name": safe(row.beneficiary_name),
            "currency": safe(row.currency),
            "amount": safe(row.amount),
            "ft_service": safe(row.ft_service),
            "bank_code": safe(row.bank_code),
            "bank_name": safe(row.beneficiary_bank_name),
            "remark": safe(row.remark),
            "customer_ref": safe(row.customer_reference),
            "email_flag": "Y" if row.email_flag else "",
            "email": safe(row.email),
            "charge": safe(row.charge, "OUR"),
            "beneficiary_type": safe(row.beneficiary_type, "1")
        }))

    return "\r\n".join(lines)

def mtfu_consolidated(self):
    lines = []

    if not self.detail:
        return ""

    debit_accounts = {d.debit_account for d in self.detail if d.debit_account}
    if len(debit_accounts) > 1:
        raise Exception("Consolidated hanya boleh 1 debit account")

    if not self.detail[0].debit_account:
        raise Exception("Debit account tidak boleh kosong")

    total_amount = sum(float(d.amount or 0) for d in self.detail)
    total_records = len(self.detail)

    debit_account = self.detail[0].debit_account

    lines.append(build_consolidated_header({
        "debit_account": debit_account,
        "total_amount": total_amount,
        "total_records": total_records
    }))

    for row in self.detail:
        lines.append(build_consolidated_detail({
            "beneficiary_account": row.beneficiary_account,
            "beneficiary_name": row.beneficiary_name,
            "city": "Jakarta",
            "currency": row.currency,
            "amount": row.amount,
            "ft_service": row.ft_service or "IBU",
            "bank_code": row.bank_code,
            "bank_name": row.beneficiary_bank_name,
            "remark": row.remark,
            "customer_ref": row.customer_reference,

            "email_flag": row.email_flag,

            "email": row.email or "",
            "charge": row.charge or "OUR",
            "beneficiary_type": row.beneficiary_type or "1"
        }))

    return "\r\n".join(lines) + "\r\n"

# def mtfu_bill_separated(self):
#     lines = []

#     if not self.bill_detail:
#         return ""

#     for row in self.bill_detail:
#         bill_key_2 = row.bill_key_2 or row.amount

#         lines.append(build_bill_detail({
#             "instruction_mode": "2",
#             "instruction_date": get_next_day(), 

#             "debit_account": row.debit_account,
#             "biller_code": row.biller_code,

#             "bill_key_1": row.bill_key_1,
#             "bill_key_2": bill_key_2,
#             "bill_key_3": row.bill_key_3,

#             "currency": row.currency or "IDR",

#             "transaction_reference": row.transaction_reference or row.remark,
#             "remark": row.remark,

#             "email": row.email,
#             "extended_payment_detail": row.extended_payment_detail,
#         }))

#     return "\r\n".join(lines)

def mtfu_bill_separated(self):
    return(
        "M;1;;;;;;1680001067568;88042;;880421234151093;180000;;IDR;2;UBP;Amount IDR 180000 tr;;;;;E\r\n"
    )
    # return (
    #     "M;2;20260507;2;1;;20260507;1150015101993;88042;Bank Mandiri;880421234151093;;50000;IDR;Payment;UBP;Payment;riskyaghata@gmail.com;;;EPD1;E\r\n"
    #     "M;2;20260507;2;1;;20260507;1150015101993;88047;Bank Mandiri - CMD;880471234151093;;75000;IDR;Payment;UBP;Payment;riskyaghata@gmail.com;;;EPD2;E\r\n"
    # )
    # return (
    #     "P;1680001067568;7;2;20171015;2;1;;20171020\r\n"
    #     "88042;Bank Mandiri;880421234151093;50000;;IDR;Payment;UBP;Payment;riskyaghata@gmail.com;;;EPD1;E\r\n"
    #     "88047;Bank Mandiri - CMD;880471234151093;;;IDR;Payment;UBP;Payment;riskyaghata@gmail.com;;;EPD2;E\r\n"
    # )

def mtfu_payroll(self):

    header = "P;20260507;1020011824312;2;200000.00"

    row1 = [
        "1111111111", "BUDI", "JKT", "JKT", "JKT",
        "IDR", "100000.00", "GAJI", "REF001", "IBU",
        "", "", "", "", "", "",
        "Y", "budi@test.com"
    ]

    row1.extend([""] * 19)

    row1.extend([
        "OUR", "1", "PAYROLL", ""
    ])

    row2 = [
        "2222222222", "SITI", "JKT", "JKT", "JKT",
        "IDR", "100000.00", "GAJI", "REF002", "OBU",
        "014", "BCA", "JKT", "JKT", "JKT", "JKT",
        "Y", "siti@test.com"
    ]

    row2.extend([""] * 19)

    row2.extend([
        "OUR", "1", "PAYROLL", ""
    ])

    return (
        header + "\r\n" +
        ";".join(row1) + "\r\n" +
        ";".join(row2)
    )

# def mtfu_separated(self):
#     lines = []

#     dummy_rows = [
#         {
#             "instruction_mode": "1",
#             "session": "1",
#             "debit_account": "1680001067568",
#             "beneficiary_account": "1680001443819",
#             "beneficiary_name": "PT MAJU JAYA ABADI",
#             "currency": "IDR",
#             "amount": "1000000",
#             "ft_service": "IBU",
#             "bank_code": "008",
#             "remark": "PEMBAYARAN INVOICE APRIL",
#             "customer_ref": "INV-2026-001",
#             "email_flag": "Y",
#             "email": "finance@majujaya.co.id",
#             "charge": "OUR",
#             "beneficiary_type": "1"
#         },
#         {
#             "instruction_mode": "1",
#             "session": "1",
#             "debit_account": "1680001067568",
#             "beneficiary_account": "1680001443819",
#             "beneficiary_name": "CV SUMBER REJEKI",
#             "currency": "IDR",
#             "amount": "1000000",
#             "ft_service": "IBU",
#             "bank_code": "008",
#             "remark": "PEMBAYARAN PROJECT",
#             "customer_ref": "PRJ-2026-002",
#             "email_flag": "",
#             "email": "",
#             "charge": "BEN",
#             "beneficiary_type": "1"
#         }
#     ]

#     for row in dummy_rows:
#         lines.append(build_mtfu_separated(row))

#     return "\r\n".join(lines)

def clean_str(v):
    if v is None:
        return ""
    v = str(v)
    return v.replace(";", "").replace("\n", " ").replace("\r", " ").strip()

def limit(v, max_len):
    return v[:max_len] if max_len else v

def val(data, key, max_len=None, default="", upper=False, numeric=False):
    v = data.get(key, default)
    v = clean_str(v)

    if upper:
        v = v.upper()

    if numeric:
        v = v.replace(",", "").replace(".", "")

    return limit(v, max_len)

def format_amount(v):
    try:
        return str(int(float(v)))
    except:
        return "0"
    
def format_amount_decimal(v):
    try:
        return f"{float(v):.2f}"
    except:
        return "0.00"

def validate_ft_service(v):
    allowed = {"IBU", "LBU", "RBU", "INU", "OBU", "BPU", "BAU", "VIA"}

    if v not in allowed:
        frappe.throw(f"Invalid FT Service: {v}")

    return v

def get_next_day():
    return (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

def build_mtfu_separated(data: dict):
    fields = [""] * 72

    fields[0] = "M"
    fields[1] = val(data, "instruction_mode", 1, default="1")
    fields[2] = get_next_day()  
    fields[3] = val(data, "session", 6, default="1")

    fields[7] = val(data, "debit_account", 40, numeric=True)
    fields[8] = val(data, "beneficiary_account", 35)
    fields[9] = val(data, "beneficiary_name", 35)

    fields[13] = val(data, "currency", 4, upper=True)
    fields[14] = format_amount(data.get("amount"))

    fields[18] = val(data, "remark", 19)   
    fields[19] = val(data, "customer_ref", 19)

    ft = val(data, "ft_service", 3, upper=True)
    fields[20] = validate_ft_service(ft)

    fields[21] = val(data, "bank_code", 12)
    fields[22] = val(data, "bank_name", 35)

    fields[27] = val(data, "email_flag", 1, upper=True)
    fields[28] = val(data, "email", 100)

    fields[49] = val(data, "charge", 3, default="OUR", upper=True)

    fields[50] = val(data, "beneficiary_type", 3, default="1")

    fields[71] = "E"

    return ";".join(fields)

def build_consolidated_header(data: dict):
    fields = []

    fields.append("P")
    fields.append(get_next_day())
    fields.append(val(data, "debit_account", 40, numeric=True))
    fields.append(str(data.get("total_records", 0)))
    fields.append(format_amount(data.get("total_amount")))

    return ";".join(fields)

def build_consolidated_detail(data: dict):
    fields = [""] * 41

    fields[0] = val(data, "beneficiary_account", 35)
    fields[1] = val(data, "beneficiary_name", 35)
    fields[2] = val(data, "city", 35, default="Jakarta")
    fields[3] = val(data, "city", 35, default="Jakarta")
    fields[4] = val(data, "city", 35, default="Jakarta")
    fields[5] = val(data, "currency", 3, upper=True)
    fields[6] = format_amount(data.get("amount"))
    fields[7] = val(data, "remark", 20)
    fields[8] = val(data, "customer_ref", 19)
    fields[9] = val(data, "ft_service", 3, default="IBU", upper=True)
    fields[10] = val(data, "bank_code", 12)
    fields[11] = val(data, "bank_name", 35)
    fields[12] = val(data, "bank_addr1", 35)
    fields[13] = val(data, "bank_addr2", 35)
    fields[14] = val(data, "bank_addr3", 35)
    fields[15] = val(data, "bank_city", 35)
    fields[16] = val(data, "email_flag", 1, default="N", upper=True)

    if fields[16] == "Y":
        fields[17] = val(data, "email", 100)
    else:
        fields[17] = ""

    fields[38] = val(data, "charge", 3, default="OUR", upper=True)
    fields[39] = val(data, "beneficiary_type", 3, default="1")
    fields[40] = val(data, "extended_payment_detail", 999)
    # fields[41] = val(data, "correspondent_bank", 100)
    # fields[42] = val(data, "treasury_ref", 15)
    # fields[43] = val(data, "underlying_doc", 100)

    return ";".join(fields)

def build_bill_detail(data: dict):
    fields = [""] * 22

    fields[0] = "M"
    fields[1] = val(data, "instruction_mode", 1, default="1")
    fields[2] = val(data, "instruction_date", 8)   # WAJIB kalau schema ada
    fields[3] = val(data, "session", 10)
    fields[4] = val(data, "recurring_type", 10)
    fields[5] = val(data, "recurring_interval", 10)
    fields[6] = val(data, "recurring_end_date", 8)

    fields[7] = val(data, "debit_account", 40, numeric=True)
    fields[8] = val(data, "biller_code", 10)
    fields[9] = ""  # jangan skip

    fields[10] = val(data, "bill_key_1", 50)
    fields[11] = val(data, "bill_key_2", 50)
    fields[12] = val(data, "bill_key_3", 50)

    fields[13] = val(data, "currency", 3, upper=True, default="IDR")
    fields[14] = val(data, "transaction_reference", 19, default="Payment")

    fields[15] = "UBP"
    fields[16] = val(data, "remark", 20)
    fields[17] = val(data, "email", 100)

    fields[20] = val(data, "extended_payment_detail", 999)
    fields[21] = "E"

    return ";".join(str(f or "") for f in fields)