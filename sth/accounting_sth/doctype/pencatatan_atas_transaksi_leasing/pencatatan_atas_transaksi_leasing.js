// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pencatatan Atas Transaksi Leasing", {
	refresh(frm) {
		set_filter(frm)
	},
	company(frm) {
		set_filter(frm)
	},
	 hitung: function(frm) {
        let tanggal_efektif  = frm.doc.tanggal_efektif;
        let tanggal_pelunasan = frm.doc.tanggal_pelunasan;
        let harga             = flt(frm.doc.harga);
        let uang_muka         = flt(frm.doc.uang_muka);
        let tingkat_suku_bunga = flt(frm.doc.tingkat_suku_bunga);
        let biaya_admin       = flt(frm.doc.biaya_admin);
        let survey            = flt(frm.doc.survey);
        let asuransi          = flt(frm.doc.asuransi);          
        let provisi           = flt(frm.doc.provisi);
        let denda_keterlambatan = flt(frm.doc.denda_keterlambatan);

        if (!tanggal_efektif || !tanggal_pelunasan) {
            frappe.msgprint({ title: 'Perhatian', indicator: 'orange',
                message: 'Harap isi Tanggal Efektif dan Tanggal Pelunasan.' });
            return;
        }
        if (harga <= 0) {
            frappe.msgprint({ title: 'Perhatian', indicator: 'orange',
                message: 'Harap isi Harga.' });
            return;
        }

        let start = frappe.datetime.str_to_obj(tanggal_efektif);
        let end   = frappe.datetime.str_to_obj(tanggal_pelunasan);

        let totalBulan = (end.getFullYear() - start.getFullYear()) * 12
                       + (end.getMonth() - start.getMonth());
        if (end.getDate() < start.getDate()) totalBulan -= 1;

        if (totalBulan <= 0) {
            frappe.msgprint({ title: 'Perhatian', indicator: 'red',
                message: 'Tanggal Pelunasan harus lebih besar dari Tanggal Efektif.' });
            return;
        }

        let pokok_pinjaman   = harga - uang_muka;             
        let cicilan_pokok    = pokok_pinjaman / totalBulan;   

        let bunga_per_bulan  = (pokok_pinjaman * (tingkat_suku_bunga / 100)) / 12;

        let premi_per_bulan  = asuransi / 100 * harga / totalBulan;  
        let total_cicilan    = cicilan_pokok + bunga_per_bulan + premi_per_bulan;    
        let denda_telat      = denda_keterlambatan / 100 * (cicilan_pokok + bunga_per_bulan)

        frm.clear_table('pencatatan_atas_transaksi_leasing_table');

        let saldo_awal = pokok_pinjaman;
        let bulan_iter = new Date(start.getFullYear(), start.getMonth(), 1);

        for (let i = 0; i < totalBulan; i++) {
            let saldo_akhir = saldo_awal - cicilan_pokok;

            let nama_bulan = bulan_iter.toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
            let kontrak    = `Bulan ke-${i + 1} (${nama_bulan})`;

            let row = frm.add_child('pencatatan_atas_transaksi_leasing_table');
            row.kontrak        = kontrak;
            row.saldo_awal     = flt(saldo_awal, 2);
            row.cicilan_pokok  = flt(cicilan_pokok, 2);
            row.bunga_cicilan  = flt(bunga_per_bulan, 2);
            row.premi_asuransi = flt(premi_per_bulan, 2);
            row.total_cicilan  = flt(total_cicilan, 2);
            row.denda_telat    = flt(denda_telat, 2); 
            row.saldo_akhir    = flt(saldo_akhir < 0 ? 0 : saldo_akhir, 2);

            saldo_awal = saldo_akhir;
            bulan_iter.setMonth(bulan_iter.getMonth() + 1);
        }

        frm.refresh_field('pencatatan_atas_transaksi_leasing_table');
    }
});


function set_filter(frm){
	frm.set_query('unit', function() {
		return {
			filters: [
				['Unit', 'company', '=', frm.doc.company]
			]
		};
	});
}
