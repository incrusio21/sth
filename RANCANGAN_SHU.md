# Rancangan Modul SHU / Perhitungan KUD

Dokumen serah-terima. Disusun 30 Juli 2026 dari sesi brainstorming, supaya sesi
berikutnya bisa lanjut tanpa mengulang analisis.

---

## 1. Apa yang dibangun

Perhitungan bagi hasil TBS antara company (mis. PT Trimitra Lestari) dan mitra
Bumdes/KUD (mis. Bumdes Jabung Cipta Usaha). Sekarang dikerjakan di Excel.

Dua doctype baru:

| Doctype | Cakupan | Peran |
|---|---|---|
| `Master Harga SHU` | per (company, tahun), **tidak submittable** | Pembagian masa **dan** matriks harga masa × kelompok umur |
| `Perhitungan KUD` | per (company, mitra, bulan) | Dokumen hasil, dicetak & ditandatangani |

> **Perubahan 11 Agustus 2026.** Dulu pembagian masa berdiri sebagai doctype
> `Masa SHU` sendiri (per bulan, submittable). Sekarang dilebur jadi child table
> `masa` di `Master Harga SHU`, karena keduanya selalu diisi bersamaan dan
> penguncian per bulan sudah ada di sini. Dua perubahan lain menyertainya: kolom
> matriks berubah dari tahun tanam jadi **kelompok umur yang paten**, dan bulan
> ditulis dengan **nama Indonesia** (sempat jadi angka romawi, lalu dikembalikan).
> Migrasinya di `sth/patches/gabung_masa_shu_ke_master_harga_shu.py`.

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

### Selesai — `Master Harga SHU`

```
sth/accounting_sth/doctype/master_harga_shu/{json,py,js,test_}
sth/accounting_sth/doctype/master_harga_shu_masa/
sth/accounting_sth/doctype/master_harga_shu_detail/
sth/accounting_sth/doctype/master_harga_shu_penetapan/
```

Fungsi murni di `master_harga_shu.py` (semuanya tanpa database, jadi bisa dites langsung):

- `check_masa_rows(rows, bulan_mulai, bulan_selesai)` — delapan aturan pembagian masa
  satu bulan. Balikannya list pesan kesalahan.
- `check_masa_setahun(rows, tahun)` — pembungkusnya: kelompokkan per bulan lalu
  jalankan `check_masa_rows`. Bulan yang tidak punya baris dilewat.
- `bagi_rata_masa(awal, akhir, jumlah)` — usulan pembagian sama rata; sisa hari masuk
  ke masa terdepan sehingga hasilnya dijamin lolos `check_masa_rows`.
- `rentang_bulan(tahun, bulan)` — nama bulan Indonesia **atau nomornya** ke
  (tanggal 1, akhir bulan).
- `kelompok_untuk_umur(umur)` — umur ke kelompok kolom matriks.
- `check_harga_rows(rows)` — aturan 3 dan 4
- `check_baris_terkunci(rows_lama, rows_baru, bulan_terkunci)` — aturan 6, sisi harga
- `check_masa_terkunci(rows_lama, rows_baru, bulan_terkunci)` — aturan 6, sisi masa.
  Ini yang menggantikan submit `Masa SHU`: tanggal masa di bulan yang sudah ditetapkan
  tidak boleh digeser, ditambah, maupun dihapus.

Whitelist: `usulan_bagi_rata()`, `get_masa_setahun()`, `get_kelompok_umur()`,
`tetapkan_bulan()`, `buka_bulan()`, `get_harga_shu()`.

`get_masa(company, tanggal)` dan `masa_setahun(company, tahun)` **adalah pintu masuk
untuk doctype lain** — Perhitungan KUD wajib lewat sini, jangan hitung tanggal sendiri
(alasannya di §6).

`BULAN_MAP` diimpor dari `sth/plantation/doctype/blok/blok.py` — jangan bikin salinan
kedua. `NAMA_BULAN` di sini cuma pembalikannya. Di sisi JS daftar bulan memang ditulis
ulang, tapi daftar kelompok umur tidak: JS mengambilnya lewat `get_kelompok_umur()`.

**Tiga hal yang berbeda dari rencana awal di §4, dan alasannya:**

1. **Tidak ada tombol "Tarik Masa".** Matriks membaca `get_masa_setahun()` langsung tiap
   dirender, jadi barisnya selalu ikut Masa SHU terbaru tanpa perlu ditarik manual.
