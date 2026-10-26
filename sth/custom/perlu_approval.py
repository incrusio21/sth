import frappe
from frappe import _
from frappe.model.workflow import get_workflow, has_approval_access, is_transition_condition_satisfied


@frappe.whitelist()
def get_jumlah_perlu_approval(filters=None):
	"""Method Number Card tipe Custom. Filter card (filters_config) berisi
	`doctype`; klik card membuka list doctype itu berisi dokumen yang sama."""
	filters = frappe.parse_json(filters) or {}
	doctype = filters.get("doctype")
	if not doctype:
		frappe.throw(_("Filter DocType wajib diisi di Number Card"))

	names = get_dokumen_perlu_approval(doctype)
	return {
		"value": len(names),
		"fieldtype": "Int",
		# view ditulis eksplisit: rute dua bagian dialihkan frappe ke last_view
		# user (mis. Report) tanpa membawa route_options, filternya hilang
		"route": ["List", doctype, "List"],
		# list kosong tetap difilter supaya tidak membuka seluruh dokumen
		"route_options": {"name": ["in", names or [""]]},
	}


def get_dokumen_perlu_approval(doctype, user=None):
	"""Dokumen yang state-nya punya transisi untuk role user, selain transisi
	dari state awal workflow (Draft -> ajukan bukan approval)."""
	user = user or frappe.session.user
	workflow = get_workflow(doctype)
	if not workflow:
		return []

	roles = set(frappe.get_roles(user))
	state_awal = workflow.states[0].state if workflow.states else None
	transisi = [
		t for t in workflow.transitions
		if t.allowed in roles and t.state != state_awal
	]
	if not transisi:
		return []

	state_field = workflow.workflow_state_field
	# get_list menghormati user permission (company/unit) seperti list view
	docs = frappe.get_list(
		doctype,
		filters={state_field: ["in", list({t.state for t in transisi})], "docstatus": ["<", 2]},
		fields=["name", "owner", state_field],
		order_by="modified desc",
		limit_page_length=0,
	)

	ada_kondisi = any(t.condition for t in transisi)
	hasil = []
	for d in docs:
		doc = frappe.get_doc(doctype, d.name) if ada_kondisi else d
		for t in transisi:
			if t.state != d.get(state_field) or not has_approval_access(user, d, t):
				continue
			if t.condition and not is_transition_condition_satisfied(t, doc):
				continue
			hasil.append(d.name)
			break

	return hasil
