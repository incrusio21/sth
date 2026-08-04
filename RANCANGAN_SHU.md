# Rancangan Modul SHU / Perhitungan KUD

Dokumen serah-terima. Disusun 30 Juli 2026 dari sesi brainstorming, supaya sesi
berikutnya bisa lanjut tanpa mengulang analisis.

---

## 1. Apa yang dibangun

Perhitungan bagi hasil TBS antara company (mis. PT Trimitra Lestari) dan mitra
Bumdes/KUD (mis. Bumdes Jabung Cipta Usaha). Sekarang dikerjakan di Excel.

Tiga doctype baru:

| Doctype | Cakupan | Peran |
|---|---|---|
| `Masa SHU` | per (company, tahun, bulan), **submittable** | Pembagian tanggal jadi masa |
| `Master Harga SHU` | per (company, tahun), **tidak submittable** | Matriks harga masa × tahun tanam |
| `Perhitungan KUD` | per (company, mitra, bulan) | Dokumen hasil, dicetak & ditandatangani |

Ditambah satu laporan **Tanggal Tanpa Harga SHU** yang statusnya wajib (alasannya di §5).

### Sumber Excel

- `C:\Users\chand\Downloads\STH\EXCEL\data untuk SHU claude.xlsx` — sheet Master Harga saja
- `C:\Users\chand\Downloads\STH\EXCEL\2026-01-31 - TML - SHU BUMDES JABUNG - ERP.xlsx` — 88 sheet;
  yang relevan cuma **PERHITUNGAN KUD** (sheet1) dan **Master Harga** (sheet2)

Tidak ada Python di mesin ini. Untuk membaca xlsx, ekstrak sebagai zip lalu baca
`xl/worksheets/sheetN.xml` + `xl/sharedStrings.xml` (PowerShell `[xml]` sudah cukup).
Peta nama sheet ke file ada di `xl/_rels/workbook.xml.rels`; atribut `r:id` bernamespace,
jadi harus dibaca lewat `GetAttribute('id', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')`.

---

## 2. Status: apa yang sudah jadi

### Selesai — `Masa SHU`

```
sth/plantation/doctype/masa_shu/masa_shu.json
sth/plantation/doctype/masa_shu/masa_shu.py
sth/plantation/doctype/masa_shu/masa_shu.js
sth/plantation/doctype/masa_shu/test_masa_shu.py
sth/plantation/doctype/masa_shu_detail/masa_shu_detail.json
sth/plantation/doctype/masa_shu_detail/masa_shu_detail.py
```

Modul **Plantation** (bukan Sales STH). Alasannya: masa terikat operasional kebun.
Kalau mau dipindah, cukup ganti field `module` dan folder induknya.

Isi `masa_shu.py`:

- `check_masa_rows(rows, bulan_mulai, bulan_selesai)` — **fungsi murni**, tanpa database.
  Delapan aturan validasi. Balikannya list pesan kesalahan.
- `bagi_rata_masa(awal, akhir, jumlah)` — **fungsi murni**. Usulan pembagian sama rata;
  sisa hari masuk ke masa terdepan sehingga hasilnya dijamin lolos `check_masa_rows`.
- `rentang_bulan(tahun, bulan)` — nama bulan Indonesia ke (tanggal 1, akhir bulan).
- `usulan_bagi_rata()` — whitelist, dipakai tombol di JS.
- `get_masa(company, tanggal)` — whitelist. **Ini pintu masuk untuk doctype lain.**
  Master Harga SHU dan Perhitungan KUD wajib lewat sini, jangan hitung tanggal sendiri
  (alasannya di §6).

`BULAN_MAP` diimpor dari `sth/plantation/doctype/blok/blok.py` — jangan bikin salinan kedua.

### Selesai — `Master Harga SHU`

```
sth/plantation/doctype/master_harga_shu/{json,py,js,test_}
sth/plantation/doctype/master_harga_shu_tahun_tanam/
sth/plantation/doctype/master_harga_shu_detail/
sth/plantation/doctype/master_harga_shu_penetapan/
```