2. **Baris harga hanya dibuat untuk sel yang diisi.** Frappe tidak punya Currency kosong —
   field Currency selalu jatuh ke 0. Jadi "belum ditetapkan" diwakili oleh **tidak adanya
   baris**, bukan oleh nilai. Ini yang membuat keputusan "kosong bukan nol" benar-benar
   terjaga sampai ke database.
3. **`get_harga_shu()` ikut ditulis di sini**, bukan jadi langkah terpisah — tempatnya
   memang di file ini dan cuma 30 baris.

`sinkron_masa_ke_harga()` menyalin ulang `tanggal_mulai`/`tanggal_selesai` dari tabel masa
**setiap kali disimpan**, jadi salinan denormalisasi itu menyembuhkan dirinya sendiri.

`get_harga_shu()` menormalkan `tahun_tanam` dengan `normalisasi_tahun_tanam()` — meredam
sebagian risiko 3 di §8, tapi bukan penggantinya: normalisasi tetap harus dilakukan juga
saat menarik produksi.

**Status pengujian:** fungsi murni `master_harga_shu.py` dan `perhitungan_kud.py` dijalankan
lewat stub (`runner.py` di scratchpad, frappe dipalsukan): **78 pemeriksaan lolos**, termasuk
pembagian Januari 2026 asli dari Excel. Belum pernah dijalankan lewat bench karena Python
frappe tidak tersedia di mesin ini. Jalankan dulu sebelum lanjut:

```bash
bench --site <site> run-tests --module sth.accounting_sth.doctype.master_harga_shu.test_master_harga_shu
```

Doctype-nya juga belum pernah dimigrasikan. `bench migrate` dulu.

### Delapan aturan validasi pembagian masa

1. Minimal ada 1 masa
2. `masa_no` berurutan 1..n
3. Tiap baris `selesai >= mulai`
4. Masa pertama mulai tepat tanggal 1
5. Masa terakhir selesai tepat akhir bulan
6. Tanpa celah — `mulai[i] == selesai[i−1] + 1 hari`
7. Tanpa tumpang tindih
8. Semua tanggal berada di dalam bulan itu

Kedelapan aturan berlaku **per bulan**, dan cuma untuk bulan yang punya baris. Bulan yang
belum diisi sama sekali itu sah — `check_masa_setahun()` melewatinya. Yang ditolak adalah
bulan yang terisi setengah.

Tidak satu pun mengandaikan jumlah masa tertentu. Januari boleh 6 masa, Februari 4,
Maret 8 — itu keputusan user tiap bulan, bukan rumus.

Nomor masa tidak diketik: `set_periode_masa()` menomori ulang tiap simpan menurut urutan
baris dalam bulannya, jadi menggeser baris di grid sudah cukup untuk menomori ulang.

Pengganti submit `Masa SHU` adalah `check_masa_terkunci()`: begitu satu bulan berstatus
Ditetapkan, tanggal masanya ikut terkunci. Tanpa itu, harga yang sudah disepakati bisa
dipindahkan ke rentang tanggal lain tanpa jejak.

---

### Selesai — `Perhitungan KUD`

```
sth/accounting_sth/doctype/perhitungan_kud/{json,py,js,test_}
sth/accounting_sth/doctype/perhitungan_kud_detail/
sth/accounting_sth/doctype/perhitungan_kud_unit/
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

Sebelum keduanya: `bench migrate` lalu jalankan kedua modul tes, dan coba alur
lengkapnya sekali di UI — buka Master Harga SHU tahun berjalan, bagi rata masa Januari,
isi matriks harganya, tetapkan bulannya, lalu Tarik Produksi di Perhitungan KUD.

---

## 4. `Master Harga SHU` — rancangan (sudah diimplementasikan, lihat §2)

```
Master Harga SHU              autoname: format:MHS-{company_abbr}-{tahun}
                              unique: (company, tahun)
├─ company       Link Company  reqd
├─ tahun         Int           reqd
├─ masa (Child)                                   ← penentu BARIS
│    bulan           Select   reqd    nama bulan Indonesia
│    bulan_no        Int      read_only
│    masa_no         Int      read_only  ← urutan baris dalam bulannya
│    tanggal_mulai   Date     reqd
│    tanggal_selesai Date     reqd
│    jumlah_hari     Int      read_only
├─ matriks       HTML                             ← grid yang diketik user
├─ harga (Child)                                  ← hasil flatten, hidden
│    bulan_no        Int
│    masa_no         Int
│    kelompok_umur   Data      ← "3", "10 - 20", …
│    umur_min        Int       ← disalin dari KELOMPOK_UMUR
│    umur_max        Int
│    tanggal_mulai   Date      ← disalin dari tabel masa
│    tanggal_selesai Date      ← disalin dari tabel masa
│    harga           Currency
└─ penetapan (Child)                              ← penguncian per bulan
     bulan_no | bulan | status | ditetapkan_oleh | ditetapkan_pada | catatan
