// Copyright (c) 2026 DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("sth.utils")

sth.utils.EfillingSelector = class EfillingSelector {
    constructor(frm, document_type, submited=null, callback) {
		this.frm = frm;
		this.callback = callback;
        this.document_type = document_type
        this.submited = submited != null ? submited : this.frm.doc.docstatus > 0

		this.render_data();
	}

    make() {
		let label = __("Kriteria Document");
		let primary_label = this.document_no ? __("Update") : __("Add");

		primary_label += " " + label;

		this.dialog = new frappe.ui.Dialog({
			title: this.item?.title || primary_label,
			size: "large",
			fields: this.get_dialog_fields(),
			primary_action_label: primary_label,
			primary_action: () => this.update_kriteria_entries()
		});

		this.dialog.show();
		this.$scan_btn = this.dialog.$wrapper.find(".link-btn");
		this.$scan_btn.css("display", "inline");
	}

    get_dialog_fields() {
		let fields = [];

		fields.push({
			fieldname: "entries",
			fieldtype: "Table",
            cannot_add_rows: this.submited,
			cannot_delete_rows: true,
			allow_bulk_edit: true,
			data: [],
			fields: this.get_dialog_table_fields(),
		});

		return fields;
	}

    get_dialog_table_fields() {
		let me = this;

		let fields = [
            {
                fieldtype: "Data",
                label: __("Kriteria"),
                fieldname: "rincian_dokumen_finance",
                in_list_view: 1,
                read_only: this.submited,
            },
            {
                fieldtype: "Attach",
                label: __("Upload File"),
                fieldname: "upload_file",
                in_list_view: 1,
                read_only: this.submited,
            },
            {
                fieldtype: "check",
                label: __("Mandatory"),
                fieldname: "mandatory",
                read_only: 1,
            },
        ];

		fields.push({
			fieldtype: "Data",
			fieldname: "name",
			label: __("Name"),
			hidden: 1,
		});

		return fields;
	}

    update_kriteria_entries() {
		let entries = this.dialog.get_values().entries;

		frappe
			.call({
				method: "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.add_criteria",
				args: {
					entries: entries,
					document_no: this.document_no,
					doc: this.frm.doc,
				},
			})
			.then((r) => {
				frappe.run_serially([
					() => {
						this.callback && this.callback(r.message);
					},
					() => this.dialog.hide(),
				]);
			});
	}

    render_data() {
        frappe
            .call({
                method: "sth.finance_sth.doctype.kriteria_dokumen_finance.kriteria_dokumen_finance.get_criteria",
                freeze: true,
                args: {
                    voucher_type: this.frm.doc.doctype,
                    voucher_no: this.frm.doc.name,
					doucment_type: this.document_type
                },
            })
            .then((r) => {
                if (r.message) {
                    this.document_no = r.message.document_no
            		this.make();
                    this.set_data(r.message.kriteria);
                }
            });
	}

	set_data(data) {
		data.forEach((d) => {
			d.name = d.child_row || d.name;
			this.dialog.fields_dict.entries.df.data.push(d);
		});

		this.dialog.fields_dict.entries.grid.refresh();
	}
}