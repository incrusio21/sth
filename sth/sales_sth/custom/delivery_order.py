

def set_default_tax_fields(doc, method):
    if not doc.taxes:
        return

    for row in doc.taxes:
        if row.meta.has_field("add_deduct_tax"):
            row.add_deduct_tax = "Add"

        if row.meta.has_field("category"):
            row.category = "Valuation and Total"