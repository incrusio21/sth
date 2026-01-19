// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("sth.ConfigureColumn");

sth.ConfigureColumn.Controller = class {
    constructor(wrapper, opts) {
        let me = this
        
        Object.assign(this, opts);
		this.wrapper = $(wrapper).html(`<div class="column-editor"></div>`);

        if(!this.doctype) return
		this.doctype += " Item"
		
        frappe.model.with_doctype(this.doctype, function () {
            me.docfields = frappe.meta.get_docfields(me.doctype, "items")
            me.prepare_wrapper_for_columns();
            me.render_selected_columns();

            $(me.wrapper)
            	.find(".add-new-fields")
            	.click(() => {
            		me.column_selector_for_dialog();
            	});
		});
	}

    prepare_wrapper_for_columns() {
		$(`
			<div class='form-group'>
				<div class='row' style='margin-bottom:10px;'>
					<div class='col-1'></div>
					<div class='col-6' style='padding-left:20px;'>
						${__("Fieldname").bold()}
					</div>
					<div class='col-4'>
						${__("Column Width").bold()}
					</div>
					<div class='col-1'></div>
				</div>
				<div class='control-input-wrapper selected-fields'>
				</div>
				<p class='help-box small text-muted'>
					<a class='add-new-fields text-muted'>
						+ ${__("Add / Remove Columns")}
					</a>
				</p>
			</div>
		`).appendTo(this.wrapper);
	}

    column_selector_for_dialog() {
		let docfields = this.prepare_columns_for_dialog(
			this.frm.doc[this.fields].map((field) => field.fieldname)
		);

		let d = new frappe.ui.Dialog({
			title: __("{0} Fields", [__(this.doctype)]),
			fields: [
				{
					label: __("Select Fields"),
					fieldtype: "MultiCheck",
					fieldname: "fields",
					options: docfields,
					columns: 2,
					sort_options: false,
				},
			],
			secondary_action_label: __("Select All"),
			secondary_action: () => this.select_all_columns(docfields),
		});

		d.set_primary_action(__("Add"), () => {
			let selected_fields = d.get_values().fields;
			this.frm.doc[this.fields] = [];
			if (selected_fields) {
				selected_fields.forEach((selected_column) => {
					let docfield = frappe.meta.get_docfield(this.doctype, selected_column);
					this.update_default_colsize(docfield);
                    
                    let row = this.frm.add_child(this.fields);
                    row.fieldname = selected_column;
                    row.columns = docfield.columns || docfield.colsize;
				});

				this.render_selected_columns();
				d.hide();
			}
		});

		d.show();
	}

    prepare_columns_for_dialog(selected_fields) {
		let fields = [];

		const blocked_fields = frappe.model.no_value_type;
		const always_allow = ["Button"];

		const show_field = (f) => always_allow.includes(f) || !blocked_fields.includes(f);

		// First, add selected fields
		selected_fields.forEach((selectedField) => {
			const selectedColumn = this.docfields.find(
				(column) => column.fieldname === selectedField
			);
			if (selectedColumn && !selectedColumn.hidden && show_field(selectedColumn.fieldtype)) {
				fields.push({
					label: __(selectedColumn.label, null, this.doctype),
					value: selectedColumn.fieldname,
					checked: true,
				});
			}
		});

		// Then, add the rest of the fields
		this.docfields.forEach((column) => {
			if (
				!selected_fields.includes(column.fieldname) &&
				!column.hidden &&
				show_field(column.fieldtype)
			) {
				fields.push({
					label: __(column.label, null, this.doctype),
					value: column.fieldname,
					checked: false,
				});
			}
		});

		return fields;
	}

    update_default_colsize(df) {
		var colsize = 2;
		switch (df.fieldtype) {
			case "Text":
				break;
			case "Small Text":
				colsize = 3;
				break;
			case "Check":
				colsize = 1;
		}
		df.colsize = colsize;
	}

    select_all_columns(docfields) {
		docfields.forEach((docfield) => {
			if (docfield.checked) {
				return;
			}
			$(`.checkbox.unit-checkbox input[type="checkbox"][data-unit="${docfield.value}"]`)
				.prop("checked", true)
				.trigger("change");
		});
	}

    render_selected_columns() {
		let fields = "";
		if (this.frm.doc[this.fields]) {
			this.frm.doc[this.fields].forEach((d) => {
				let docfield = frappe.meta.get_docfield(this.doctype, d.fieldname);

				fields += `
					<div class='control-input flex align-center form-control fields_order sortable-handle sortable'
						style='display: block; margin-bottom: 5px; padding: 0 8px; cursor: pointer; height: 32px;' data-fieldname='${
							docfield.fieldname
						}'
						data-label='${docfield.label}' data-type='${docfield.fieldtype}'>

						<div class='row'>
							<div class='col-1' style='padding-top: 4px;'>
								<a style='cursor: grabbing;'>${frappe.utils.icon("drag", "xs")}</a>
							</div>
							<div class='col-6' style='padding-top: 5px;'>
								${__(docfield.label, null, docfield.parent)}
							</div>
							<div class='col-4' style='padding-top: 2px; margin-top:-2px;' title='${__("Columns")}'>
								<input class='form-control column-width my-1 input-xs text-right'
								style='height: 24px; max-width: 80px; background: var(--bg-color);'
									value='${cint(d.columns) || docfield.columns}'
									data-fieldname='${docfield.fieldname}' style='background-color: var(--modal-bg); display: inline'>
							</div>
							<div class='col-1' style='padding-top: 3px;'>
								<a class='text-muted remove-field' data-fieldname='${docfield.fieldname}'>
									<i class='fa fa-trash-o' aria-hidden='true'></i>
								</a>
							</div>
						</div>
					</div>`;
			});
		}

		$(this.wrapper).find(".selected-fields").html(fields);

		this.prepare_handler_for_sort();
		this.select_on_focus();
		this.update_column_width();
		this.remove_selected_column();
	}

    prepare_handler_for_sort() {
		new Sortable($(this.wrapper).find(".selected-fields")[0], {
			handle: ".sortable-handle",
			draggable: ".sortable",
			onUpdate: () => {
				this.sort_columns();
			},
		});
	}

    select_on_focus() {
		$(this.wrapper)
			.find(".column-width")
			.click((event) => {
				$(event.target).select();
			});
	}

    update_column_width() {
		$(this.wrapper)
			.find(".column-width")
			.change((event) => {
				if (cint(event.target.value) === 0) {
					event.target.value = cint(event.target.defaultValue);
					frappe.throw(__("Column width cannot be zero."));
				}

				this.frm.doc[this.fields].forEach((row) => {
					if (row.fieldname === event.target.dataset.fieldname) {
						frappe.model.set_value(row.doctype, row.name, "columns", cint(event.target.value))
						event.target.defaultValue = cint(event.target.value);
					}
				});
			});
	}

    remove_selected_column() {
		$(this.wrapper)
			.find(".remove-field")
			.click((event) => {
				let fieldname = event.currentTarget.dataset.fieldname;
				let selected_columns_for_grid = this.frm.doc[this.fields].filter((row) => {
					return row.fieldname !== fieldname;
				});

				// if (selected_columns_for_grid && selected_columns_for_grid.length === 0) {
				// 	frappe.throw(__("At least one column is required to show in the grid."));
				// }

				this.frm.set_value(this.fields, selected_columns_for_grid)
				$(this.wrapper).find(`[data-fieldname="${fieldname}"]`).remove();
			});
	}

    sort_columns() {
		this.frm.doc[this.fields] = [];

		let columns = $(this.wrapper).find(".fields_order") || [];
		columns.each((idx) => {
			let row = this.frm.add_child(this.fields);
			row.fieldname = $(columns[idx]).attr("data-fieldname");
			row.columns = cint($(columns[idx]).find(".column-width").attr("value"));
		});
	}
}