import requests

BASE_URL = "https://dev-erp.sthgroup.com"
API_KEY = "54fe04a950b4506"
API_SECRET = "cc5a8f13c52b70c"


def post_timbangan(payload: dict) -> dict:
	url = f"{BASE_URL}/api/resource/Timbangan"
	headers = {
		"Authorization": f"token {API_KEY}:{API_SECRET}",
		"Content-Type": "application/json",
	}

	response = requests.post(url, json=payload, headers=headers)
	if not response.ok:
		print("Status:", response.status_code)
		print("Body:", response.text)
	response.raise_for_status()
	return response.json()

def execute():
	payload = {
		"trans_no": "WBDTML002260703145353054",
		"docstatus": 1,
		"unit": "TPRM",
		"company": "PT. TRIMITRA LESTARI",
		"posting_date": "2026-07-03",
		"weight_in_time": "14:53:51",
		"weight_out_time": None,
		"type": "Wb Pabrik",
		"ticket_number": "WBDTML002260703145353054",
		"spb": "SPBTML002260703133606506",
		"tujuan_pks": "PKS",
		"total_janjang": 144,
		"total_brondolan": 200,
		"bruto": 7500,
		"tara": 0,
		"netto": 0,
	}
	result = post_timbangan(payload)
	print(result)