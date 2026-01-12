
frappe.views.ReportView = class CustomReportView extends frappe.views.ReportView {
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

        if (!docfield) {
            console.log(doctype)
            console.log(fieldname)
            docfield = frappe.model.get_std_field(fieldname, true);
            console.log(docfield)

            if(doctype == "Customer" && (fieldname == "name" || fieldname == "docstatus")){
                return
            }

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
        
        if(doctype == "Customer" && fieldname == "kode_pelanggan"){
            docfield.fieldtype = "Link";
            docfield.options = this.doctype;
            console.log("PERNAH MASUK SINI")
        }

        return {
            id: id,
            field: fieldname,
            name: title,
            content: title,
            docfield,
            width,
            editable,
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