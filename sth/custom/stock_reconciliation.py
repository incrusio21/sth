import frappe

def validate_retain_amount(self, method):
    for item in self.items:
        if item.retain_amount:
            if item.current_amount and item.qty and item.qty != 0:
                item.valuation_rate = flt(item.current_amount / item.qty, 
                                         item.precision('valuation_rate'))
                
                item.amount = flt(item.qty * item.valuation_rate, 
                                 item.precision('amount'))