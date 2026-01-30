
frappe.views.ReportView = class CustomReportView extends frappe.views.ReportView {
	setup_defaults() {
		super.setup_defaults();
		this.page_title = __("") + " " + this.page_title;
		this.view = "Report";
		const route = frappe.get_route();

		if (route.length === 3) {
			return frappe.db.get_list("Report", {
				filters: {
					ref_doctype: route[1],
					name: ["like", "%Report : %"]
				},
				fields: ["name"],
				limit: 1
			}).then((reports) => {
				if (reports && reports.length > 0) {
					route.push(reports[0].name);
				}
				return this.do_setup_defaults(route);
			});
		} else {
			return this.do_setup_defaults(route);
		}
	}

	do_setup_defaults(route) {
		if (route.length === 4) {
			this.report_name = route[3];
		}

		if (this.report_name) {
			return this.get_report_doc().then((doc) => {
				this.report_doc = doc;
				this.report_doc.json = JSON.parse(this.report_doc.json);

				this.filters = this.report_doc.json.filters;
				this.order_by = this.report_doc.json.order_by;
				this.add_totals_row = this.report_doc.json.add_totals_row;
				this.page_title = __(this.report_name);
				this.page_length = this.report_doc.json.page_length || 20;
				this.order_by = this.report_doc.json.order_by || "modified desc";
				this.chart_args = this.report_doc.json.chart_args;
			});
		} else {
			this.add_totals_row = this.view_user_settings.add_totals_row || 0;
			this.chart_args = this.view_user_settings.chart_args;
		}
		return this.get_list_view_settings();
	}
	build_column(c) {
		let [fieldname, doctype] = c;
		let docfield = frappe.meta.docfield_map[doctype || this.doctype][fieldname];

		// group by column
		if (fieldname === "_aggregate_column") {
			docfield = this.group_by_control.get_group_by_docfield();
		}

		// child table index column
		if (fieldname === "idx" && doctype !== this.doctype) {
			docfield = {
				label: "Index",
				fieldtype: "Int",
				parent: doctype,
			};
		}

		const excludedDoctypes = ["Customer", "Supplier", "Item", "Item Group"];
		const excludedFields = ["name", "docstatus", "workflow_state"];

		if (excludedDoctypes.includes(doctype) && excludedFields.includes(fieldname)) {
			return;
		}
		
		if (!docfield) {            
			docfield = frappe.model.get_std_field(fieldname, true);

			if (docfield) {
				if (!docfield.label) {
					docfield.label = toTitle(fieldname);
					if (docfield.label.includes("_")) {
						docfield.label = docfield.label.replace("_", " ");
					}
				}
				docfield.parent = this.doctype;
				if (fieldname == "name") {
					docfield.options = this.doctype;
				}
				if (fieldname == "docstatus" && !frappe.meta.has_field(this.doctype, "status")) {
					docfield.label = "Status";
					docfield.fieldtype = "Data";
					docfield.name = "status";
				}
			   
			}
		}
		if (!docfield || docfield.report_hide) return;

		let title = __(docfield.label, null, docfield.parent);
		if (doctype !== this.doctype) {
			title += ` (${__(doctype)})`;
		}

		const editable =
			frappe.model.is_non_std_field(fieldname) &&
			!docfield.read_only &&
			!docfield.is_virtual;

		const align = (() => {
			const is_numeric = frappe.model.is_numeric_field(docfield);
			if (is_numeric) {
				return "right";
			}
			return docfield.fieldtype === "Date" ? "right" : "left";
		})();

		let id = fieldname;

		// child table column
		if (doctype !== this.doctype && fieldname !== "_aggregate_column") {
			id = `${doctype}:${fieldname}`;
		}

		let width = (docfield ? cint(docfield.width) : null) || null;
		if (this.report_doc) {
			// load the user saved column width
			let saved_column_widths = this.report_doc.json.column_widths || {};
			width = saved_column_widths[id] || width;
		}

		let compareFn = null;
		if (docfield.fieldtype === "Date") {
			compareFn = (cell, keyword) => {
				if (!cell.content) return null;
				if (keyword.length !== "YYYY-MM-DD".length) return null;

				const keywordValue = frappe.datetime.user_to_obj(keyword);
				const cellValue = frappe.datetime.str_to_obj(cell.content);
				return [+cellValue, +keywordValue];
			};
		}
		
		const fieldTypeOverrides = {
			"Customer": {
				"kode_pelanggan": { fieldtype: "Link", options: this.doctype }
			},
			"Supplier": {
				"kode_supplier": { fieldtype: "Link", options: this.doctype }
			},
			"Item": {
				"item_code": { fieldtype: "LinkAwal", options: this.doctype }
			},
			"Item Group": {
				"custom_item_group_code": { fieldtype: "LinkAwal", options: this.doctype }
			}
		};

		let fineditable = editable

		const override = fieldTypeOverrides[doctype]?.[fieldname];
		if (override) {
			docfield.fieldtype = override.fieldtype;
			docfield.options = override.options;
			docfield.read_only = 1;
			fineditable = false
		}
		console.log(fieldname)
		return {
			id: id,
			field: fieldname,
			name: title,
			content: title,
			docfield,
			width,
			fineditable,
			align,
			compareValue: compareFn,
			format: (value, row, column, data) => {
				let doc = null;
				if (Array.isArray(row)) {
					doc = row.reduce((acc, curr) => {
						if (!curr.column.docfield) return acc;

						if (
							curr.column.docfield.fieldtype == "Link" &&
							frappe.boot.link_title_doctypes.includes(
								curr.column.docfield.options
							) &&
							curr.html
						) {
							this.link_title_doctype_fields[curr.content] =
								curr.column.docfield.options;
						}
						acc[curr.column.docfield.fieldname] = curr.content;
						return acc;
					}, {});
				} else {
					doc = row;
				}

				return frappe.format(value, column.docfield, { always_show_decimals: true }, doc);
			},
		};
	}
};