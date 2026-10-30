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
        if dt == "Purchase Invoice":
            # retensi yang sudah dipotong lewat taxes tidak ada di outstanding
            from sth.overrides.purchase_invoice import retensi_ditahan

            outstanding_amount -= retensi_ditahan(doc)
        else:
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


# Sub tipe Others yang menagih customer. Management Fee KUD justru mengkredit
# piutangnya, dan Nota DP sudah dibayar Payment Entry-nya sendiri.
OTHERS_DITAGIH = ("Asset", "Barang Non Stok", "Jual Asset")

SQL_SI_NOTA_PIUTANG = """
    SELECT t.pengakuan_penjualan FROM `tabNota Piutang Pemenuhan Kontrak Table` t
    WHERE t.parent = np.name AND t.parenttype = 'Nota Piutang'
"""


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_nota_piutang_belum_lunas(doctype, txt, searchfield, start, page_len, filters):
    """Nota Piutang yang masih punya tagihan belum lunas, lihat get_tagihan_nota_piutang.

    Sisa jurnal dihitung dari Payment Entry tersubmit, sama dengan outstanding Sales
    Invoice yang baru berkurang waktu pembayarannya disubmit.
    """
    filters = filters or {}

    return frappe.db.sql("""
        SELECT np.name, np.tipe, IFNULL(np.sub_tipe_others, ''), IFNULL(np.no_kontrak, '')
        FROM `tabNota Piutang` np
        WHERE np.docstatus = 1
          AND (np.tipe = 'Pemenuhan Kontrak' OR (np.tipe = 'Others' AND np.sub_tipe_others IN %(others)s))
          AND (%(company)s = '' OR np.company = %(company)s)
          AND (np.name LIKE %(txt)s OR np.no_kontrak LIKE %(txt)s OR np.bulan LIKE %(txt)s)
          AND (
            EXISTS (
              SELECT 1 FROM `tabSales Invoice` si
              WHERE si.docstatus = 1
                AND si.outstanding_amount > 0
                AND (si.name = np.sales_invoice OR si.name IN ({si}))
            )
            OR EXISTS (
              SELECT 1
              FROM `tabJournal Entry` je
              JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
              WHERE je.nota_piutang = np.name
                AND je.docstatus = 1
                AND jea.party_type = 'Customer'
                AND jea.debit_in_account_currency > IFNULL((
                  SELECT SUM(per.allocated_amount)
                  FROM `tabPayment Entry Reference` per
                  JOIN `tabPayment Entry` pe ON pe.name = per.parent
                  WHERE per.reference_doctype = 'Journal Entry'
                    AND per.reference_name = je.name
                    AND pe.docstatus = 1
                ), 0)
            )
          )
        ORDER BY np.date DESC, np.name DESC
        LIMIT %(start)s, %(page_len)s
    """.format(si=SQL_SI_NOTA_PIUTANG), {
        "others": OTHERS_DITAGIH,
        "company": filters.get("company") or "",
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    })