```

### Kenapa bentuknya begini

**Tidak submittable.** Dokumennya setahun tapi diisi bulan demi bulan. Kalau submit,
seluruh tahun terkunci dan harus amend 12 kali setahun. Penguncian turun ke level bulan
lewat `penetapan` — dan sejak masa ikut pindah ke sini, penguncian itu menjaga tanggal
masa juga (`check_masa_terkunci`).

**Masa dan harga satu dokumen.** Keduanya selalu diisi bersamaan dan dikunci bersamaan.
Waktu terpisah, tanggal masa harus disalin lintas doctype dan pembatalan `Masa SHU` perlu
penjaga sendiri; sekarang salinannya cuma dari child table ke child table di dokumen yang
sama.

**Tanggal tetap disalin ke baris harga** supaya `get_harga_shu()` cukup satu query tanpa
join ke tabel masa.

**Kolom = kelompok umur, bukan tahun tanam.** Beberapa umur sengaja dihargai sama, jadi
umur 15 dan 16 sama-sama masuk kolom `10 - 20`. Daftarnya paten di `KELOMPOK_UMUR`:
3, 4, 5, 6, 7, 8, 9, `10 - 20`, `21 - 24`, 25. Kelompok terakhir menampung yang lebih tua
dari 25 (`umur_max` 999) supaya kebun tua tidak jatuh ke harga 0; di bawah 3 tahun memang
tidak punya kolom.

**Simpan tahun tanam di transaksi, hitung umur saat mencari harga.** `2012 = 14TH` itu
2026−2012. Kalau `"14TH"` disimpan, tahun depan datanya bohong. `get_harga_shu()` yang
menghitung `m.tahun − tahun_tanam` lalu mencocokkannya ke `umur_min..umur_max`.

### Aturan validasi

1. Pembagian masa: delapan aturan di §2, berlaku per bulan yang terisi
2. `kelompok_umur` harus ada di daftar `KELOMPOK_UMUR`
3. `harga >= 0`
4. Kombinasi (`bulan_no`, `masa_no`, `kelompok_umur`) unik
5. Bulan yang punya baris harga wajib punya barisnya di tabel masa
6. Di bulan berstatus Ditetapkan: baris harga **dan** tanggal masa tidak boleh diubah,
   ditambah, maupun dihapus

Aturan 6 meniru `validate_approved_rows()` di
`sth/sales_sth/doctype/harga_beli_tbs/harga_beli_tbs.py` — bandingkan dengan
`get_doc_before_save()`, lempar kalau baris terkunci hilang atau berubah.

Bulan boleh ditetapkan walaupun masih ada sel kosong. **Sengaja** — lihat §5.

### Matriks input

Prototipe interaktifnya sudah disetujui user di sesi ini. Perilaku yang harus ada:

- Baris = masa (dikelompokkan per bulan), kolom = kelompok umur
- Navigasi panah / Tab / Enter antar sel
- **Tempel dari Excel** — parse TSV multi-baris multi-kolom; format Indonesia
  (`3.406,67`) harus terbaca: buang titik, ganti koma jadi titik
- Sel kosong diberi warna, **bukan diisi nol**. Kosong = belum ditetapkan,
  nol = harganya memang nol. Dua hal berbeda.
- Kolomnya sama untuk semua bulan dan tidak bisa ditambah — daftarnya paten
- Barisnya dibaca dari tabel masa di dokumen yang sama, jadi ikut berubah begitu
  pembagian masanya diedit, tanpa perlu disimpan dulu

Label kelompok dibaca lewat `attr("data-umur")`, bukan `data("data-umur")`: jQuery
mengubah `"3"` jadi angka tapi `"10 - 20"` tetap string, dan perbandingannya dengan isi
child table jadi meleset.

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
| Tempat masa | **Child table di `Master Harga SHU`** (11 Agu 2026). Dulu doctype `Masa SHU` sendiri |
| Kolom matriks | **Kelompok umur yang paten** (11 Agu 2026), bukan tahun tanam yang ditarik dari tiket timbangan |
| Umur di luar 3–25 | **Di atas 25 ikut kelompok 25**; di bawah 3 tidak punya kolom, jadi harganya 0 |
| Penulisan bulan | **Nama Indonesia.** Sempat diubah jadi angka romawi, lalu dikembalikan (11 Agu 2026) |
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

**Inilah alasan masa cuma boleh punya satu definisi.** Dulu itu diwujudkan dengan doctype
`Masa SHU` yang berdiri sendiri; sekarang dengan child table `masa` yang jadi satu-satunya
tempat tanggal masa ditulis. Perhitungan KUD tetap wajib membacanya lewat `masa_setahun()`
atau `get_masa()`, tidak boleh menghitung rentang tanggal sendiri.

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
├─ biaya_bkm_perawatan     Currency          ← Σ grand_total BKM Perawatan
├─ biaya_bkm_panen         Currency          ← Σ grand_total BKM Panen
├─ biaya_bkm_traksi        Currency          ← Σ grand_total BKM Traksi
├─ detail_biaya (Child)                      ← daftar BKM-nya satu per satu
├─ biaya_perawatan         Currency          ← jumlah ketiganya
├─ lain_lain               Currency          ← INPUT MANUAL
├─ [Tombol] Tarik Produksi
└─ detail (Child)
     tahun_tanam | masa_no | tanggal_mulai | netto_kg | harga | total
```

