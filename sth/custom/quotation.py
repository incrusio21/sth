import frappe

def set_custom_payment_schedule_due_date(doc, method):
  if not doc.get("tanggal_pembayaran"):
    return

  if not doc.get("payment_schedule"):
    doc.append("payment_schedule", {
      "due_date": doc.tanggal_pembayaran,
      "invoice_portion": 100,
    })