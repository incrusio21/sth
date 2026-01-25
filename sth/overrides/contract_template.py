# 1. contract_template.py (in your app's doctype folder)
import base64
import contextlib
import io
import mimetypes
import os
import subprocess
from urllib.parse import parse_qs, urlparse
from packaging.version import Version

from bs4 import BeautifulSoup

import frappe
from frappe import _
from frappe.utils import cstr, scrub_urls
from frappe.utils.pdf import (
	PDF_CONTENT_ERRORS,
	cleanup,
	get_wkhtmltopdf_version,
	get_file_data_from_writer,
	prepare_options,
)
from frappe.model.document import Document
from frappe.website.serve import get_response_without_exception_handling

from frappe.www.printview import get_print_format, get_print_style

import pdfkit
from pypdf import PdfReader, PdfWriter

# requirement
# bench pip install PyPDF2 reportlab
# from io import BytesIO
# from PyPDF2 import PdfReader, PdfWriter
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
# from reportlab.platypus import Table, TableStyle, Paragraph
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib import colors
# from reportlab.lib.colors import HexColor

class ContractTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.crm.doctype.contract_template_fulfilment_terms.contract_template_fulfilment_terms import ContractTemplateFulfilmentTerms
		from frappe.types import DF

		contract_terms: DF.TextEditor | None
		fulfilment_terms: DF.Table[ContractTemplateFulfilmentTerms]
		is_group: DF.Check
		lft: DF.Int
		old_parent: DF.Link | None
		parent_contract_template: DF.Link | None
		requires_fulfilment: DF.Check
		rgt: DF.Int
		title: DF.Data | None
	# end: auto-generated types
	
	def add_page_numbers(self, pdf_content):
		
		pdf_reader = PdfReader(BytesIO(pdf_content))
		pdf_writer = PdfWriter()
		
		total_pages = len(pdf_reader.pages)
		
		width, height = A4

		for page_num in range(total_pages):
			page = pdf_reader.pages[page_num]
			
			packet = BytesIO()
			can = canvas.Canvas(packet, pagesize=A4)
			
			# buat selain halaman 1
			if page_num != 0: 
				page_text = f"{page_num + 1}"
				# Position options (choose one):
				# Bottom Center:
				# can.drawCentredString(A4[0] / 2, 30, page_text)
				
				# Bottom Right:
				can.drawRightString(width - 70, 30, page_text)
				
				# Bottom Left:
				# can.drawString(50, 30, page_text)

				# Add a line above page number (optional):
				# can.setStrokeColor(HexColor("#CCCCCC"))
				# can.setLineWidth(0.5)
				# can.line(50, 40, A4[0] - 50, 40)
				# ======================

				# Tabel Paraf
				# ======================
				styles = getSampleStyleSheet()

				data = [
					[Paragraph("<b>Paraf</b>", styles["Normal"]), ""],
					[Paragraph("<b>Pihak 1</b>", styles["Normal"]),
					Paragraph("<b>Pihak 2</b>", styles["Normal"])],
					["", ""],
				]

				table = Table(
					data,
					colWidths=[100, 100],
					rowHeights=[100, 100, 150]
				)

				table.setStyle(TableStyle([
					("SPAN", (0, 0), (1, 0)),  # Paraf span 2 kolom
					("ALIGN", (0, 0), (-1, 1), "CENTER"),
					("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

					("BOX", (0, 0), (-1, -1), 1, colors.black),
					("INNERGRID", (0, 0), (-1, -1), 1, colors.black),

					("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
					("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
				]))

				# Posisi kanan bawah
				table.wrapOn(can, width, height)
				table.drawOn(
					can,
					width - 90 * mm,   # kanan
					5 * mm             # bawah
				)


			# Set font and color
			can.setFont("Courier", 9)
			can.setFillColor(HexColor("#666666"))
			
			can.save()
			packet.seek(0)
			page_number_pdf = PdfReader(packet)
			page.merge_page(page_number_pdf.pages[0])
			
			pdf_writer.add_page(page)
		
		output = BytesIO()
		pdf_writer.write(output)
		output.seek(0)
		
		return output.read()
	
def get_pdf(html, cover, options=None, output: PdfWriter | None = None):
	html = scrub_urls(html)
	html, options = prepare_options(html, options)

	options.update({"disable-javascript": "", "disable-local-file-access": ""})

	filedata = ""
	if Version(get_wkhtmltopdf_version()) > Version("0.12.3"):
		options.update({"disable-smart-shrinking": ""})

	try:
		# Set filename property to false, so no file is actually created
		filedata = pdfkit.from_string(html, options=options or {}, cover=cover, cover_first=True, verbose=True)

		# create in-memory binary streams from filedata and create a PdfReader object
		reader = PdfReader(io.BytesIO(filedata))
	except OSError as e:
		if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
			if not filedata:
				print(html, options)
				frappe.throw(_("PDF generation failed because of broken image links"))

			# allow pdfs with missing images if file got created
			if output:
				output.append_pages_from_reader(reader)
		else:
			raise
	finally:
		cleanup(options)

	if "password" in options:
		password = options["password"]

	if output:
		output.append_pages_from_reader(reader)
		return output

	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	if "password" in options:
		writer.encrypt(password)

	filedata = get_file_data_from_writer(writer)

	return filedata

def generate_pdf(doc, print_format):
	html = get_pdf_html(doc, print_format)
	cover = get_cover(doc.contract_cover)

	pdf = get_pdf(html, cover)
	
	# pdf_with_pages = self.add_page_numbers(pdf)
	return pdf

def get_pdf_html(doc, print_format_name):
	print_format = frappe.get_doc("Print Format", print_format_name)
	jenv = frappe.get_jenv()
	
	body = jenv.from_string(get_print_format(doc.doctype, print_format)).render({"doc": doc})
	
	html = jenv.get_template("legal/pdfview.html").render({
		"body": body,
		"print_style": get_print_style(None, print_format),
	})
	
	return html

def get_cover(html):
	if not html:
		return None
	
	soup = BeautifulSoup(html, "html.parser")
	text = soup.get_text(strip=True)

	if not text:
		return None
	
	wrapper = soup.find("div", class_="ql-editor")
	if wrapper:
		wrapper.unwrap()   # HAPUS TAG, ISI TETAP

	html = f"""<html>
			<body>
				{soup}
			</div>
		</html>
	"""
	# create temp file
	fname = os.path.join("/tmp", f"frappe-pdf-{frappe.generate_hash()}.html")
	with open(fname, "wb") as f:
		f.write(html.encode("utf-8"))
	
	return fname
	
@frappe.whitelist()
def download_contract_pdf(doctype, docname, print_format):
	doc = frappe.get_doc(doctype, docname)
	pdf = generate_pdf(doc, print_format)
	
	frappe.local.response.filename = f"{docname}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"

