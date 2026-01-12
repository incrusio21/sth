frappe.ui.form.MultiSelectDialog = class CustomMultiSelectDialog extends frappe.ui.form.MultiSelectDialog {
    async get_child_result() {
        let filters = [["parentfield", "=", this.child_fieldname]];

        await this.add_parent_filters(filters);
        this.add_custom_child_filters(filters);

        console.log(this.child_doctype == "Material Request Item")
        
        if(this.child_doctype == "Material Request Item"){
            
            return frappe.call({
                method: "sth.overrides.get_list_custom.get_filtered_list",
                args: {
                    doctype: this.child_doctype,
                    filters: filters,
                    fields: ["name", "parent", ...this.child_columns],
                    parent: this.doctype,
                    limit_page_length: this.child_page_length + 5,
                    order_by: "parent",
                    // Add your custom modifications
                },
            });
        }
        else{
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
};