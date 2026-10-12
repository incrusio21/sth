// Aturan Link Title dari Pengaturan Link Title, dibawa boot sebagai
// frappe.boot.sth_link_title (lihat pengaturan_link_title.isi_boot).
//
// Dulu Material Request, Sales Invoice, dan Pertanggungjawaban Perjalanan Dinas
// masing-masing membungkus frappe.utils.get_link_title waktu formnya dibuka, lalu
// memasang kembali fungsi yang mereka simpan begitu route pindah. Yang disimpan
// adalah apa pun yang sedang terpasang saat itu — bisa pembungkus milik berkas
// lain — dan urutan watcher route-nya bergantung form mana yang dibuka duluan.
// Contohnya: buka PPD, lalu Sales Invoice, lalu PPD lagi, lalu menu lain. Watcher
// PPD menyimpan pembungkus Sales Invoice sebagai "asli", Sales Invoice memasang
// fungsi frappe yang sebenarnya, lalu PPD mengembalikan pembungkus Sales Invoice.
// Sejak itu seluruh desk kehilangan judul link sampai halaman dimuat ulang.
//
// Sekarang pembungkusnya dipasang sekali dan tidak menyimpan keadaan apa-apa:
// tiap panggilan melihat route saat itu dan aturan dari boot.

function aturan_link_title() {
	return (frappe.boot && frappe.boot.sth_link_title) || {};
}

// Judul link ke `doctype` disembunyikan kalau route sekarang ada di daftar
// pengecualian. Route-nya dibaca tiap kali, bukan diingat, supaya pindah menu
// tidak pernah meninggalkan apa-apa.
function link_title_disembunyikan(doctype) {
	const disembunyikan = aturan_link_title().disembunyikan || {};
	const route = frappe.get_route() || [];
	const di_doctype = route[1];

	if (!di_doctype || !Object.prototype.hasOwnProperty.call(disembunyikan, di_doctype)) {
		return false;
	}

	// null berarti semua link di doctype itu.
	const daftar = disembunyikan[di_doctype];
	return !daftar || daftar.includes(doctype);
}

function pasang_link_title() {
	const utils = frappe.utils;
	if (!utils || utils.sth_link_title) {
		return;
	}

	const get_asal = utils.get_link_title;
	const fetch_asal = utils.fetch_link_title;

	// Mengembalikan name apa adanya; formatter Link menganggapnya "tanpa title".
	utils.get_link_title = function (doctype, name) {
		if (link_title_disembunyikan(doctype)) return name;
		return get_asal.apply(this, arguments);
	};

	utils.fetch_link_title = function (doctype, name) {
		if (link_title_disembunyikan(doctype)) return Promise.resolve(name);
		return fetch_asal.apply(this, arguments);
	};

	utils.sth_link_title = true;
}

// frappe mengisi link_title_doctypes dari DocType dan Property Setter yang
// bernilai 1, jadi doctype yang JSON-nya menyalakan Link Title tetap terdaftar
// walau master mematikannya. Disaring di sini; filter di tempat supaya semua yang
// sudah memegang array-nya ikut melihat.
function saring_link_title_doctypes() {
	const daftar = frappe.boot && frappe.boot.link_title_doctypes;
	const nonaktif = aturan_link_title().nonaktif || [];
	if (!Array.isArray(daftar) || !nonaktif.length) {
		return;
	}

	for (let i = daftar.length - 1; i >= 0; i--) {
		if (nonaktif.includes(daftar[i])) {
			daftar.splice(i, 1);
		}
	}
}

pasang_link_title();

// frappe.boot belum tentu terisi waktu bundel ini dievaluasi, jadi penyaringan
// diulang di app_ready.
saring_link_title_doctypes();
$(document).on("app_ready", saring_link_title_doctypes);
