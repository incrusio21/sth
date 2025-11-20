import frappe

def coba_cek_berapa_lama_backdate(self,method):
	field_date = "posting_date"
	tanggal_perbandingan = self.get(field_date)