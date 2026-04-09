# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SoundingStockPalmKerneldiBunkerKernel(Document):
	def before_save(self):
		pass

	def split_and_avg(self,arr):
		arr = list(map(int, arr))
		mid = len(arr) // 2
		
		left = arr[:mid + (len(arr) % 2)]
		right = arr[mid:]
		
		return sum(left)/len(left), sum(right)/len(right)
