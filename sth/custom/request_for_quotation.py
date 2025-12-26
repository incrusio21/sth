import frappe

def update_unit_in_table(self,method):
    for row in self.items:
        row.unit = self.unit