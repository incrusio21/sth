frappe.ui.form.on("Item Group", {
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.parent_item_group) {
            frm.set_df_property('parent_item_group', 'read_only', 0);
        }
        else{    
            frm.set_df_property('parent_item_group', 'read_only', 1);
        }
        
        if(!frm.is_new()){
            if(frm.doc.persetujuan_1){
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
        }
    },
    
    refresh: function(frm){
        if(!frm.is_new()){
            if(frm.doc.persetujuan_1){
                frm.set_df_property('persetujuan_1', 'read_only', 1);
            }
        }
    },
    
    parent_item_group: function(frm){
        if(frm.is_new() && frm.doc.parent_item_group){
            if(frm.doc.parent_item_group === "All Item Groups"){
                frm.set_value('custom_item_group_code', '');
                frm.set_df_property('custom_item_group_code', 'read_only', 0);
            } else {
                generate_kode_item_group_from_parent(frm);
            }
        }
    }
});

function generate_kode_item_group_from_parent(frm) {
    if(!frm.doc.parent_item_group || frm.doc.parent_item_group === "All Item Groups"){
        return;
    }
    
    frappe.call({
        method: 'sth.overrides.item_group.get_next_group_code_by_parent',
        args: {
            parent_group: frm.doc.parent_item_group
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('custom_item_group_code', r.message);
                frm.set_df_property('custom_item_group_code', 'read_only', 1);
            } else {
                frappe.msgprint(__('Could not generate code. Parent group may not have a code.'));
            }
        }
    });
}