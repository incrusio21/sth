# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from functools import reduce


import frappe
from frappe import _, scrub
from frappe.utils import flt, getdate, nowdate

from erpnext.accounts.party import (
	complete_contact_details, 
	get_party_bank_account
)
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	allocate_open_payment_requests_to_references,
	apply_early_payment_discount,
	get_bank_cash_account,
	get_reference_as_per_payment_terms,
	set_grand_total_and_outstanding_amount,
	set_paid_amount_and_received_amount,
	set_party_account,
	set_party_account_currency,
	set_party_type,
	set_payment_type,
	set_pending_discount_loss,
	split_early_payment_discount_loss,
	update_accounting_dimensions
)

@frappe.whitelist()
def get_payment_entry(
	dt,
	dn,
	party_amount=None,
	bank_account=None,
	bank_amount=None,
	party_type=None,
	payment_type=None,
	reference_date=None,
	ignore_permissions=False,
	created_from_payment_request=False,
):
    doc = frappe.get_doc(dt, dn)
    over_billing_allowance = frappe.db.get_single_value("Accounts Settings", "over_billing_allowance")
    if dt in ("Sales Order", "Purchase Order") and flt(doc.per_billed, 2) >= (100.0 + over_billing_allowance):
        frappe.throw(_("Can only make payment against unbilled {0}").format(_(dt)))

    if not party_type:
        party_type = set_party_type(dt)

    party_account = set_party_account(dt, dn, doc, party_type)
    party_account_currency = set_party_account_currency(dt, party_account, doc)

    if not payment_type:
        payment_type = set_payment_type(dt, doc)

    grand_total, outstanding_amount = set_grand_total_and_outstanding_amount(
        party_amount, dt, party_account_currency, doc
    )

    # jika ada field retensi amount kurangi nilai outstanding
    if doc.get("retensi_amount") and not doc.get("retensi_paid"):
        outstanding_amount -= doc.retensi_amount
        
    # bank or cash
    bank = get_bank_cash_account(doc, bank_account)

    # if default bank or cash account is not set in company master and party has default company bank account, fetch it
    if party_type in ["Customer", "Supplier"] and not bank:
        party_bank_account = get_party_bank_account(party_type, doc.get(scrub(party_type)))
        if party_bank_account:
            account = frappe.db.get_value("Bank Account", party_bank_account, "account")
            bank = get_bank_cash_account(doc, account)

    paid_amount, received_amount = set_paid_amount_and_received_amount(
        dt, party_account_currency, bank, outstanding_amount, payment_type, bank_amount, doc
    )

    reference_date = getdate(reference_date)
    paid_amount, received_amount, discount_amount, valid_discounts = apply_early_payment_discount(
        paid_amount, received_amount, doc, party_account_currency, reference_date
    )

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = payment_type
    pe.company = doc.company
    pe.cost_center = doc.get("cost_center")
    pe.posting_date = nowdate()
    pe.reference_date = reference_date
    pe.mode_of_payment = doc.get("mode_of_payment")
    pe.party_type = party_type
    pe.party = doc.get(scrub(party_type))
    pe.contact_person = doc.get("contact_person")
    complete_contact_details(pe)
    pe.ensure_supplier_is_not_blocked()

    pe.paid_from = party_account if payment_type == "Receive" else bank.account
    pe.paid_to = party_account if payment_type == "Pay" else bank.account
    pe.paid_from_account_currency = (
        party_account_currency if payment_type == "Receive" else bank.account_currency
    )
    pe.paid_to_account_currency = party_account_currency if payment_type == "Pay" else bank.account_currency
    pe.paid_from_account_type = frappe.db.get_value("Account", pe.paid_from, "account_type")
    pe.paid_to_account_type = frappe.db.get_value("Account", pe.paid_to, "account_type")
    pe.paid_amount = paid_amount
    pe.received_amount = received_amount
    pe.letter_head = doc.get("letter_head")
    pe.bank_account = frappe.db.get_value(
        "Bank Account", {"is_company_account": 1, "is_default": 1, "company": doc.company}, "name"
    )

    if dt in ["Purchase Order", "Sales Order", "Sales Invoice", "Purchase Invoice"]:
        pe.project = doc.get("project") or reduce(
            lambda prev, cur: prev or cur, [x.get("project") for x in doc.get("items")], None
        )  # get first non-empty project from items

    if pe.party_type in ["Customer", "Supplier"]:
        bank_account = get_party_bank_account(pe.party_type, pe.party)
        pe.set("party_bank_account", bank_account)
        pe.set_bank_account_data()

    # only Purchase Invoice can be blocked individually
    if doc.doctype == "Purchase Invoice" and doc.invoice_is_blocked():
        frappe.msgprint(_("{0} is on hold till {1}").format(doc.name, doc.release_date))
    else:
        if doc.doctype in (
            "Sales Invoice",
            "Purchase Invoice",
            "Purchase Order",
            "Sales Order",
        ) and frappe.get_cached_value(
            "Payment Terms Template",
            doc.payment_terms_template,
            "allocate_payment_based_on_payment_terms",
        ):
            for reference in get_reference_as_per_payment_terms(
                doc.payment_schedule, dt, dn, doc, grand_total, outstanding_amount, party_account_currency
            ):
                pe.append("references", reference)
        else:
            if dt == "Dunning":
                for overdue_payment in doc.overdue_payments:
                    pe.append(
                        "references",
                        {
                            "reference_doctype": "Sales Invoice",
                            "reference_name": overdue_payment.sales_invoice,
                            "payment_term": overdue_payment.payment_term,
                            "due_date": overdue_payment.due_date,
                            "total_amount": overdue_payment.outstanding,
                            "outstanding_amount": overdue_payment.outstanding,
                            "allocated_amount": overdue_payment.outstanding,
                        },
                    )

                pe.append(
                    "deductions",
                    {
                        "account": doc.income_account,
                        "cost_center": doc.cost_center,
                        "amount": -1 * doc.dunning_amount,
                        "description": _("Interest and/or dunning fee"),
                    },
                )
            else:
                pe.append(
                    "references",
                    {
                        "reference_doctype": dt,
                        "reference_name": dn,
                        "bill_no": doc.get("bill_no"),
                        "due_date": doc.get("due_date"),
                        "total_amount": grand_total,
                        "outstanding_amount": outstanding_amount,
                        "allocated_amount": outstanding_amount,
                    },
                )

    tambah_je_ppn_nota_piutang(pe, dt, dn)

    pe.setup_party_account_field()
    pe.set_missing_values()
    pe.set_missing_ref_details()

    update_accounting_dimensions(pe, doc)

    if party_account and bank:
        if discount_amount:
            base_total_discount_loss = 0
            if frappe.db.get_single_value("Accounts Settings", "book_tax_discount_loss"):
                base_total_discount_loss = split_early_payment_discount_loss(pe, doc, valid_discounts)

            set_pending_discount_loss(
                pe, doc, discount_amount, base_total_discount_loss, party_account_currency
            )

        pe.set_exchange_rate(ref_doc=doc)
        pe.set_amounts()

    # If PE is created from PR directly, then no need to find open PRs for the references
    if not created_from_payment_request:
        allocate_open_payment_requests_to_references(pe.references, pe.precision("paid_amount"))

    set_note_from_purchase_invoice(pe, dt, dn, doc)

    return pe


