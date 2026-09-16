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
	"BOM": null,
	"Delivery Note": null,
	"Delivery Order": null,
	"Material Request": "item_name",
	"Pengeluaran Barang": "item_name",
	"Pick List": null,
	"Proposal": null,
	"Purchase Invoice": null,
	"Purchase Order": null,
	"Purchase Receipt": null,
	"Quotation": null,
	"Request for Quotation": "item_name",
	"Retur Ke Supplier": null,
	"Sales Order": null,
	"Stock Entry": null,
	"Subcontracting Order": null,
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
	// di-cache. Kalau di sini dipulangkan value, seluruh doctype lain — Sales
	// Invoice, Journal Entry, Pick List — ikut berubah dari nama jadi kode,
	// padahal tidak ada yang meminta itu.
	//
	// Harganya ditanggung doctype yang memanggil
	// `frm.set_indicator_formatter("item_code")` tanpa argumen get_text: form.js
	// baris 1823 memanggil formatter ini langsung untuk merangkai label
	// indikator dan **tidak menjaga hasilnya** — beda dengan jalur Link
	// formatter di formatter_override.js yang pakai `if (diformat)`. undefined
	// di sana jatuh ke `${label}` dan tercetak sebagai kata "undefined" di
	// kolom Item.
	//
	// Jadi setiap doctype berindikator item_code wajib punya barisnya sendiri di
	// ATURAN walau isinya null. Yang sekarang memakainya: Stock Entry, Quotation,
	// Purchase Invoice, Pick List, Subcontracting Order, BOM, Material Request,
	// Request for Quotation, Supplier Quotation, Purchase Order, Sales Order,
	// Delivery Note (ERPNext), dan Proposal (sth). Kalau nanti ada doctype baru
	// yang memasang indikator item_code, daftarkan di sini.
	if (!(doctype in ATURAN)) {
		return undefined;
	}

	const field = ATURAN[doctype];

	// Jatuh ke kode Item kalau namanya belum terisi — mis. baris yang barusan
	// ditambah dan item_name-nya belum sempat ditarik.
	return (field && doc[field]) || value;
}

// Sel diamnya lewat formatter di atas, tapi kotak isiannya tidak. ControlLink
// menampilkan judul dokumen — untuk Item berarti item_name — kalau doctype-nya
// masuk frappe.boot.link_title_doctypes, dan Item punya Property Setter
// show_title_field_in_link. Akibatnya kolom "Kode Barang" berubah jadi nama
// barang begitu selnya disentuh, dan di Purchase Receipt itulah yang kelihatan
// sepanjang baris sedang diisi.
//
// Aturannya diambil dari tabel yang sama: doctype yang nilainya null minta kode,
// jadi kotaknya pun kode. Yang memetakan ke field nama tetap memakai judul,
// begitu juga doctype yang tidak terdaftar.
function pasang_is_title_link() {
	const kelas = frappe.ui && frappe.ui.form && frappe.ui.form.ControlLink;

	// Sekali saja. pasang_formatter_item dipanggil dua kali — level modul dan
	// app_ready — dan membungkus dua lapis bikin pemanggilan asalnya berantai.
	if (!kelas || kelas.prototype.sth_is_title_link) {
		return;
	}

	const asal = kelas.prototype.is_title_link;

	kelas.prototype.is_title_link = function () {
		if (this.get_options() === "Item") {
			// Baris tabel anak membawa doctype anaknya sendiri, sama seperti di
			// formatter. Kontrol di dialog atau filter tidak punya doc sama
			// sekali, dan itu jatuh ke perilaku asal.
			const doctype = this.doc && (this.doc.parenttype || this.doc.doctype);

			if (doctype && ATURAN[doctype] === null) {
				return false;
			}
		}

		return asal.call(this);
	};

	kelas.prototype.sth_is_title_link = true;
}

function pasang_formatter_item() {
	frappe.form.link_formatters["Item"] = formatter_item;
	pasang_is_title_link();
}

pasang_formatter_item();

$(document).on("app_ready", pasang_formatter_item);
