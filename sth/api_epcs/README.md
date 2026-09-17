# API EPCS

Endpoint yang dipakai sistem luar (EPCS) untuk bertukar data dengan ERP.

| Berkas | Isi |
| --- | --- |
| `rkh_data.py` | kirim Rencana Kerja Harian ke ERP |
| `timbangan_data.py` | tarik data Timbangan dari ERP |
| `get_data.py` | tarik master Item, Item Group, dan Transaction Type |

Dokumen ini membahas yang pertama.

## Rencana Kerja Harian

```
POST /api/method/sth.api_epcs.rkh_data.create_or_update
```

Satu kiriman = satu dokumen Rencana Kerja Harian. Kegiatan, blok, dan luas
pekerjaannya dikirim sebagai daftar; gudang, penerima material, dan kemandoran
berlaku untuk seluruh dokumen.

`trans_no` adalah patokannya. Kiriman dengan `trans_no` yang sudah pernah masuk
memperbarui dokumen yang sama, bukan melahirkan dokumen baru, jadi request boleh
diulang tanpa takut dobel.

### Contoh kiriman

```bash
curl -X POST "https://erp.example.com/api/method/sth.api_epcs.rkh_data.create_or_update" \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d @rkh.json
```

`rkh.json`:

```json
{
  "trans_no": "RKH/KBN01/2026/09/0042",
  "tanggal_pembuatan": "2026-09-16",
  "posting_date": "2026-09-17",
  "kode_estate": "KBN01",
  "kode_divisi": "KBN01-D1",
  "kode_kemandoran": "KMD-0117",
  "gudang_central": "Gudang Central - KBN01",
  "gudang_virtual": "Gudang Virtual - KBN01",
  "nik_penerima_material": "1206010909900006",
  "kegiatan": [
    {
      "kode_kegiatan": "12660",
      "kode_blok": "A01",
      "luas_pekerjaan": 12.5,
      "tk_laki_laki": 8,
      "tk_perempuan": 4
    },
    {
      "kode_kegiatan": "12666",
      "kode_blok": "A02",
      "luas_pekerjaan": 7.25,
      "tk_laki_laki": 5,
      "tk_perempuan": 3
    }
  ],
  "material": [
    {
      "kode_material": "31201002",
      "jumlah_material": 250,
      "satuan": "Kg"
    },
    {
      "kode_material": "30202001",
      "jumlah_material": 40,
      "satuan": "Ltr"
    }
  ]
}
```

### Contoh balasan

```json
{
  "message": {
    "name": "RKH-17.09.2026-00042",
    "trans_no": "RKH/KBN01/2026/09/0042",
    "docstatus": 1,
    "status": "created",
    "grand_total": 4250000
  }
}
```

Balasan **selalu** memuat `name`, nomor dokumen RKH di ERP, apa pun yang terjadi
dengan kirimannya:

| `status` | Artinya |
| --- | --- |
| `created` | `trans_no` belum pernah masuk, dokumennya baru dibuat |
| `updated` | dokumen lamanya masih draft dan isinya diperbarui |
| `unchanged` | kiriman ulang, isinya sama persis, tidak ada yang diubah |
| `submitted` | dokumennya sudah disubmit, perubahannya tidak bisa masuk; alasannya ada di `message` |

Yang berakhir sebagai error HTTP hanya kiriman yang datanya tidak bisa dipakai
sama sekali: `trans_no` kosong, kode estate tidak ketemu, kegiatan tidak ada di
master, atau mandor/kerani tidak bisa diturunkan dari kemandoran. Di situ memang
belum ada dokumen yang bisa dikembalikan nomornya.

### Field dokumen