@frappe.whitelist()
def get_tagihan_nota_piutang(nota_piutang, payment_entry=None):
    """Baris references Payment Entry untuk tagihan Nota Piutang yang belum lunas.

    - Pemenuhan Kontrak: Sales Invoice di List Pengakuan Penjualan, ditambah Journal
      Entry PPN + Reclass-nya (pengakuan_penjualan_ppn berisi nama Journal Entry).
    - Others Jual Asset: Sales Invoice-nya, ditambah Journal Entry PPN-nya.
    - Others Asset / Barang Non Stok: Journal Entry piutang customer dari nota ini.

    paid_from ikut akun piutang baris pertama: piutang Others memakai akun piutang
    lain-lain, bukan akun default customer.
    """
    np = frappe.get_doc("Nota Piutang", nota_piutang)
    np.check_permission("read")

    if np.docstatus != 1:
        frappe.throw(_("Nota Piutang {0} belum di-submit").format(np.name))

    rows = []

    si_names = []
    if np.tipe == "Pemenuhan Kontrak":
        si_names = [d.pengakuan_penjualan for d in np.nota_hutang_pemenuhan_kontrak_table if d.pengakuan_penjualan]
    elif np.tipe == "Others" and np.sub_tipe_others == "Jual Asset" and np.sales_invoice:
        si_names = [np.sales_invoice]

    for name in dict.fromkeys(si_names):
        si = frappe.get_doc("Sales Invoice", name)
        if si.docstatus != 1 or flt(si.outstanding_amount) <= 0:
            continue

        rows.append({
            "reference_doctype": "Sales Invoice",
            "reference_name": si.name,
            "party": si.customer,
            "account": si.debit_to,
            "bill_no": si.get("bill_no") or "",
            "due_date": si.due_date,
            "total_amount": flt(si.grand_total),
            "outstanding_amount": flt(si.outstanding_amount),
            "exchange_rate": flt(si.conversion_rate) or 1,
        })

    if np.tipe == "Pemenuhan Kontrak" or (np.tipe == "Others" and np.sub_tipe_others in OTHERS_DITAGIH):
        sudah = {r["reference_name"] for r in rows}
        # Neto debit - kredit: JE Reclass bernilai minus mengkredit piutang customer
        # di jurnal yang sama dengan debit PPN-nya
        for je in frappe.db.sql("""
            SELECT je.name, jea.party, jea.account,
                SUM(jea.debit_in_account_currency - jea.credit_in_account_currency) AS total
            FROM `tabJournal Entry` je
            JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
            WHERE je.nota_piutang = %(np)s
              AND je.docstatus = 1
              AND jea.party_type = 'Customer'
            GROUP BY je.name, jea.party, jea.account
            HAVING total > 0
        """, {"np": np.name}, as_dict=True):
            if je.name in sudah:
                continue

            # Payment Entry yang sedang dibuka tidak dihitung, supaya barisnya bisa
            # ditarik ulang setelah sempat dihapus
            dialokasikan = frappe.db.sql("""
                SELECT COALESCE(SUM(per.allocated_amount), 0)
                FROM `tabPayment Entry Reference` per
                JOIN `tabPayment Entry` pe ON pe.name = per.parent
                WHERE per.reference_doctype = 'Journal Entry'
                  AND per.reference_name = %(je)s
                  AND pe.docstatus = 1
                  AND pe.name != %(payment_entry)s
            """, {"je": je.name, "payment_entry": payment_entry or ""})[0][0]

            sisa = flt(je.total) - flt(dialokasikan)
            if sisa <= 0:
                continue

            rows.append({
                "reference_doctype": "Journal Entry",
                "reference_name": je.name,
                "party": je.party,
                "account": je.account,
                "total_amount": flt(je.total),
                "outstanding_amount": sisa,
                "exchange_rate": 1,
            })

    # Unit Nota Piutang cuma diisi form-nya dari Sales Order, jadi bisa kosong;
    # ambil dari Sales Order atau Sales Invoice tagihannya
    company, unit = np.company, np.unit
    if not (company and unit) and np.get("no_kontrak"):
        so = frappe.db.get_value("Sales Order", np.no_kontrak, ["company", "unit"], as_dict=True) or {}
        company, unit = company or so.get("company"), unit or so.get("unit")
    for r in rows:
        if company and unit:
            break
        si = frappe.db.get_value(r["reference_doctype"], r["reference_name"],
            ["company", "unit"] if r["reference_doctype"] == "Sales Invoice" else ["company"], as_dict=True) or {}
        company, unit = company or si.get("company"), unit or si.get("unit")

    return {
        "company": company,
        "unit": unit,
        "customer": rows[0]["party"] if rows else np.get("customer"),
        "paid_from": rows[0]["account"] if rows else None,
        "rows": rows,
    }


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