Fungsi murni di `master_harga_shu.py` (semuanya tanpa database, jadi bisa dites langsung):

- `check_tahun_tanam(rows, tahun)` — aturan 1 dan 2
- `check_harga_rows(rows)` — aturan 3 dan 4
- `check_baris_terkunci(rows_lama, rows_baru, bulan_terkunci)` — aturan 6

Whitelist: `get_masa_setahun()`, `tetapkan_bulan()`, `buka_bulan()`, `get_harga_shu()`.

**Tiga hal yang berbeda dari rencana awal di §4, dan alasannya:**

1. **Tidak ada tombol "Tarik Masa".** Matriks membaca `get_masa_setahun()` langsung tiap
   dirender, jadi barisnya selalu ikut Masa SHU terbaru tanpa perlu ditarik manual.
2. **Baris harga hanya dibuat untuk sel yang diisi.** Frappe tidak punya Currency kosong —
   field Currency selalu jatuh ke 0. Jadi "belum ditetapkan" diwakili oleh **tidak adanya
   baris**, bukan oleh nilai. Ini yang membuat keputusan "kosong bukan nol" benar-benar
   terjaga sampai ke database.
3. **`get_harga_shu()` ikut ditulis di sini**, bukan jadi langkah terpisah — tempatnya
   memang di file ini dan cuma 30 baris.

`sinkron_dan_validasi_masa()` menyalin ulang `tanggal_mulai`/`tanggal_selesai` dari Masa SHU
**setiap kali disimpan**, jadi salinan denormalisasi itu menyembuhkan dirinya sendiri.

`get_harga_shu()` menormalkan `tahun_tanam` dengan `cint()` — meredam sebagian risiko 3 di §8,
tapi bukan penggantinya: normalisasi tetap harus dilakukan juga saat menarik produksi.

**Status pengujian:** fungsi murni sudah dijalankan lewat stub, **19 pemeriksaan lolos**.
`test_master_harga_shu.py` belum pernah dijalankan lewat bench.

**Status pengujian:** logika kedua fungsi murni sudah dijalankan lewat stub dan
**21 pemeriksaan lolos**, termasuk pembagian Januari 2026 asli dari Excel.
`test_masa_shu.py` **belum pernah dijalankan lewat bench** karena Python/frappe tidak
tersedia di mesin ini. Jalankan dulu sebelum lanjut:

```bash
bench --site <site> run-tests --module sth.plantation.doctype.masa_shu.test_masa_shu
```

Doctype-nya juga belum pernah dimigrasikan. `bench migrate` dulu.

### Delapan aturan validasi `Masa SHU`

1. Minimal ada 1 masa
2. `masa_no` berurutan 1..n
3. Tiap baris `selesai >= mulai`
4. Masa pertama mulai tepat tanggal 1
5. Masa terakhir selesai tepat akhir bulan
6. Tanpa celah — `mulai[i] == selesai[i−1] + 1 hari`
7. Tanpa tumpang tindih
8. Semua tanggal berada di dalam bulan itu

Tidak satu pun mengandaikan jumlah masa tertentu. Januari boleh 6 masa, Februari 4,
Maret 8 — itu keputusan user tiap bulan, bukan rumus.

Plus `before_cancel`: tolak pembatalan kalau sudah ada harga berstatus Ditetapkan
yang memakai masa ini. Sekarang masih dijaga oleh `frappe.db.exists("DocType", "Master Harga SHU")`
karena doctype-nya belum ada — **hapus penjagaan itu setelah Master Harga SHU jadi**.

---

### Selesai — `Perhitungan KUD`

```
sth/plantation/doctype/perhitungan_kud/{json,py,js,test_}
sth/plantation/doctype/perhitungan_kud_detail/
sth/plantation/doctype/perhitungan_kud_unit/
```

**Submittable** — ini dokumen uang yang dicetak dan ditandatangani.

Fungsi murni di `perhitungan_kud.py` (semuanya tanpa database):

