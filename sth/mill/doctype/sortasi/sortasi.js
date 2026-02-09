// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sortasi", {
	refresh(frm) {

	},
	mentah(frm){
		kalkulasi_tbs(frm)
		kalkukasi_mentah(frm)
		kalkulasi_nilai_panen(frm)
	},
	masak(frm){
		kalkulasi_tbs(frm)
		kalkukasi_masak(frm)
		kalkulasi_nilai_panen(frm)
	},
	terlalu_masak(frm){
		kalkulasi_tbs(frm)
		kalkukasi_terlalu_masak(frm)
		kalkulasi_nilai_panen(frm)
	},
	tandan_kosong(frm){
		kalkulasi_tbs(frm)
		kalkukasi_tandan_kosong(frm)
		kalkulasi_nilai_panen(frm)
	},
	abn(frm){
		kalkulasi_tbs(frm)
		kalkukasi_abn(frm)
		kalkulasi_nilai_panen(frm)
	},
	tpi(frm){
		kalkulasi_tbs(frm)
		kalkukasi_tpi(frm)
		kalkulasi_nilai_panen(frm)
	},
	r_dmg(frm){
		kalkulasi_tbs(frm)
		kalkukasi_r_dmg(frm)
		kalkulasi_nilai_panen(frm)
	},
	brondolan(frm){
		kalkulasi_tbs(frm)
		kalkukasi_brondolan(frm)
		kalkulasi_nilai_panen(frm)
	},
	restan(frm){
		kalkulasi_tbs(frm)
		kalkukasi_restan(frm)
		kalkulasi_nilai_panen(frm)
	},
	spi(frm){
		kalkulasi_tbs(frm)
		kalkukasi_spi(frm)
		kalkulasi_nilai_panen(frm)
	},
	tnr(frm){
		frm.set_value("tenera_kg", frm.doc.netto * frm.doc.tnr / 100)
		kalkulasi_pot_sortasi(frm)
	},
	dura(frm){
		frm.set_value("dura_kg", frm.doc.netto * frm.doc.dura / 100)
		kalkulasi_pot_sortasi(frm)		
	},
	bm_e(frm){
		frm.set_value("buah_mengkal_kg", frm.doc.netto * frm.doc.bm_e / 100)
		kalkulasi_pot_sortasi(frm)
	},
	tp_e(frm){
		frm.set_value("kg_tp", frm.doc.netto * frm.doc.tp_e / 100)
		kalkulasi_pot_sortasi(frm)
	},
	kp(frm){
		frm.set_value("kg_kp", frm.doc.netto * frm.doc.kp / 100)
		kalkulasi_pot_sortasi(frm)
	},
	br(frm){
		frm.set_value("kg_br", frm.doc.netto * frm.doc.br / 100)
		kalkulasi_pot_sortasi(frm)
	},
	tm_e(frm){
		frm.set_value("buah_restan_kg", frm.doc.netto * frm.doc.tm_e / 100)
		kalkulasi_pot_sortasi(frm)
	},
	tbs(frm){
		frm.set_value("kg_mk", frm.doc.netto * frm.doc.tbs / 100)
		kalkulasi_pot_sortasi(frm)
	},
	brd_e(frm){
		frm.set_value("kg_brd", frm.doc.netto * frm.doc.brd_e / 100)
		kalkulasi_pot_sortasi(frm)
	}


});

function kalkulasi_pot_sortasi(frm){
	frm.set_value("potongan_sortasi_external", frm.doc.bm_e+frm.doc.tp_e+frm.doc.kp+frm.doc.br+frm.doc.tm_e+frm.doc.tbs+frm.doc.brd_e)
}

function kalkulasi_tbs(frm){
	if(frm.doc.tipe == "Internal"){
		let total = frm.doc.mentah + frm.doc.masak + frm.doc.terlalu_masak + frm.doc.tandan_kosong + frm.doc.abn
		frm.set_value("total_tbs_internal", total)
	}
}

function kalkukasi_mentah(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_mth", (frm.doc.mentah / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_mth", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_mth == 0){
			nilai = 40
		}
		else if(frm.doc.p_mth > 1 && frm.doc.p_mth <= 3){
			nilai = 10
		}

		frm.set_value("n_mnt", nilai )
	}
}

