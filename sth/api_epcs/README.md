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

`rkh.json` — semua kodenya diambil dari master sungguhan (kloning 13 Sep 2026),
jadi payload ini benar-benar jalan, bukan karangan:

```json
{
  "trans_no": "RKH/TMDE01/2026/09/0042",
  "tanggal_pembuatan": "2026-09-16",
  "posting_date": "2026-09-17",
  "kode_estate": "TMDE",
  "kode_divisi": "TMDE01",
  "kode_kemandoran": "TMDE01-MDR-1",
  "gudang_central": "WH-TMDE-CENTRAL-TML",
  "gudang_virtual": "TRPE52-CENTRAL - TML",
  "nik_penerima": "1506010807950002",
  "kegiatan": [
    {
      "kode_kegiatan": "621100204",
      "kode_blok": "G03a",
      "luas_pekerjaan": 15.6,
      "tk_laki_laki": 8,
      "tk_perempuan": 4
    },
    {
      "kode_kegiatan": "621100203",
      "kode_blok": "G03b",
      "luas_pekerjaan": 7.2,
      "tk_laki_laki": 5,
      "tk_perempuan": 3
    }
  ],
  "material": [
    {
      "kode_material": "30301003",
      "jumlah_material": 250,
      "satuan": "LTR"
    },
    {
      "kode_material": "30301011",
      "jumlah_material": 40,
      "satuan": "KG"
    }
  ]
}
```

| Kode | Artinya di master |
| --- | --- |
| `TMDE` / `TMDE01` | Unit dan Divisi, company PT. TRIMITRA LESTARI |
| `TMDE01-MDR-1` | Kemandoran I TMDE01 |
| `G03a` / `G03b` | Blok di divisi itu, luas areal 15,6 dan 7,2 ha |
| `621100204` | SEMPROT PIRINGAN / PSR PIKUL BERBUKIT — Perawatan, basis 3,5, Rp 40.587,70 |
| `621100203` | SEMPROT PIRINGAN / PSR PIKUL DATAR — Perawatan, basis 5,0, Rp 28.411,40 |
| `30301003` / `30301011` | GLIFOSAT 486 G/L (LTR) dan METIL METSULFURON 20PERSEN (KG) |

### Contoh balasan

Ini balasan sungguhan waktu payload di atas dijalankan di kloning:

```json
{
  "message": {
    "name": "RKH-17-09-26-00001",
    "trans_no": "RKH/TMDE01/2026/09/0042",
    "docstatus": 1,
    "status": "created",
    "grand_total": 714343.6
  }
}
```

Dokumen yang terbentuk:

| | |
| --- | --- |
| mandor | `1506011809790003` ABDUL HALIM, MANDOR PERAWATAN — diturunkan dari kemandoran |
| kerani | `1506010807950002` FERRI ANJOLIAN SAPUTRA, KERANI DIVISI — diturunkan dari kemandoran |
| total luas | 22,8 ha |
| tenaga kerja | 20 orang (13 laki-laki, 7 perempuan) |
| baris 1 | 621100204, blok G03a, 12 orang × Rp 40.587,70 = Rp 487.052,40 |
| baris 2 | 621100203, blok G03b, 8 orang × Rp 28.411,40 = Rp 227.291,20 |
| material | dosis 250 LTR dan 40 KG, amount Rp 0 — lihat catatan tarif di bawah |

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

**Tarif material sering nol.** Tarifnya diambil dari Rencana Kerja Bulanan
Perawatan yang menaungi kegiatan itu — kegiatan, divisi, blok, dan tanggalnya
harus jatuh di dalam rentang RKB yang sudah disubmit. Di kloning 13 Sep 2026 belum
ada satu pun RKB Perawatan, jadi seluruh baris material mendarat dengan rate 0 dan
tidak menyumbang apa-apa ke `grand_total`. Ini bukan kesalahan kiriman; RKB-nya
yang memang belum dibuat. Kalau tarifnya mau dipastikan, kirim `rate` sendiri di
baris materialnya.

**Kode kegiatan dan kode material bisa diterjemahkan.** Beberapa kode yang dikirim
EPCS adalah kode induk atau kode milik sistem luar, dan dipetakan ke kode ERP-nya
lewat `KEGIATAN_API_MAP` dan `ITEM_API_MAP` di `sth/custom/api.py` — misalnya
`12660` masuk sebagai `126600101`, `31201002` sebagai `30302011`. Kode yang tidak
ada di dua peta itu diteruskan apa adanya. Kode baru harus ditambahkan ke daftar
itu dan butuh deploy.

**mandor dan kerani tidak ada di payload.** Keduanya wajib di RKH tapi tidak
dikirim EPCS, jadi dicari dari karyawan aktif yang Kode Kemandoran-nya sama dan
`designation_name`-nya memuat kata MANDOR / KERANI. Perhatikan yang dicocokkan
nama jabatannya, bukan field `designation` karyawan — di ERP ini isinya kode
(`MD05`, `KR04`), sementara teks jabatannya ada di master Designation.

**Derivasi itu sering gagal.** Di kloning 13 Sep 2026 cuma **27 dari 112**
kemandoran yang punya mandor sekaligus kerani aktif; 67 punya mandornya saja.
Kalau salah satu tidak ketemu, kirimannya ditolak dengan pesan yang menyebut
kemandorannya. Jalan pastinya: EPCS mengirim NIK-nya langsung lewat field
`mandor`, `kerani`, atau `mandor1`.

**Dokumen yang sudah disubmit tidak bisa diubah lagi.** Kalau EPCS masih perlu
mengoreksi berkali-kali, kirim `"submit": 0` sampai rencananya final, lalu kirim
sekali lagi tanpa flag itu.

**Baris yang hilang dari kiriman ikut terhapus.** Tabel kegiatan dan material
diisi ulang dari nol tiap kali dikirim. Field dokumen yang tidak ikut di payload
justru dibiarkan apa adanya, tidak dikosongkan.
