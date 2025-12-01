frappe.provide("sth.queries");

sth.queries = {
    item_by_subtype: function (doc) {
        let filters = {}

        if (doc.sub_transaction_type == "Purchase Request" || doc.custom_sub_transaction_type == "Purchase Request") {
            filters = {
                is_stock_item: 1
            }
        }

        return {
            filters
        }
    }
}
