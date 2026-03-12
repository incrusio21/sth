import frappe
 
# ── Configuration ──────────────────────────────────────────────────────────────
SOURCE_COMPANY = "PT. TRIMITRA LESTARI"
 
# All account-link fields on the Company doctype
ACCOUNT_FIELDS = [
	"default_bank_account",
	"default_cash_account",
	"default_receivable_account",
	"default_payable_account",
	"default_expense_account",
	"default_income_account",
	"write_off_account",
	"exchange_gain_loss_account",
	"round_off_account",
	"accumulated_depreciation_account",
	"depreciation_expense_account",
	"expenses_included_in_asset_valuation",
	"disposal_account",
	"capital_work_in_progress_account",
	"asset_received_but_not_billed",
	"default_payroll_payable_account",
	"default_inventory_account",
	"stock_adjustment_account",
	"stock_received_but_not_billed",
	"expenses_included_in_valuation",
	"default_advance_received_account",
	"default_advance_paid_account",
	"default_discount_account",
	"default_deferred_revenue_account",
	"default_deferred_expense_account",
	"tax_withholding_account",
	"unrealized_exchange_gain_loss_account",
	"unrealized_profit_loss_account",
	"inter_company_transaction_reference",
]
# ──────────────────────────────────────────────────────────────────────────────
 
 
def get_company_abbr(company_name):
	return frappe.db.get_value("Company", company_name, "abbr")
 
 
def replace_abbr_in_account(account_name, source_abbr, target_abbr):
	"""
	Replace the trailing abbreviation in an account name.
	e.g. "Sales - RW" with source_abbr="RW", target_abbr="TL"  →  "Sales - TL"
	"""
	if not account_name:
		return None
	suffix = f" - {source_abbr}"
	if account_name.endswith(suffix):
		base = account_name[: -len(suffix)]
		return f"{base} - {target_abbr}"
	# Abbreviation not found at end — return as-is (may cause link error, logged below)
	return account_name
 
 
def account_exists(account_name):
	return frappe.db.exists("Account", account_name)
 
 
def fix_company(target_company, source_abbr, source_accounts):
	target_abbr = get_company_abbr(target_company)
	if not target_abbr:
		print(f"  [SKIP] Could not get abbreviation for '{target_company}'")
		return
 
	print(f"\n→ Processing: {target_company}  (abbr: {target_abbr})")
 
	company_doc = frappe.get_doc("Company", target_company)
	changed = False
	errors = []
 
	for field in ACCOUNT_FIELDS:
		source_value = source_accounts.get(field)
		if not source_value:
			continue  # source company doesn't have this field set either
 
		new_value = replace_abbr_in_account(source_value, source_abbr, target_abbr)
 
		if not account_exists(new_value):
			errors.append(f"    [MISSING] {field}: '{new_value}' does not exist — skipping")
			continue
 
		current_value = company_doc.get(field)
		if current_value == new_value:
			continue  # already correct
 
		print(f"    {field}: '{current_value}' → '{new_value}'")
		company_doc.set(field, new_value)
		changed = True
 
	if errors:
		print("  Warnings (accounts not found in Chart of Accounts):")
		for e in errors:
			print(e)
 
	if changed:
		company_doc.flags.ignore_links = True      # skip re-validation during save
		company_doc.flags.ignore_validate = True
		company_doc.save(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Saved '{target_company}'")
	else:
		print(f"  ✓ No changes needed for '{target_company}'")
 
 
def fix_all():
	# ── 1. Load source company ────────────────────────────────────────────────
	if not frappe.db.exists("Company", SOURCE_COMPANY):
		print(f"[ERROR] Source company '{SOURCE_COMPANY}' not found.")
		return
 
	source_abbr = get_company_abbr(SOURCE_COMPANY)
	source_doc = frappe.get_doc("Company", SOURCE_COMPANY)
	source_accounts = {f: source_doc.get(f) for f in ACCOUNT_FIELDS}
 
	print(f"Source company : {SOURCE_COMPANY}")
	print(f"Source abbr    : {source_abbr}")
	print(f"Source accounts loaded:\n")
	for f, v in source_accounts.items():
		if v:
			print(f"  {f}: {v}")
 
	# ── 2. Get all OTHER companies ────────────────────────────────────────────
	all_companies = frappe.get_all("Company", pluck="name")
	target_companies = [c for c in all_companies if c != SOURCE_COMPANY]
 
	print(f"\nFound {len(target_companies)} other companies to update.\n")
	print("=" * 60)
 
	# ── 3. Process each company ───────────────────────────────────────────────
	for company in target_companies:
		fix_company(company, source_abbr, source_accounts)
 
	print("\n" + "=" * 60)
	print("Done.")
 
 
# Allow running as a script directly in bench console
if __name__ == "__main__":
	fix_all()
 