### Rumus (sudah dicocokkan angkanya dengan Excel, semuanya konsisten)

```
Total per baris      = netto × harga
Jumlah Produksi TBS  = Σ total                    → 78.458.951  (netto 22.501 kg)

Biaya Perawatan, Panen & Transport                → 31.654.532  ← dari BKM
Lain-lain                                                        ← manual
Total Biaya Perawatan, Panen & Transport          = keduanya
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
`GANTI TANGGAL` di tanggal tanda tangan. Yang pertama tidak lagi diketik — lihat §7a.

---

## 7a. Sumber Biaya Perawatan, Panen & Transport

Excel mengetiknya tangan. Di sini angkanya dirakit dari Buku Kerja Mandor unit plasma,
ditarik oleh tombol yang sama dengan produksinya:

```sql
SELECT SUM(b.grand_total)
FROM `tab<Buku Kerja Mandor ...>` b
INNER JOIN `tabUnit` u ON b.unit = u.name
WHERE b.docstatus = 1
  AND b.company = %(company)s
  AND u.plasma = 1
  AND b.unit IN %(units)s
  AND b.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
```

Tiga jenis BKM, satu field masing-masing supaya angkanya bisa ditelusuri:
Perawatan, Panen, dan Traksi sebagai bagian transportnya.

Dokumennya **tidak langsung dijumlah di SQL**. Yang diambil daftarnya, lalu disimpan
utuh di child table `detail_biaya` (`Perhitungan KUD Biaya BKM`): jenis, nomor BKM
(Dynamic Link, bisa diklik), tanggal, unit, divisi, nilai. Ketiga field ringkasan
dijumlah ulang dari daftar itu tiap validate lewat `rekap_biaya_bkm()`, jadi angka
di atas tidak pernah bisa menyimpang dari daftar di bawahnya.

**Yang dijumlahkan `grand_total`, bukan nilai jurnalnya.** BKM Perawatan sengaja
membuang material dari GL Entry-nya (`get_nilai_gl_entry()`) karena material sudah
dijurnal Stock Entry "Material Used" ke akun kegiatan yang sama. Mitra tetap ditagih
material yang dipakai di kebunnya, jadi di sini yang dipakai nilai penuh dokumen.
BKM Panen sendiri sudah mengurangi denda di `after_calculate_grand_total()`.

**Cukup `docstatus = 1`, tidak menunggu workflow Posted.** BKM baru Posted saat
Accounting Period ditutup — jauh sesudah perhitungan bulanan ini dibuat. Menunggunya
berarti biayanya selalu nol saat dibutuhkan.

`unit` di BKM Traksi tidak wajib diisi. BKM Traksi tanpa unit tidak akan pernah
terhitung di sini, sama seperti BKM milik unit non plasma.

`lain_lain` tetap manual, dan berpengaruh lewat
`total_biaya_perawatan_panen_dan_transport` yang jadi masukan `hitung_shu()` —
bukan `biaya_perawatan`.

---

## 8. Sumber netto, dan tiga risiko di jalurnya

```
Timbangan                     docstatus = 1
├─ company                                              ← filter
├─ posting_date                                         ← pengelompokan masa
├─ netto_2                                              ← netto tiket
├─ total_janjang                                        ← dasar pembagian
└─ spb_detail (Timbangan SPB Detail)
     ├─ unit  →  Unit.plasma = 1                        ← filter
     ├─ tahun_tanam                                     ← tercatat di tiket
     └─ jumlah_janjang                                  ← porsi baris
