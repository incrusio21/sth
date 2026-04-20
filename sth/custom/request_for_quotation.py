import frappe

def update_unit_in_table(self,method):
    for row in self.items:
        row.unit = self.unit


@frappe.whitelist()
def check_created_rfq(pr_sr):
    data = frappe.db.sql("""
        select rfq.name 
        from `tabRequest for Quotation` rfq
        join `tabRequest for Quotation Item` rfqi on rfq.name = rfqi.parent
        where rfqi.material_request = %s
        group by rfq.name
    """,(pr_sr),as_dict=True)

    return [r.name for r in data]