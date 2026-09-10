// Pertahankan centangan baris anak waktu daftarnya dimuat ulang.
//
// render_child_datatable() bawaan frappe mengosongkan seluruh centangan 500 ms
// sesudah hasil pencarian datang:
//
//     setTimeout(() => {
//         this.child_datatable.rowmanager.checkMap = []
//         this.child_datatable.refresh(this.get_child_datatable_rows())
//     }, 500)
//
// Mengetik di kotak pencarian masuk ke jalur itu lewat debounce 300 ms, jadi
// ada jendela selebar 300 ms + waktu tunggu server + 500 ms saat pemuatan ulang
// yang lama masih mengantre. Centangan yang dibuat di dalam jendela itu ikut
// terhapus, dan yang terlihat orang: centangan pertamanya hilang sendiri
// sesaat setelah diklik. Ikut hilang juga dari Get Items, karena
// get_selected_child_names() membaca checkMap yang sama.
//
// Yang diperbaiki di sini cuma pemuatan ulangnya. Baris yang memang tersaring
// keluar oleh pencarian baru tetap kehilangan centangannya — sama seperti
// sebelumnya, dan memang begitu perilaku dialognya: yang tidak ada di daftar
// tidak bisa diwakili checkMap, yang isinya sejajar dengan baris yang tampil.

frappe.ui.form.MultiSelectDialog = class MultiSelectDialogCheckMap extends (
	frappe.ui.form.MultiSelectDialog
) {
	setup_child_datatable() {
		super.setup_child_datatable();

		this._baris_anak_tampil = this._snapshot_baris_anak();
	}

	render_child_datatable() {
		if (!this.child_datatable) {
			return super.render_child_datatable();
		}

		setTimeout(() => {
			// Dibaca di dalam setTimeout, bukan sebelumnya: centangan yang mau
			// diselamatkan justru yang dibuat selama 500 ms ini.
			const terpilih = this._nama_baris_anak_tercentang();

			// Sekali saja — get_child_datatable_rows() sekalian menyalakan atau
			// mematikan tombol More.
			const baris_tabel = this.get_child_datatable_rows();
			const baris_baru = this._snapshot_baris_anak();

			// Disusun sebelum refresh(), bukan sesudah. Render tabelnya memanggil
			// restoreState() -> highlightCheckedRows(), yang menyalakan kotak
			// centangnya dari checkMap; kalau checkMap baru diisi belakangan,
			// barisnya tercatat tercentang tapi kotaknya kelihatan kosong sampai
			// ada render berikutnya.
			const rowmanager = this.child_datatable.rowmanager;
			rowmanager.checkMap = baris_baru.map((baris) => (terpilih.has(baris.name) ? 1 : 0));

			this.child_datatable.refresh(baris_tabel);
			this.$child_wrapper.find(".dt-scrollable").css("height", "300px");
			this.$child_wrapper.find(".dt-scrollable").css("overflow-y", "scroll");

			this._baris_anak_tampil = baris_baru;

			// Penjaga kalau render-nya tidak sempat memanggil restoreState;
			// idempoten, cuma memasang ulang yang sudah tercatat tercentang.
			rowmanager.highlightCheckedRows();
		}, 500);
	}

	// Baris anak yang sedang ditampilkan tabelnya, objeknya utuh.
	// get_child_datatable_rows() membuang field name (Object.values(d).slice(1)),
	// jadi dari datatable-nya sendiri baris cuma dikenali lewat nomor urut.
	_snapshot_baris_anak() {
		return (this.child_results || []).slice(0, this.child_page_length);
	}

	_nama_baris_anak_tercentang() {
		// Bukan get_selected_child_names(): fungsi itu menerjemahkan checkMap
		// lewat child_results, padahal show_child_results() sudah mengganti
		// child_results sebelum tabelnya sendiri dimuat ulang. Yang sejajar
		// dengan checkMap saat ini adalah baris yang benar-benar tampil.
		const tampil = this._baris_anak_tampil || [];
		const check_map = this.child_datatable.rowmanager.checkMap || [];
		const nama = [];

		check_map.forEach((tercentang, index) => {
			if (tercentang == 1 && tampil[index]) {
				nama.push(tampil[index].name);
			}
		});

		return new Set(nama);
	}
};
