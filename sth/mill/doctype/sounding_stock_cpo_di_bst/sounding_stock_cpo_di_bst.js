// Copyright (c) 2026, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sounding Stock CPO di BST", {
    setup(frm) {
        erpnext.queries.setup_queries(frm, "Warehouse", function (doc) {
            return {
                filters: {
                    company: doc.company,
                    is_group: 0,
                    unit: doc.unit
                }
            }
        })
    },

    onload(frm) {
        if (!frm.is_new()) return

        new frappe.ui.Scanner({
            dialog: true,
            multiple: false,
            on_scan(data) {
                frm.events.apply_qr_pabrik(frm, data)
            },
        })

        frm.trigger('get_location')
    },

    apply_qr_pabrik(frm, data) {
        // Isi QR pabrik dibuat Mill Master: { pabrik, unit, latitude, longitude }
        const text = data && data.result && data.result.text
        if (!text) return

        let scan_data
        try {
            scan_data = JSON.parse(text)
        } catch (e) {
            scan_data = null
        }

        if (!scan_data || !scan_data.pabrik) {
            frappe.msgprint(__("QR tidak dikenali. Pastikan yang discan adalah QR Pabrik."))
            return
        }

        frm.set_value("pabrik", scan_data.pabrik)
        frm.set_value("pabrik_latitude", scan_data.latitude)
        frm.set_value("pabrik_longitude", scan_data.longitude)

        frm.set_value("tanggal_scan", frappe.datetime.get_today())
        frm.set_value("jam_scan", moment().format('HH:mm:ss'))
        frm.set_value("user_scan", frappe.session.user)
    },

    get_location(frm) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                frm.set_value("latitude", position.coords.latitude)
                frm.set_value("longitude", position.coords.longitude)
            },
            (err) => {
                frappe.msgprint(err.message);
            }
        );
    },

    refresh(frm) {

    },

    get_data(frm) {
        // if (frm.doc.docstatus != 0) return

        frm.call("get_data", { freeze: true, freeze_message: "Getting Data..." })
            .then(() => {
                frm.dirty()
                // frm.refresh()
            })
    },

    calculate_avg_sounding_1(frm) {
        average = (frm.doc.uhst1 + frm.doc.uhst2 + frm.doc.uhst3) / 3
        frm.set_value("ukuran_hasil_sounding", average)
    },

    calculate_avg_sounding_2(frm) {
        average = (frm.doc.uhst1_2 + frm.doc.uhst2_2 + frm.doc.uhst3_2) / 3
        frm.set_value("ukuran_hasil_sounding_2", average)
    },

    calculate_avg_suhu_1(frm) {
        average = (frm.doc.hst1 + frm.doc.hst2 + frm.doc.hst3) / 3
        frm.set_value("hasil_suhu", average)
    },

    calculate_avg_suhu_2(frm) {
        average = (frm.doc.hst1_2 + frm.doc.hst2_2 + frm.doc.hst3_2) / 3
        frm.set_value("hasil_suhu_2", average)
    },

    get_ukuran_sounding(tinggi, bst, pabrik) {
        const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_ukuran_sounding"
        return frappe.xcall(method, { tinggi, bst, pabrik })
    },

    get_berat_jenis_suhu(pabrik = "", suhu) {
        const method = frappe.model.get_server_module_name(cur_frm.doctype) + ".get_berat_jenis"
        return frappe.xcall(method, { pabrik, suhu })
    },


    uhst1: (frm) => frm.trigger('calculate_avg_sounding_1'),
    uhst2: (frm) => frm.trigger('calculate_avg_sounding_1'),
    uhst3: (frm) => frm.trigger('calculate_avg_sounding_1'),

    hst1: (frm) => frm.trigger('calculate_avg_suhu_1'),
    hst2: (frm) => frm.trigger('calculate_avg_suhu_1'),
    hst3: (frm) => frm.trigger('calculate_avg_suhu_1'),

    uhst1_2: (frm) => frm.trigger('calculate_avg_sounding_2'),
    uhst2_2: (frm) => frm.trigger('calculate_avg_sounding_2'),
    uhst3_2: (frm) => frm.trigger('calculate_avg_sounding_2'),

    hst1_2: (frm) => frm.trigger('calculate_avg_suhu_2'),
    hst2_2: (frm) => frm.trigger('calculate_avg_suhu_2'),
    hst3_2: (frm) => frm.trigger('calculate_avg_suhu_2'),

    ukuran_hasil_sounding(frm) {
        frm.events.get_ukuran_sounding(frm.doc.ukuran_hasil_sounding, "BST 01", frm.doc.pabrik || '').then((res) => {
            frm.set_value("ukuran_hasil_sounding_kg", res)
            frm.set_value("tonase_sebenarnya", flt(frm.doc.ukuran_hasil_sounding_kg) * flt(frm.doc.berat_jenis_suhu))
        })
    },

    ukuran_hasil_sounding_2(frm) {
        frm.events.get_ukuran_sounding(frm.doc.ukuran_hasil_sounding_2, "BST 02", frm.doc.pabrik || '').then((res) => {
            frm.set_value("ukuran_hasil_sounding_kg_2", res)
            frm.set_value("tonase_sebenarnya_2", flt(frm.doc.ukuran_hasil_sounding_kg_2) * flt(frm.doc.berat_jenis_suhu_2))
        })
    },

    hasil_suhu(frm) {
        if (!frm.doc.hasil_suhu) return
        frm.events.get_berat_jenis_suhu(frm.doc.pabrik, frm.doc.hasil_suhu).then((res) => {
            frm.set_value("berat_jenis_suhu", res)
        })
    },

    hasil_suhu_2(frm) {
        frm.events.get_berat_jenis_suhu(frm.doc.pabrik, frm.doc.hasil_suhu_2).then((res) => {
            frm.set_value("berat_jenis_suhu_2", res)
        })
    },

    berat_jenis_suhu(frm) {
        frm.set_value("tonase_sebenarnya", flt(frm.doc.ukuran_hasil_sounding_kg) * flt(frm.doc.berat_jenis_suhu))
    },

    berat_jenis_suhu_2(frm) {
        frm.set_value("tonase_sebenarnya_2", flt(frm.doc.ukuran_hasil_sounding_kg_2) * flt(frm.doc.berat_jenis_suhu_2))
    },

    tonase_sebenarnya(frm) {
        frm.trigger('calculate_totals')
    },

    tonase_sebenarnya_2(frm) {
        frm.trigger('calculate_totals')
    },

    produksi_cpo(frm) {
        frm.trigger('calculate_oer_netto')
    },

    tbs_olah(frm) {
        frm.trigger('calculate_oer_netto')
    },

    potongan_sortasi(frm) {
        frm.trigger('calculate_oer_netto')
    },

    calculate_oer_netto(frm) {
        const oer_netto_1 = frm.doc.tbs_olah ? flt(frm.doc.produksi_cpo) / frm.doc.tbs_olah * 100 : 0

        // Dua penjaga, kembaran calculate_oer_netto di sisi server. Penyebut nol:
        // seluruh TBS yang masuk kena potongan sortasi, hasil baginya Infinity.
        // tbs_olah nol: potongan sortasinya sedang menumpuk untuk hari olah
        // berikutnya, penyebutnya negatif dan OER-nya minus tanpa arti.
        const penyebut_netto_2 = flt(frm.doc.tbs_olah) - flt(frm.doc.potongan_sortasi)
        const oer_netto_2 = (flt(frm.doc.tbs_olah) && penyebut_netto_2)
            ? flt(frm.doc.produksi_cpo) / penyebut_netto_2 * 100
            : 0

        frm.set_value("oer_netto_1", oer_netto_1)
        frm.set_value("oer_netto_2", oer_netto_2)
    },

    calculate_totals(frm) {
        // flt di sepanjang sini bukan gaya-gayaan: hasil kali yang salah satu
        // bahannya kosong jadi NaN, dan NaN yang dikirim ke server ditulis JSON
        // sebagai null - di sana jadi None dan penjumlahannya error.
        const total_stock = flt(frm.doc.tonase_sebenarnya) + flt(frm.doc.tonase_sebenarnya_2)
        const total_produksi = (total_stock + flt(frm.doc.pengiriman_cpo)) - flt(frm.doc.stock_awal)
        frm.set_value("stock_bst", total_stock)
        frm.set_value("produksi_cpo", total_produksi)
    },

});