| Field EPCS | Field ERP | Wajib | Catatan |
| --- | --- | --- | --- |
| `no_trans` / `no_dokumen` | `trans_no` | ya | patokan create-or-update |
| `tanggal_pembuatan` | `tanggal_pembuatan` | tidak | |
| `tanggal_penggunaan` | `posting_date` | ya | tanggal rencananya dikerjakan |
| `kode_estate` | `unit` | ya | kode pendek atau nama Unit lengkap, dua-duanya diterima |
| `kode_divisi` | `divisi` | ya | |
| `kode_kemandoran` | `gang_code` | ya | dipakai mencari mandor & kerani |
| `gudang_central` | `gudang_central` | tidak | nama Warehouse |
| `gudang_virtual` | `gudang_virtual` | tidak | nama Warehouse |
| `nik_penerima` | `nik_penerima_material` | tidak | NIK karyawan |
| `kegiatan` | `kegiatan_detail` | ya | daftar, minimal satu baris |
| `material` | `material` | tidak | daftar |
| — | `submit` | tidak | `1` (bawaan) langsung disubmit, `0` biarkan draft |

Nama field ERP boleh dipakai langsung sebagai ganti nama EPCS-nya. Kalau keduanya
dikirim sekaligus, yang menang nama ERP-nya.

### Baris kegiatan

| Field EPCS | Field ERP | Wajib |
| --- | --- | --- |
| `kode_kegiatan` | `kegiatan` | ya |
| `kode_blok` | `blok` | ya, kecuali kegiatan bibitan |
| `luas_pekerjaan` | `target_volume` | ya |
| `tk_laki_laki` | `jumlah_tk_laki_laki` | tidak |
| `tk_perempuan` | `jumlah_tk_perempuan` | tidak |

Kategori kegiatan, tipe kegiatan, dan tarif upahnya **tidak perlu dikirim** —
semuanya diambil dari master Kegiatan dan Kegiatan Company tiap kali dokumen
disimpan. Jumlah tenaga kerja dihitung dari laki-laki + perempuan; kalau keduanya
tidak dikirim, dihitung dari luas ÷ volume basis.

### Baris material

| Field EPCS | Field ERP | Wajib |
| --- | --- | --- |
| `kode_material` | `item` | ya |
| `jumlah_material` | `dosis` | ya — total kebutuhan, bukan per hektar |
| `satuan` | `uom` | tidak |

Kategori material diambil dari Item Group, tarifnya dari Rencana Kerja Bulanan
Perawatan yang menaungi kegiatannya, jadi keduanya tidak perlu dikirim.

`satuan` boleh ikut dikirim, tapi nilainya tidak dipakai: `uom` di baris material
selalu diambil ulang dari `stock_uom` master Item. Kalau satuan EPCS berbeda dari
satuan stok ERP, `jumlah_material` harus sudah dikonversi ke satuan stok sebelum
dikirim — tidak ada konversi di sisi ERP.

## Hal yang sering jadi pertanyaan

**Material hilang dari dokumen.** Tabel material hanya bertahan kalau ada
setidaknya satu baris kegiatan yang tipenya Perawatan. Ini aturan lama RKH, bukan
perilaku baru API-nya.

**Kode kegiatan dan kode material diterjemahkan.** Beberapa kode yang dikirim EPCS
adalah kode induk atau kode milik sistem luar, dan dipetakan ke kode ERP-nya lewat
`KEGIATAN_API_MAP` dan `ITEM_API_MAP` di `sth/custom/api.py`. Di contoh di atas,
`12660` masuk sebagai `126600101` dan `31201002` masuk sebagai `30302011`. Kode
baru harus ditambahkan ke daftar itu dan butuh deploy.

**mandor dan kerani tidak ada di payload.** Keduanya wajib di RKH tapi tidak
dikirim EPCS, jadi dicari dari karyawan aktif yang Kode Kemandoran-nya sama dan
jabatannya memuat kata MANDOR / KERANI. Kalau datanya belum rapi, kirim NIK-nya
langsung lewat field `mandor`, `kerani`, atau `mandor1`.

**Dokumen yang sudah disubmit tidak bisa diubah lagi.** Kalau EPCS masih perlu
mengoreksi berkali-kali, kirim `"submit": 0` sampai rencananya final, lalu kirim
sekali lagi tanpa flag itu.

**Baris yang hilang dari kiriman ikut terhapus.** Tabel kegiatan dan material
diisi ulang dari nol tiap kali dikirim. Field dokumen yang tidak ikut di payload
justru dibiarkan apa adanya, tidak dikosongkan.
