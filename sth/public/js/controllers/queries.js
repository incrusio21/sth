frappe.provide("sth.queries");

sth.queries = {
    item_by_subtype: function (doc) {
        let filters = {}

        if (doc.sub_purchase_type == "Purchase Request") {
            filters = {
                is_stock_item: 1
            }
        } else if (doc.sub_purchase_type == "Service Request") {
            filters = {
                is_stock_item: 0
            }
        }

        return {
            filters
        }
    }
}
