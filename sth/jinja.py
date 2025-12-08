from frappe.utils import get_defaults
from num2words import num2words

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