- `normalisasi_tahun_tanam(nilai)` — jawaban untuk risiko 3 di §8
- `pecah_berat_baris(row)` — jawaban untuk risiko 1 dan 2 di §8
- `cari_masa(masa_rows, tanggal)` dan `kelompokkan_netto(baris_spb, masa_rows)`
- `hitung_shu(...)` — rantai potongan §7

Rentang tanggal diambil dari `masa_setahun()` milik Master Harga SHU lalu disaring
per bulan — tidak ada tanggal yang dihitung sendiri di sini (§6).

**Tambahan yang tidak ada di rancangan awal:**

1. **Daftar unit plasma per dokumen** (`Perhitungan KUD Unit`, Table MultiSelect).
   Query §8 menyaring `unit.plasma = 1` saja, jadi kalau satu company punya dua
   Bumdes nettonya tercampur tanpa ketahuan. Terisi otomatis dengan semua unit
   plasma milik company; kurangi manual kalau mitranya lebih dari satu.
2. **`validate_semua_baris_berharga()` di `on_submit`.** Netto berharga 0 boleh ada
   di draft, tapi tidak boleh disubmit — di dokumen inilah kelonggaran "kembalikan 0"
   (§5) berhenti, karena angkanya langsung jadi uang yang dibayar. Kalau ternyata
   terlalu ketat, longgarkan jadi `msgprint` di satu tempat itu saja.
3. **`status_harga`** — ringkasan "N dari M baris belum ada harganya" di header.

**Status pengujian:** `test_perhitungan_kud.py` sudah ditulis (26 pemeriksaan) tapi
**belum pernah dijalankan** — Python maupun Node tidak ada di mesin ini. Rantai
hitungan §7 sudah dicocokkan manual lewat PowerShell dengan angka Januari 2026.

Asersi angka rupiah sengaja memakai `assertAlmostEqual(delta=0.01)`: Management Fee
jatuh persis di titik tengah (1.961.473,775), jadi digit terakhirnya ditentukan oleh
**Rounding Method di System Settings**, bukan oleh kode. Yang diuji ketat adalah
invariannya — rantai potongan menyambung, dan angsuran + pembayaran selalu berjumlah
persis Hasil Bersih.

---

## 3. Yang belum dikerjakan, berurutan

1. **Laporan Tanggal Tanpa Harga SHU** — wajib, alasannya di §5
2. **Print format `Perhitungan KUD`** — dokumen ini dicetak dan ditandatangani

Sebelum keduanya: `bench migrate` lalu jalankan ketiga modul tes, dan coba alur
lengkapnya sekali di UI — buat Masa SHU Januari, submit, isi matriks harganya,
tetapkan bulannya, lalu Tarik Produksi di Perhitungan KUD.

---

## 4. `Master Harga SHU` — rancangan (sudah diimplementasikan, lihat §2)

```
Master Harga SHU              autoname: format:MHS-{company_abbr}-{tahun}
                              unique: (company, tahun)
├─ company       Link Company  reqd
├─ tahun         Int           reqd
├─ tahun_tanam (Child)                            ← penentu KOLOM
│    tahun_tanam  Int   reqd
│    umur         Int   read_only   = tahun − tahun_tanam
│    label        Data  read_only   = "{umur}TH"
├─ matriks       HTML                             ← grid yang diketik user
├─ harga (Child)                                  ← hasil flatten, hidden
│    masa_shu        Link Masa SHU
│    bulan_no        Int
│    masa_no         Int
│    tanggal_mulai   Date      ← disalin dari Masa SHU
│    tanggal_selesai Date      ← disalin dari Masa SHU
│    tahun_tanam     Int
│    harga           Currency
└─ penetapan (Child)                              ← penguncian per bulan
     bulan_no | status | ditetapkan_oleh | ditetapkan_pada
```

### Kenapa bentuknya begini

**Tidak submittable.** Dokumennya setahun tapi diisi bulan demi bulan. Kalau submit,
seluruh tahun terkunci dan harus amend 12 kali setahun. Penguncian turun ke level bulan
lewat `penetapan`.

