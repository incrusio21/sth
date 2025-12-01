from io import BytesIO
from base64 import b64encode
from pyqrcode import create as qrcreate
import frappe

@frappe.whitelist()
def validate_create_qr(doc,method):
	generate_qr_for_doc(doc, 1)

def get_qr_svg(data):
	"""Get SVG code to display Qrcode for OTP."""
	url = qrcreate(data)
	svg = ""
	stream = BytesIO()
	try:
		url.svg(stream, scale=4, quiet_zone=1, module_color="#222")
		svg = stream.getvalue().decode().replace("\n", "")
		svg = b64encode(svg.encode())
		print("MAKING QR")
	finally:
		stream.close()

	return svg.decode()

@frappe.whitelist()
def generate_qr_for_doc(doc, dont_save=0):
	data = doc.name
	if doc.doctype == "Driver":
		data = doc.get("custom_license_plate")

	qr_svg_b64 = get_qr_svg(data)

	if hasattr(doc, "custom_qr"):
		doc.custom_qr = qr_svg_b64
		if dont_save == 0:
			doc.save(ignore_permissions=True)

	return qr_svg_b64