function kalkukasi_masak(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_msk", (frm.doc.masak / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_msk", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_msk > 95){
			nilai = 10
		}
		else if(frm.doc.p_msk <= 95 && frm.doc.p_msk > 90){
			nilai = 7
		}
		else if(frm.doc.p_msk <= 90 && frm.doc.p_msk > 85){
			nilai = 5
		}		
		frm.set_value("n_msk", nilai )
	}
}

function kalkukasi_terlalu_masak(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_tmsk", (frm.doc.terlalu_masak / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_tmsk", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_tmsk <= 1){
			nilai = 10
		}
		else if(frm.doc.p_tmsk > 1 && frm.doc.p_tmsk <= 3){
			nilai = 7
		}
		else if(frm.doc.p_tmsk > 3 && frm.doc.p_tmsk <= 4){
			nilai = 5
		}

		frm.set_value("n_tmsk", nilai )
	}
}

function kalkukasi_tandan_kosong(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_tk", (frm.doc.tandan_kosong / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_tk", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_tk <= 1){
			nilai = 10
		}
		else if(frm.doc.p_tk > 1 && frm.doc.p_tk <= 2){
			nilai = 7
		}
		else if(frm.doc.p_tk > 2 && frm.doc.p_tk <= 3){
			nilai = 5
		}

		frm.set_value("n_tk", nilai )
	}
}

function kalkukasi_abn(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_abn", (frm.doc.abn / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_abn", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_abn >= 0 && frm.doc.p_abn <= 2){
			nilai = 5
		}
		else if(frm.doc.p_abn > 2 && frm.doc.p_abn <= 5){
			nilai = 3
		}

		frm.set_value("n_abn", nilai )
	}
}

function kalkukasi_tpi(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_tp", (frm.doc.tpi / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_tp", 0);
		}
		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_tp <= 1){
			nilai = 10
		}
		else if(frm.doc.p_tp > 1 && frm.doc.p_tp <= 2){
			nilai = 3
		}
		frm.set_value("n_tp", nilai )
	}
}

function kalkukasi_r_dmg(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_dmg", (frm.doc.r_dmg / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_dmg", 0);
		}
	}
}

function kalkukasi_brondolan(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.netto){
			frm.set_value("p_brd", (frm.doc.brondolan / frm.doc.netto) * 100);
		}
		else{
			frm.set_value("p_brd", 0);
		}

		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_brd > 6){
			nilai = 5
		}
		else if(frm.doc.p_brd > 5 && frm.doc.p_brd <= 6){
			nilai = 3
		}
		else if(frm.doc.p_brd > 3 && frm.doc.p_brd <= 5){
			nilai = 1
		}

		frm.set_value("n_brd", nilai )
	}
}


function kalkukasi_restan(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.total_tbs_internal){
			frm.set_value("p_rst", (frm.doc.restan / frm.doc.total_tbs_internal) * 100);
		}
		else{
			frm.set_value("p_rst", 0);
		}
	}
}

function kalkukasi_spi(frm) {
	if(frm.doc.tipe == "Internal"){
		if(frm.doc.netto){
			frm.set_value("p_smph", (frm.doc.spi / frm.doc.netto) * 100);
		}
		else{
			frm.set_value("p_smph", 0);
		}

		let nilai = "0"
		if(frm.doc.total_tbs_internal == 0){
			nilai = "N/A"
		}
		else if(frm.doc.p_smph >= 0 && frm.doc.p_smph <= 1){
			nilai = 10
		}
		else if(frm.doc.p_smph > 3 && frm.doc.p_smph <= 5){
			nilai = 5
		}
		else if(frm.doc.p_smph > 2){
			nilai = 0
		}

		frm.set_value("n_smph", nilai )
	}
}

function kalkulasi_nilai_panen(frm){
	if(frm.doc.tipe == "Internal"){
		let total = flt(frm.doc.n_mnt) + flt(frm.doc.n_msk) + flt(frm.doc.n_tmsk) + flt(frm.doc.n_tk) + flt(frm.doc.n_abn) + flt(frm.doc.n_tp) + flt(frm.doc.n_brd);
		frm.set_value("nilai_panen", total)
	}
}