# 1. contract_template.py (in your app's doctype folder)

import frappe
from frappe import _
from frappe.utils.pdf import get_pdf
from frappe.model.document import Document

# requirement
# bench pip install PyPDF2 reportlab
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

class ContractTemplate(Document):
	def generate_pdf(self):
		html = self.get_pdf_html()
		pdf = get_pdf(html, {"margin-bottom": "20mm"})
		
		pdf_with_pages = self.add_page_numbers(pdf)
		return pdf_with_pages
	
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
	
	def get_pdf_html(self):
		content = self.contract_terms or ""
		
		html = f"""
		<!DOCTYPE html>
		<html>
		<head>
			<meta charset="utf-8">
			<style>
				body {{
					font-family: Arial, sans-serif;
					padding: 20px;
					line-height: 1.6;
				}}
			</style>
		</head>
		<body>
			{content}
		</body>
		</html>
		"""
		return html


@frappe.whitelist()
def download_contract_pdf(docname):
	doc = frappe.get_doc('Contract Template', docname)
	pdf = doc.generate_pdf()
	
	frappe.local.response.filename = f"{docname}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "download"