**Tanggal disalin ke baris harga** supaya `get_harga_shu()` cukup satu query tanpa join.
Salinan itu bisa basi kalau Masa SHU diamend — itulah yang dicegah `before_cancel` di
Masa SHU. Dua hal ini satu paket, jangan ambil salah satunya saja.

**Simpan tahun tanam, hitung umur.** `2012 = 14TH` itu 2026−2012. Kalau `"14TH"` disimpan,
tahun depan datanya bohong. Sheet Excel-nya sendiri mengonfirmasi rumus ini di blok
bantuan H2:J5 (`TAHUN − TT = USIA`).

### Enam aturan validasi

1. `tahun_tanam` tidak boleh duplikat dalam satu dokumen
2. `tahun_tanam <= tahun`
3. `harga >= 0`
4. Kombinasi (`bulan_no`, `masa_no`, `tahun_tanam`) unik
5. Bulan yang punya baris harga wajib punya `Masa SHU` ber-`docstatus=1`
6. Baris di bulan berstatus Ditetapkan tidak boleh diubah nilainya maupun dihapus

Aturan 6 meniru `validate_approved_rows()` di
`sth/sales_sth/doctype/harga_beli_tbs/harga_beli_tbs.py` — bandingkan dengan
`get_doc_before_save()`, lempar kalau baris terkunci hilang atau berubah.

Bulan boleh ditetapkan walaupun masih ada sel kosong. **Sengaja** — lihat §5.

### Matriks input

Prototipe interaktifnya sudah disetujui user di sesi ini. Perilaku yang harus ada:

- Baris = masa (dikelompokkan per bulan), kolom = tahun tanam
- Navigasi panah / Tab / Enter antar sel
- **Tempel dari Excel** — parse TSV multi-baris multi-kolom; format Indonesia
  (`3.406,67`) harus terbaca: buang titik, ganti koma jadi titik
- Sel kosong diberi warna, **bukan diisi nol**. Kosong = belum ditetapkan,
  nol = harganya memang nol. Dua hal berbeda.
- Kolom bisa ditambah/dihapus, label umur menyesuaikan sendiri
- Bulan yang belum punya Masa SHU: tampilkan keterangan, jangan tampilkan baris

Preseden grid custom di STH: `sth/public/js/controllers/komoditi_editor.js` —
`frappe.ui.form.make_control` dirender ke wrapper HTML field.

---

## 5. Keputusan yang sudah diambil user

Jangan tanyakan ulang.

| Hal | Keputusan |
|---|---|
| Harga belum ditetapkan | `get_harga_shu()` **kembalikan 0**, jangan throw. Transaksi boleh mendahului penetapan harga |
| Bulan dengan sel kosong | **Boleh ditetapkan**. Penetapan sebagian itu normal |
| Penguncian | **Per bulan**, bukan per masa |
| Kolom catatan per masa | **Tidak perlu** |
| Jumlah masa | **Bebas tiap bulan**, ditentukan manual |
| Nama doctype masa | **`Masa SHU`** (bukan `Kalender Masa` — khusus SHU) |
| Harga per mitra | **Tidak.** Seragam untuk semua Bumdes di bawah satu company |
| Dimensi company | **Perlu**, karena Perhitungan KUD antar dua pihak |

**Konsekuensi gabungan dari dua keputusan pertama:** lubang harga tidak lagi tertahan
di validasi. Satu-satunya yang bisa memperlihatkan sel kosong sebelum uangnya dihitung
adalah **laporan Tanggal Tanpa Harga SHU**. Karena itu laporan tersebut wajib, bukan pelengkap.

Diputuskan sendiri karena mengikuti langsung: **bulan yang sudah ditetapkan bisa dibuka
kembali**, dan pembukaannya tercatat di `penetapan`. User belum membantah, tapi belum
mengiyakan eksplisit juga.

### Bulan yang belum ditetapkan harus benar-benar kosong