@frappe.whitelist()
def get_je_ppn_nota_piutang(sales_invoice, party, account, payment_entry=None):
    """Journal Entry PPN Nota Piutang Jual Asset yang masih menggantung untuk invoice ini.

    PPN penjualan asset ditagihkan lewat Journal Entry tersendiri, bukan lewat Sales
    Invoice-nya, supaya outstanding invoice tetap sama dengan grand total. Jurnal itu
    tidak akan muncul di Get Outstanding Invoices, jadi harus ditarik terpisah.

    Balikan: list of dict {name, total, sisa}. `sisa` sudah dikurangi alokasi di
    Payment Entry lain — termasuk yang masih draft — supaya jurnal yang sama tidak
    tertagih dua kali. Payment Entry yang sedang dibuka dikecualikan lewat
    `payment_entry`, supaya barisnya bisa ditarik ulang setelah sempat dihapus.
    """
    if not (sales_invoice and party and account):
        return []

    je_list = frappe.db.sql("""
        SELECT je.name, SUM(jea.debit_in_account_currency) AS total
        FROM `tabJournal Entry` je
        JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
        JOIN `tabNota Piutang` np ON np.name = je.nota_piutang
        WHERE je.docstatus = 1
          AND np.docstatus = 1
          AND np.sub_tipe_others = 'Jual Asset'
          AND np.sales_invoice = %(sales_invoice)s
          AND jea.party_type = 'Customer'
          AND jea.party = %(party)s
          AND jea.account = %(account)s
        GROUP BY je.name
    """, {
        "sales_invoice": sales_invoice,
        "party": party,
        "account": account,
    }, as_dict=True)

    hasil = []

    for je in je_list:
        dialokasikan = frappe.db.sql("""
            SELECT COALESCE(SUM(per.allocated_amount), 0)
            FROM `tabPayment Entry Reference` per
            JOIN `tabPayment Entry` pe ON pe.name = per.parent
            WHERE per.reference_doctype = 'Journal Entry'
              AND per.reference_name = %(je)s
              AND pe.docstatus != 2
              AND pe.name != %(payment_entry)s
        """, {"je": je.name, "payment_entry": payment_entry or ""})[0][0]

        sisa = flt(je.total) - flt(dialokasikan)

        if sisa <= 0:
            continue

        hasil.append({"name": je.name, "total": flt(je.total), "sisa": sisa})

    return hasil


