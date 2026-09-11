// Satu formatter Item untuk seluruh desk, dipilih menurut doctype barisnya.
//
// frappe.form.link_formatters itu satu objek global per muat halaman, dan JS
// doctype dijalankan sekali saja per doctype — form.js: `if (!this.setup_done)
// this.setup()`, bukan tiap kali formnya dibuka. Dulu tujuh berkas doctype
// menulis ke kunci 'Item' yang sama di level modul, jadi yang terakhir dimuat
// menang untuk semua doctype sekaligus: buka Material Request, lalu Purchase
// Order, lalu balik ke Material Request — nama barangnya hilang dan tinggal
// kodenya, sampai halamannya dimuat ulang.
//
// Sekarang penugasannya cuma di sini, dan yang menentukan tampilan adalah
// doctype baris yang sedang digambar, bukan halaman mana yang kebetulan dibuka
// lebih dulu.
//
// Dimuat lewat sth.bundle.js sesudah formatter_override.js, yang mengosongkan
// frappe.form.link_formatters. Jadi doctype yang tidak disebut di bawah memakai
// kode Item apa adanya.
//
// Pemasangannya diulang di app_ready. ERPNext memasang formatter Item-nya
// sendiri — yang menampilkan "KODE: Nama" — di level modul erpnext.bundle.js,
// dan urutan antar-app di app_include_js tidak dijamin: kalau bundel ERPNext
// dimuat sesudah sth.bundle.js, punya kita tertimpa diam-diam dan seluruh desk
// kembali menampilkan judul. Dulu keadaan itu tidak terlihat karena JS tiap
// doctype menimpanya lagi waktu formnya dibuka. desk.js memicu app_ready
// sesudah semua bundel dievaluasi — ERPNext sendiri memakai kait yang sama —
// jadi pemasangan kedua ini pasti menang tanpa bergantung urutan.

// Doctype yang tampilan link Item-nya kita tentukan sendiri: nilainya nama field
// tempat nama barang disimpan, atau null kalau yang mau ditampilkan kode Item apa
// adanya.
//
// Retur Ke Supplier menampilkan kode walau barisnya menyimpan nama_barang —
// field link-nya sendiri memang bernama kode_barang.
const ATURAN = {
	"Delivery Note": null,
	"Material Request": "item_name",
	"Pengeluaran Barang": "item_name",
	"Purchase Order": null,
	"Purchase Receipt": null,
	"Request for Quotation": "item_name",
	"Retur Ke Supplier": null,
	"Sales Order": null,
	"Supplier Quotation": "item_name",
};

function formatter_item(value, doc) {
	if (!doc) {
		return undefined;
	}

	// Baris tabel anak membawa doctype anaknya sendiri, jadi induknya dikenali
	// lewat parenttype.
	const doctype = doc.parenttype || doc.doctype;

	// Doctype yang tidak disebut dibiarkan apa adanya: mengembalikan undefined
	// berarti frappe yang memutuskan, termasuk memakai judul dokumen yang
	// di-cache. Kalau di sini dipulangkan value, seluruh doctype lain — Stock
	// Entry, Sales Invoice, Pick List — ikut berubah dari nama jadi kode,
	// padahal tidak ada yang meminta itu.
	if (!(doctype in ATURAN)) {
		return undefined;
	}

	const field = ATURAN[doctype];

	// Jatuh ke kode Item kalau namanya belum terisi — mis. baris yang barusan
	// ditambah dan item_name-nya belum sempat ditarik.
	return (field && doc[field]) || value;
}

function pasang_formatter_item() {
	frappe.form.link_formatters["Item"] = formatter_item;
}

pasang_formatter_item();

$(document).on("app_ready", pasang_formatter_item);
