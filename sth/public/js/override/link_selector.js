frappe.ui.form.LinkSelector = class CustomLinkSelector extends frappe.ui.form.LinkSelector {
    make() {
        var me = this;

        this.start = 0;
        this.page_length = 10;
        this.dialog = new frappe.ui.Dialog({
            title: __("Select {0}", [this.doctype == "[Select]" ? __("value") : __(this.doctype)]),
            size: "extra-large", //tambahan disini
            fields: [
                {
                    fieldtype: "Data",
                    fieldname: "txt",
                    label: __("Beginning with"),
                    description: __("You can use wildcard %"),
                },
                {
                    fieldtype: "HTML",
                    fieldname: "results",
                },
                {
                    fieldtype: "Button",
                    fieldname: "more",
                    label: __("More"),
                    click: () => {
                        me.start += me.page_length;
                        me.search();
                    },
                },
            ],
            primary_action_label: __("Search"),
            primary_action: function () {
                me.start = 0;
                me.search();
            },
        });

        if (this.txt) this.dialog.fields_dict.txt.set_input(this.txt);

        this.dialog.get_input("txt").on("keypress", function (e) {
            if (e.which === 13) {
                me.start = 0;
                me.search();
            }
        });
        this.dialog.show();
        this.search();
    }
}