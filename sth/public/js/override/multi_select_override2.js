frappe.ui.form.MultiSelectDialog = class CustomMultiSelectDialog extends frappe.ui.form.MultiSelectDialog {
    set_filter_for_children(filters) {
        this.filter_child = this.filter_child || []

        for (const row of this.filter_child) {
            filters.push(row)
        }
    }

    async get_child_result() {
        let filters = [["parentfield", "=", this.child_fieldname]];

        await this.add_parent_filters(filters);
        this.add_custom_child_filters(filters);
        this.set_filter_for_children(filters)

        return frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: this.child_doctype,
                filters: filters,
                fields: ["name", "parent", ...this.child_columns],
                parent: this.doctype,
                limit_page_length: this.child_page_length + 5,
                order_by: "parent",
            },
        });
    }
}