def tambah_je_ppn_nota_piutang(pe, dt, dn):
    """Ikutkan Journal Entry PPN Nota Piutang ke pembayaran yang dibuat dari invoicenya.

    Jalur tombol Payment di Sales Invoice. Yang diketik manual di form Payment Entry
    ditarik sisi client lewat get_je_ppn_nota_piutang() yang sama.
    """
    if dt != "Sales Invoice" or pe.payment_type != "Receive":
        return

    for je in get_je_ppn_nota_piutang(dn, pe.party, pe.paid_from):
        pe.append("references", {
            "reference_doctype": "Journal Entry",
            "reference_name": je["name"],
            "total_amount": je["total"],
            "outstanding_amount": je["sisa"],
            "allocated_amount": je["sisa"],
        })

        # paid_amount tadi dihitung dari outstanding invoicenya saja, jadi PPN ini
        # ditambahkan supaya tidak ada selisih yang menggantung
        pe.paid_amount = flt(pe.paid_amount) + je["sisa"]
        pe.received_amount = flt(pe.received_amount) + je["sisa"]


def set_note_from_purchase_invoice(pe, dt, dn, doc):
    """
    Keterangan PV diisi nama barang dari invoice-nya. Formatnya disamakan dengan pengisian
    otomatis di form PV (satu baris per invoice), supaya keterangan tetap konsisten kalau
    nanti ada invoice lain ditambahkan manual di tabel references.
    """
    if dt != "Purchase Invoice":
        return

    item_names = []
    for item in doc.get("items") or []:
        item_name = item.get("item_name") or item.get("item_code")

        # barang yang sama di beberapa baris invoice cukup ditulis sekali
        if item_name and item_name not in item_names:
            item_names.append(item_name)

    if not item_names:
        return

    pe.note = "{0}: {1}".format(dn, ", ".join(item_names))