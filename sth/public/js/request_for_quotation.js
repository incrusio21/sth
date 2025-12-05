frappe.ui.form.on('Request for Quotation', {
    refresh(frm) {
        // frm.trigger('remove_listener_edit_item')
    },

    onload_post_render(frm) {
        frm.set_df_property("items", "cannot_add_rows", true)
    },

    remove_listener_edit_item(frm) {
        frm.get_field('items').$wrapper.find('.btn-open-row').off('click')
    }
})