Di Excel, Februari 2026 sampai Januari 2027 terisi 3.592,08 — harga masa terakhir Januari
yang di-copy ke bawah. **Jangan ditiru.** Kalau bulan depan diisi carry-forward, kondisi
"belum ditetapkan" tidak pernah tercapai, dan `get_harga_shu()` akan mengembalikan harga
bulan lalu dengan penuh keyakinan. Nilai 0 itu berisik dan ketahuan; harga bulan lalu
yang menyamar itu diam.

---

## 6. Temuan: dua definisi masa yang berbeda di satu workbook

Di file `2026-01-31 - TML - SHU BUMDES JABUNG - ERP.xlsx`:

| Masa | Menurut sheet Master Harga | Menurut sheet PERHITUNGAN KUD (kolom K) |
|---|---|---|
| I | 1–2 Jan | 1 Jan saja |
| II | **3**–8 Jan | **2**–8 Jan |
| III–VI | 9–15, 16–22, 23–29, 30–31 | sama |

Bulan itu kebetulan tidak ketahuan karena masa I dan II sama-sama berharga 3.406,67.
Kalau perubahan harga jatuh di 2 Januari, dua sheet menghasilkan angka berbeda.
Sheet KUD juga punya baris masa I dua kali (baris 10 dan 11) — 7 baris untuk 6 masa.

**Inilah alasan `Masa SHU` berdiri sendiri.** Master Harga SHU dan Perhitungan KUD
harus sama-sama membaca `get_masa()`, tidak boleh menghitung rentang tanggal sendiri.

---

## 7. `Perhitungan KUD`

```
Perhitungan KUD              autoname: format:PK-{mitra}-{tahun}-{bulan_no}
├─ company       Link Company
├─ mitra         Link Supplier          ← Bumdes/KUD
├─ tahun, bulan
├─ persen_management_fee   Percent  default 2,5
├─ persen_pph22            Percent  default 0,25
├─ persen_bagi_hasil       Percent  default 50
├─ biaya_perawatan         Currency          ← INPUT MANUAL
├─ [Tombol] Tarik Produksi
└─ detail (Child)
     tahun_tanam | masa_no | tanggal_mulai | netto_kg | harga | total
```

### Rumus (sudah dicocokkan angkanya dengan Excel, semuanya konsisten)

```
Total per baris      = netto × harga
Jumlah Produksi TBS  = Σ total                    → 78.458.951  (netto 22.501 kg)

Biaya Perawatan, Panen & Transport                → 31.654.532  ← manual
Management Fee 2,5%  = 2,5%  × Jumlah Produksi    →  1.961.474
Jumlah Biaya Op      = keduanya                   → 33.616.006

Setelah dipotong Biaya Op                         → 44.842.945
Potongan PPh Pasal 22 = 0,25% × Jumlah Produksi   →    196.147,38
Hasil Bersih                                      → 44.646.797,62

Angsuran Hutang Bumdes ke TML (50%)               → 22.323.398,81
Pembayaran TML ke Bumdes      (50%)               → 22.323.398,81
```

**Management Fee dan PPh 22 sama-sama dari Jumlah Produksi TBS**, bukan dari angka
setelah potongan. Mudah keliru kalau dibaca dari tata letaknya.

**Pembulatan di Excel tidak konsisten** — Management Fee dibulatkan ke rupiah penuh
(1.961.474 dari 1.961.473,775), PPh 22 tidak (196.147,3775).

**Keputusan user 4 Agustus 2026: semua 2 desimal.** Ketidakkonsistenan Excel tidak
ditiru karena tidak punya alasan. Akibatnya Hasil Bersih jadi 44.646.797,84 — **0,22
rupiah di atas Excel**. Selisih segitu memang diharapkan; yang harus dicurigai kalau
selisihnya membesar.

`pembayaran_ke_mitra` dihitung sebagai **sisa** (`hasil_bersih − angsuran`), bukan
`50% × hasil_bersih`. Dengan begitu kedua bagian selalu berjumlah persis Hasil Bersih
walaupun persentasenya diubah jadi angka yang tidak habis dibagi.

Sheet Excel menandai sendiri dua input manual: `GANTI ANGKA` di sebelah Biaya Perawatan,
`GANTI TANGGAL` di tanggal tanda tangan.

