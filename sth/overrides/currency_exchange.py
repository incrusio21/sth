import frappe

from erpnext.setup.doctype.currency_exchange.currency_exchange import CurrencyExchange

class CurrencyExchange(CurrencyExchange):
    def validate(self):
        super().validate()
        self.exchange_rate = (self.buying_rate + self.selling_rate) / 2