// frappe.model.add_to_locals menelusuri setiap array di dokumen non-tabel dan
// memasukkan isinya ke locals. Dokumen DocType dari getdoctype membawa array
// __workflow_docs dan __print_formats, jadi saat meta sebuah doctype pertama kali
// dimuat, Workflow / Print Format miliknya ikut dimasukkan lewat add_to_locals,
// yang menimpa objek lama tanpa melihat apakah dokumen itu sedang terbuka.
//
// Contohnya form Workflow "Approval Expense Claim": form itu memuat meta Expense
// Claim, dan respons meta tersebut membawa Workflow yang sama. Locals lalu berisi
// salinan baru, sedangkan form masih memegang objek lama. Grid menggambar ulang
// baris dari locals, padahal drag menomori ulang baris di frm.doc. Akibatnya nomor
// tidak berubah setelah drag dan urutan yang tersimpan kacau. Kejadiannya hanya
// kalau meta doctype target belum dimuat di tab itu, misalnya tepat setelah save
// Workflow yang membersihkan cache dan memuat ulang halaman.
//
// Array berawalan "__" bukan child table. frappe.meta.sync sudah menyinkronkan
// __workflow_docs dan __print_formats lewat frappe.model.sync, yang memperbarui
// objek yang ada di tempatnya, jadi di sini array itu disembunyikan sementara.

const add_to_locals_asli = frappe.model.add_to_locals;

frappe.model.add_to_locals = function (doc) {
	const disembunyikan = {};

	if (doc && typeof doc === "object") {
		for (const key of Object.keys(doc)) {
			if (key.startsWith("__") && Array.isArray(doc[key])) {
				disembunyikan[key] = doc[key];
				delete doc[key];
			}
		}
	}

	try {
		return add_to_locals_asli.apply(this, arguments);
	} finally {
		if (doc && typeof doc === "object") {
			Object.assign(doc, disembunyikan);
		}
	}
};
