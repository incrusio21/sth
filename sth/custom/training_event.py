import frappe

def create_journal_entry(self, method):
  company = frappe.get_doc("Company", self.company)
  costings = frappe.db.sql("""
    SELECT 
    tec.expense_type,
    tec.total_amount,
    eca.default_account
    FROM `tabTraining Event Costing` as tec
    JOIN `tabExpense Claim Type` as ect ON ect.name = tec.expense_type
    JOIN `tabExpense Claim Account` as eca ON eca.parent = ect.name
    WHERE tec.parent = %s AND eca.company = %s;
  """, (self.name, self.company), as_dict=True)

  je = frappe.new_doc("Journal Entry")
  je.update({
    "company": self.company,
    "posting_date": self.custom_posting_date,
  })

  for c in costings:
    je.append("accounts", {
      "account": c['default_account'],
      "debit_in_account_currency": c['total_amount']
    })
    # frappe.throw(f"{c['expense_type']} - {c['total_amount']} - {c['default_account']}")
  
  je.append("accounts", {
    "account": company.default_payable_account,
    "party_type": "Supplier",
    "party": self.supplier,
    "credit_in_account_currency": self.custom_grand_total_costing,
  })

  je.submit()
  self.db_set("custom_journal_entry", je.name)

def delete_journal_entry(self, method):
  if self.custom_journal_entry:
    je_name = self.custom_journal_entry

    try:
      je = frappe.get_doc("Journal Entry", je_name)
      
      if je.docstatus == 1:
          je.cancel()
      
      frappe.delete_doc("Journal Entry", je_name, force=1)
      self.db_set("custom_journal_entry", None)

    except frappe.DoesNotExistError:
      frappe.msgprint(f"Journal Entry {je_name} tidak ditemukan, mungkin sudah dihapus.")
    except Exception as e:
      frappe.throw(f"Gagal menghapus Journal Entry {je_name}: {str(e)}")