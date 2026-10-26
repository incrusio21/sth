// Konfirmasi sebelum workflow action "Revision" di semua doctype.
//
// Tombol action di workflow.js memanggil trigger("before_workflow_action") lalu
// apply_workflow di .then()-nya, tanpa .catch(). Jadi pembungkus di sini cukup
// mengembalikan promise yang tidak pernah selesai kalau user menjawab "Tidak":
// apply_workflow tidak terpanggil dan tidak ada unhandled rejection.
//
// workflow.js sudah memanggil frappe.dom.freeze() sebelum trigger. Lapisan freeze
// menutupi dialog, jadi dilepas dulu selama dialog tampil dan dipasang lagi
// kalau user menjawab "Ya" — finally di workflow.js yang melepasnya nanti.

const trigger_asli = frappe.ui.form.ScriptManager.prototype.trigger;

frappe.ui.form.ScriptManager.prototype.trigger = function (event_name, doctype, name) {
	const frm = this.frm;
	if (event_name !== "before_workflow_action" || frm.selected_workflow_action !== "Revision") {
		return trigger_asli.apply(this, arguments);
	}

	const me = this;
	const args = arguments;
	frappe.dom.unfreeze();
	return new Promise((resolve) => {
		const d = frappe.confirm(
			__("Yakin akan revisi {0}?", [frm.doc.name.bold()]),
			() => {
				frappe.dom.freeze();
				resolve(trigger_asli.apply(me, args));
			},
			() => {
				frm.selected_workflow_action = null;
			}
		);
		d.get_primary_btn().html(__("Ya"));
		d.set_secondary_action_label(__("Tidak"));
	});
};
