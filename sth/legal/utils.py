# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

from frappe.utils import getdate

def get_days_name(date_string):
    """
    Mengembalikan nama hari dalam Bahasa Indonesia
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        string nama hari
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    days = {
        0: "Senin",
        1: "Selasa",
        2: "Rabu",
        3: "Kamis",
        4: "Jumat",
        5: "Sabtu",
        6: "Minggu"
    }
    return days.get(date_obj.weekday(), "")

def get_date_number(date_string):
    """
    Mengembalikan tanggal dalam angka (1-31)
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        int tanggal
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    return str(date_obj.day).zfill(2)

def get_date_text(date_string):
    """
    Mengembalikan tanggal dalam teks (satu, dua, tiga, dst)
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        string tanggal dalam teks
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    return number_to_text(date_obj.day).title()

def get_month_number(date_string):
    """
    Mengembalikan bulan dalam angka (1-12)
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        int bulan
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    return str(date_obj.month).zfill(2)

def get_month_name(date_string):
    """
    Mengembalikan nama bulan dalam Bahasa Indonesia
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        string nama bulan
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    months = {
        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember"
    }
    return months.get(date_obj.month, "")

def get_year_number(date_string):
    """
    Mengembalikan tahun dalam angka (2024, 2025, dst)
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        int tahun
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    return date_obj.year

def get_year_text(date_string):
    """
    Mengembalikan tahun dalam teks (dua ribu dua puluh empat, dst)
    Args:
        date_string: string tanggal atau datetime object
    Returns:
        string tahun dalam teks
    """
    if not date_string:
        return ""
    
    date_obj = getdate(date_string)
    return number_to_text(date_obj.year)

def money_to_text(number):
    from num2words import num2words

    integer = int(number)
    try:
        ret = num2words(integer, lang="id")
    except NotImplementedError:
        ret = num2words(integer, lang="en")
    except OverflowError:
        ret = num2words(integer, lang="en")
    return ret.replace("-", " ")

def file_image(url):
    return f"""<img src="{url}"></a>"""

def number_to_text(number):
    """
    Konversi angka ke teks Bahasa Indonesia
    Args:
        number: int angka yang akan dikonversi
    Returns:
        string angka dalam teks
    """
    if number == 0:
        return "nol"
    
    ones = ["", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan"]
    teens = ["sepuluh", "sebelas", "dua belas", "tiga belas", "empat belas", "lima belas", 
             "enam belas", "tujuh belas", "delapan belas", "sembilan belas"]
    tens = ["", "", "dua puluh", "tiga puluh", "empat puluh", "lima puluh", 
            "enam puluh", "tujuh puluh", "delapan puluh", "sembilan puluh"]
    
    def convert_below_thousand(n):
        if n == 0:
            return ""
        elif n < 10:
            return ones[n]
        elif n < 20:
            return teens[n - 10]
        elif n < 100:
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
        else:
            if n == 100:
                return "seratus"
            elif n < 200:
                return "seratus " + convert_below_thousand(n % 100)
            else:
                return ones[n // 100] + " ratus" + (" " + convert_below_thousand(n % 100) if n % 100 != 0 else "")
    
    if number < 1000:
        return convert_below_thousand(number)
    elif number < 2000:
        return "seribu" + (" " + convert_below_thousand(number % 1000) if number % 1000 != 0 else "")
    elif number < 1000000:
        return convert_below_thousand(number // 1000) + " ribu" + (" " + convert_below_thousand(number % 1000) if number % 1000 != 0 else "")
    else:
        return str(number)  # Fallback untuk angka sangat besar