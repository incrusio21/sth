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
// frappe.form.link_formatters — termasuk formatter Item bawaan ERPNext yang
// menampilkan "KODE: Nama". Jadi doctype yang tidak disebut di bawah memakai
// kode Item apa adanya, persis keadaan sekarang sebelum satu pun JS doctype
// sempat dimuat.

// Doctype yang menampilkan nama barang, berikut field tempat namanya disimpan.
//
// Sisanya menampilkan kode Item apa adanya. Purchase Order, Purchase Receipt,
// dan Retur Ke Supplier dulu punya formatter sendiri untuk itu; sekarang cukup
// tidak disebut di sini. Retur Ke Supplier memang menampilkan kode walau
// barisnya menyimpan nama_barang — field link-nya sendiri bernama kode_barang.
const FIELD_NAMA_BARANG = {
	"Material Request": "item_name",
	"Pengeluaran Barang": "item_name",
	"Request for Quotation": "item_name",
	"Supplier Quotation": "item_name",
};

frappe.form.link_formatters["Item"] = function (value, doc) {
	if (!doc) {
		return value;
	}

	// Baris tabel anak membawa doctype anaknya sendiri, jadi induknya dikenali
	// lewat parenttype.
	const field = FIELD_NAMA_BARANG[doc.parenttype || doc.doctype];

	// Jatuh ke kode Item kalau namanya belum terisi — mis. baris yang barusan
	// ditambah dan item_name-nya belum sempat ditarik.
	return (field && doc[field]) || value;
};
