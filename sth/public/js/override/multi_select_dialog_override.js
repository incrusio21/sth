frappe.ui.form.MultiSelectDialog = class CustomMultiSelectDialog extends frappe.ui.form.MultiSelectDialog {
    async get_child_result() {
        let filters = [["parentfield", "=", this.child_fieldname]];

        await this.add_parent_filters(filters);
        this.add_custom_child_filters(filters);
        
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
    
    bind_events() {
        let me = this;

        this.$results.on("click", ".list-item-container", function (e) {
            if (!$(e.target).is(":checkbox") && !$(e.target).is("a")) {
                $(this).find(":checkbox").trigger("click");
            }
            let name = $(this).attr("data-item-name").trim();
            if ($(this).find(":checkbox").is(":checked")) {
                me.selected_fields.add(name);
            } else {
                me.selected_fields.delete(name);
            }
        });

        this.$results.on("click", ".list-item--head :checkbox", (e) => {
            let checked = $(e.target).is(":checked");
            this.$results.find(".list-item-container .list-row-check").each(function () {
                $(this).prop("checked", checked);
                const name = $(this).closest(".list-item-container").attr("data-item-name").trim();
                if (checked) {
                    me.selected_fields.add(name);
                } else {
                    me.selected_fields.delete(name);
                }
            });
        });

        this.$parent.find(".input-with-feedback").on("change", () => {
            frappe.flags.auto_scroll = false;
            if (this.is_child_selection_enabled()) {
                this.show_child_results();
            } else {
                this.get_results();
            }
        });

        this.$parent.find('[data-fieldtype="Data"]').on("input", () => {
            var $this = $(this);
            clearTimeout($this.data("timeout"));
            $this.data(
                "timeout",
                setTimeout(function () {
                    frappe.flags.auto_scroll = false;
                    if (me.is_child_selection_enabled()) {
                        me.show_child_results();
                    } else {
                        me.empty_list();
                        me.get_results();
                    }
                }, 300)
            );
        });

        this.$parent.find('[data-fieldtype="Link"]').on("blur", () => {
            var $this = $(this);
            clearTimeout($this.data("timeout"));
            $this.data(
                "timeout",
                setTimeout(function () {
                    frappe.flags.auto_scroll = false;
                    if (me.is_child_selection_enabled()) {
                        me.show_child_results();
                    } else {
                        me.empty_list();
                        me.get_results();
                    }
                }, 300)
            );
        });
    }
};