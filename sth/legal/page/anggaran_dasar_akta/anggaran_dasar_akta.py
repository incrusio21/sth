# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def get_anggaran_dasar_akta(company=None, anggaran_dasar=None):
    if not (company and anggaran_dasar):
        return

    akta_dict = {}

    saham = frappe.qb.DocType("Detail Form Saham")
    saham_data = (
        frappe.qb.from_(saham)
        .select(
            saham.akta, saham.tanggal_akta, saham.employee,
            saham.qty, saham.rate,
            saham.amount, saham.npwp
        )
        .where(saham.parent == anggaran_dasar)
    ).run()

    for d in saham_data:
        akta = akta_dict.setdefault(d[0], {
            "saham": [],
            "pengurus": [],
            "kriteria": [],
            "details": {}
        })

        akta["saham"].append(
            frappe._dict(zip([
                "tanggal_akta", "nama", 
                "lembar_saham", "nilai_saham", 
                "saham_amount", "npwp"
            ], d[1:], strict=False))
        )

    pengurus = frappe.qb.DocType("Detail Susunan Pengurus dan Komisaris")
    pengurus_data = (
        frappe.qb.from_(pengurus)
        .select(
            pengurus.akta, pengurus.tanggal_akta, pengurus.employee,
            pengurus.designation, pengurus.note,
        )
        .where(pengurus.parent == anggaran_dasar)
    ).run()

    for d in pengurus_data:
        akta = akta_dict.setdefault(d[0], {
            "saham": [],
            "pengurus": [],
            "kriteria": [],
            "details": {}
        })

        akta["pengurus"].append(
            frappe._dict(zip([
                "tanggal_akta", "nama", 
                "designation", "note",
            ], d[1:], strict=False))
        )

    kriteria = frappe.qb.DocType("Angaran Dasar Kriteria")
    kriteria_data = (
        frappe.qb.from_(kriteria)
        .select(
            kriteria.akta, kriteria.kriteria_file, kriteria.kriteria,
        )
        .where(kriteria.parent == anggaran_dasar)
    ).run()

    for d in kriteria_data:
        akta = akta_dict.setdefault(d[0], {
            "saham": [],
            "pengurus": [],
            "kriteria": [],
            "details": {}
        })

        akta["kriteria"].append(
            frappe._dict(zip([
                "kriteria_file", "kriteria"
            ], d[1:], strict=False))
        )

    if not akta_dict:
        return
    
    akta = frappe.qb.DocType("Akta List")
    akta_data = (
        frappe.qb.from_(akta)
        .select(
            akta.name, akta.nomor_akta, akta.tgl_akta, akta.nama_notaris,
            akta.nomor_sk_kehakiman, akta.tanggal_sk_kehakiman,
            akta.kedudukan, akta.alamat, akta.modal_dasar, 
            akta.modal_di_setor, akta.kegiatan_usaha, akta.bnri,
            akta.tbnri, akta.keterangan,
        )
        .where(akta.name.isin(list(akta_dict.keys())))
    ).run()

    for d in akta_data:
        akta_dict[d[0]]["details"] = frappe._dict(zip([
            "nomor_akta", "tanggal_akta", "nama_notaris", 
            "nomor_sk_kehakiman", "tanggal_sk_kehakiman",
            "kedudukan", "alamat", "modal_dasar",
            "modal_di_setor", "kegiatan_usaha", "bnri",
            "tbnri", "keterangan"
        ], d[1:], strict=False))

    return akta_dict