```

```sql
SELECT t.name AS timbangan, t.posting_date, t.netto_2, t.total_janjang,
       d.blok, d.tahun_tanam, d.jumlah_janjang
FROM `tabTimbangan SPB Detail` d
INNER JOIN `tabTimbangan` t ON d.parent = t.name
INNER JOIN `tabUnit` u ON d.unit = u.name
WHERE t.docstatus = 1
  AND t.company = %(company)s
  AND u.plasma = 1
  AND d.unit IN %(units)s
  AND t.posting_date BETWEEN %(tanggal_mulai)s AND %(tanggal_selesai)s
```

Rentang tanggalnya **diambil dari Masa SHU**, jangan dihitung di sini.

Unit dibaca dari **baris tiket**, bukan dari kepala tiket: `Timbangan.unit` berisi PKS
penerima, sedangkan `Timbangan SPB Detail.unit` berisi unit kebun asal buahnya.

### Kenapa netto tidak dibaca dari SPB

`Timbangan.update_spb_weight()` menyalin `netto` tiket ke **setiap** baris SPB
(`for row in spb_doc.details: row.total_weight = self.netto`). Satu tiket dengan tiga
blok menaruh netto penuh tiga kali, jadi membaca `SPB Timbangan Pabrik.total_weight`
menghitung buah satu truk berkali-kali. Netto yang dipakai SHU diambil dari `netto_2`
tiketnya, sekali per tiket.

### Dua risiko yang ditangani di `perhitungan_kud.py`

**1. Satu tiket memuat beberapa blok dengan tahun tanam berbeda.** Netto dibagi menurut
janjang di `pecah_netto_tiket()`, dan **baris terakhir menyerap sisa pembulatan** supaya
jumlah pecahan persis sama dengan netto tiketnya. Kalau sebagian baris tiket tersaring
keluar — misal ada blok dari unit non plasma — tidak ada yang menyerap sisa, jadi yang
terhitung hanya sebesar porsinya.

**2. `tahun_tanam` bertipe Data, bukan Int.** `"2010"` dan `"2010 "` jadi dua tahun tanam
berbeda saat dijumlahkan, dan yang tidak cocok mengembalikan harga 0 tanpa suara.
Normalisasi (strip + cast int) ada di satu tempat, `normalisasi_tahun_tanam()` di
`master_harga_shu.py`, dipakai baik oleh Master Harga SHU maupun Perhitungan KUD.

Keduanya menghasilkan angka yang tetap terlihat wajar — tidak ketahuan saat input,
hanya saat rekap tidak cocok.

---

## 9. Dua keputusan yang sudah diambil (4 Agustus 2026)

**Pembagian netto satu tiket → menurut janjang.** Tiap baris tiket dapat porsi
`jumlah_janjang/total_janjang`, baris terakhir menyerap sisa. Tiap kg masuk ke tahun
tanam yang sebenarnya. Diimplementasikan di `pecah_netto_tiket()`.

**Tanggal penentu masa → `timbangan.posting_date`** (tanggal timbang). Satu tiket jatuh
utuh ke satu masa, dan harga SHU sendiri ditetapkan mengikuti masa timbang. Tanggal
panen di baris SPB sengaja tidak dipakai. Kalau perjanjian dengan Bumdes ternyata
menyebut tanggal panen, yang berubah cuma kolom tanggal di `ambil_baris_timbangan()`
dan `kelompokkan_netto()`.

**Tahun tanam Master Harga SHU → dari tiket timbangan, bukan ketikan.** ~~Tabel Tahun
Tanam diisi `sinkron_tahun_tanam()` saat simpan.~~ **Dibatalkan 11 Agustus 2026:** kolom
matriks tidak lagi mengikuti tahun tanam yang kebetulan ada di tiket, melainkan daftar
kelompok umur yang paten (§4). Tabel Tahun Tanam beserta query ke tiket timbangan dibuang;
tahun tanam tetap dibaca dari tiket, tapi cuma saat Perhitungan KUD menarik produksi dan
memanggil `get_harga_shu()`.
