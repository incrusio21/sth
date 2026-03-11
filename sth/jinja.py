from frappe.utils import get_defaults
from num2words import num2words
import frappe
from datetime import datetime

def money_in_words_idr(
    number,  # bisa Union[str, float, int]
    main_currency=None,
    fraction_currency=None
):
    try:
        number = int(round(float(number)))
    except (ValueError, TypeError):
        return ""

    return f"{num2words(number, lang='id')} rupiah"

def format_tanggal_id(tanggal):
    if not tanggal:
        return ""

    bulan = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }

    if isinstance(tanggal, str):
        tanggal = frappe.utils.getdate(tanggal)

    return f"{tanggal.day} {bulan[tanggal.month]} {tanggal.year}"