---

## 8. Sumber netto, dan tiga risiko di jalurnya

```
Surat Pengantar Buah          docstatus = 1
├─ company                                              ← filter
├─ unit  →  Unit.plasma = 1                             ← filter
├─ posting_date                                         ← pengelompokan masa
├─ total_weight = in_weight − out_weight − mill_cut     surat_pengantar_buah.py:178
└─ details (SPB Timbangan Pabrik)
     ├─ blok  →  Blok.tahun_tanam
     └─ total_weight = header.total_weight × total_janjang ÷ header.total_janjang
                                                        surat_pengantar_buah.py:196
```

```sql
SELECT b.tahun_tanam, SUM(d.total_weight) AS netto
FROM `tabSPB Timbangan Pabrik` d
INNER JOIN `tabSurat Pengantar Buah` s ON d.parent = s.name
INNER JOIN `tabBlok` b ON d.blok = b.name
INNER JOIN `tabUnit` u ON s.unit = u.name
WHERE s.docstatus = 1
  AND s.company = %(company)s
  AND u.plasma = 1
  AND s.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
GROUP BY b.tahun_tanam
```

Rentang tanggalnya **diambil dari Masa SHU**, jangan dihitung di sini.

### Tiga risiko — ketiganya sudah ditangani di `perhitungan_kud.py`

**1. Satu baris child punya dua blok.** `blok` dan `blok_restan` ada di baris yang sama,
`total_janjang = qty + qty_restan` (py:102), tapi berat dialokasikan ke baris — tidak
dipecah antar kedua blok. Kalau tahun tanamnya beda, netto masuk ke tahun tanam yang
salah lalu dikali harga yang salah.

**2. Sisa pembulatan alokasi tidak diserap** (py:196). Tiap baris dibulatkan sendiri
sehingga `Σ child.total_weight ≠ header.total_weight`. Pola yang benar sudah dipakai di
`naikkan_ke_tm` pada `sth/plantation/doctype/blok/blok.py` — baris terakhir menyerap sisa.

**3. `Blok.tahun_tanam` bertipe Data, bukan Int** (`blok.json:70`). `"2010"` dan `"2010 "`
jadi dua tahun tanam berbeda saat `GROUP BY`, dan yang tidak cocok mengembalikan harga 0
tanpa suara. Normalisasi (strip + cast int) di satu tempat saat menarik produksi.

Ketiganya menghasilkan angka yang tetap terlihat wajar — tidak ketahuan saat input,
hanya saat rekap tidak cocok.

Penanganannya di `pecah_berat_baris()`: berat baris dibagi menurut janjang, **blok
utama menyerap sisa pembulatan** sehingga jumlah kedua pecahan selalu persis sama
dengan berat barisnya. Kalau tahun tanam kedua blok kebetulan sama, baris tidak
dipecah sama sekali — memecah hanya menambah peluang salah bulat.

Perbaikan ini **lokal untuk SHU**. `SPB Timbangan Pabrik.total_weight` di database
tetap tidak dipecah — risiko 1 dan 2 masih ada untuk pembaca lain dari field itu.

---

## 9. Dua keputusan yang sudah diambil (4 Agustus 2026)

**Penanganan restan → pecah menurut janjang.** `blok` dapat porsi `qty/total_janjang`,
`blok_restan` sisanya. Tiap kg masuk ke tahun tanam yang sebenarnya. Diimplementasikan
di `pecah_berat_baris()`.

**Tanggal penentu masa → `spb.posting_date`** (tanggal timbang). Satu SPB jatuh utuh ke
satu masa, dan harga SHU sendiri ditetapkan mengikuti masa timbang. `panen_date` dan
`panen_date_restan` di baris child sengaja tidak dipakai. Kalau perjanjian dengan
Bumdes ternyata menyebut tanggal panen, yang berubah cuma kolom tanggal di
`ambil_baris_spb()` dan `kelompokkan_netto()` — tapi ingat restan punya
`panen_date_restan` sendiri yang bisa jatuh ke bulan lain.
