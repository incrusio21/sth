# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns(filters)
	res = get_result(filters)

	return columns, res

def get_result(filters):
	
	return frappe.db.sql(
		f"""
		select 
			p.company, p.unit, p.name as project, p.expected_start_date as date, 
			po.supplier, p.project_name, p.from_project, ifnull(po.grand_total, 0) as amount, p.proposal_type, p.status
		from `tabProject` p
		left join `tabPurchase Order` po on p.purchase_order = po.name 
		where for_proposal = 1 {get_conditions(filters)}
	""",
		filters,
		as_dict=1,
	)

def get_conditions(filters):
	conditions = []

	if filters.get("unit"):
		conditions.append("p.unit = %(unit)s")
	
	if filters.get("supplier"):
		conditions.append("po.supplier = %(supplier)s")

	if filters.get("project"):
		conditions.append("p.name = %(project)s")

	if filters.get("project_name"):
		filters["project_name"] = f"%{filters['project_name']}%"
		conditions.append("p.project_name like %(project_name)s")

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_columns(filters):
	
	columns = [
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
		},
		{
			"label": _("Unit"),
			"fieldname": "unit",
			"fieldtype": "Link",
			"options": "Unit",
		},
		{
			"label": _("Number"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
		},
		{
			"label": _("Number"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
		},
		{
			"label": _("Project"),
			"fieldname": "project_name",
			"fieldtype": "Data",
		},
		{
			"label": _("From Project"),
			"fieldname": "from_project",
			"fieldtype": "Link",
			"options": "Project",
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Pendukung"),
			"fieldname": "pendukung",
			"fieldtype": "Data",
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
		},
	]

	return columns