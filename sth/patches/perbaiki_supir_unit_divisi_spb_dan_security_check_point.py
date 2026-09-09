import re

import frappe

# Batas rincian yang dicetak per kategori masalah, supaya output bench tidak
# kebanjiran kalau yang bermasalah ternyata banyak.
BATAS_RINCIAN = 20

# Penanda satu SPB yang bloknya jatuh di lebih dari satu divisi; dibedakan dari
# None, yang artinya divisinya tidak ketemu sama sekali.
BEDA_DIVISI = object()

# Rekap spb-muatan-block-20260909153948.xlsx, satu baris per Trans No SPB:
#
#     trans_no|kode unit|nama sopir|blok1,blok2,...
#
# ESTATE, KENDARAAN, dan SOPIR di ekspor itu seragam untuk satu Trans No, jadi
# 429 baris per blok cukup diringkas jadi 216 baris. Bloknya disimpan lengkap
# karena divisi tidak ada di ekspor dan harus dicari lewat master Blok.
DATA = """\
SPBTML62260908155712705|TPRE|HENDRA L|G10c,G10b,G11a
SPBTMM95260908164001614|ASRE|JULPRIANDI MANURUNG|A06f
SPBTML12260908190047192|TPRE|-|F03e,F03f
SPBTML12260908155158106|TPRE|J. RIANTO SIMAMORA|F03e,F03f
SPBTML12260908114647320|TPRE|J. RIANTO SIMAMORA|F03g,F03f
SPBTMM02260908192113205|TPRE|HENDRA L|F03d
SPBTMM02260908180142951|TPRE|EDI CANDRA|F03d
SPBTMM02260908125419895|TPRE|EDI CANDRA|F03d,F03e
SPBTMM09260908192855972|TPRE|ANDI ASMORO SINUHAJI|F99d,F99c
SPBTMM09260908175935557|TPRE|ANDI ASMORO SINUHAJI|F99d,F99c
SPBTMM09260908161636303|TPRE|ANDI ASMORO SINUHAJI|F99b
SPBTMM09260908115908854|TPRE|ANDI ASMORO SINUHAJI|F99c,F99b
SPBTML51260908155638800|TMDE|SOFYAN|G04a,G05a,G04j,G04k,G04b,G05b,G05c
SPBTML51260908120447002|TMDE|SOFYAN|G04j,G04a,G04k,G04b,G05b
SPBTML85260908203608326|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|D05f,D05e
SPBTML83260908194736626|TPRE|AGUS SIMANJUNTAK|D05d,D05e
SPBTML83260908114917479|TPRE|AGUS SIMANJUNTAK|D05e,D05d
SPBTML85260908170223767|TPRE|AGUS SIMANJUNTAK|D05f,D05d,D05e,D05c
SPBTML85260908150410944|TPRE|AGUS SIMANJUNTAK|D05c,D05d,D05e
SPBTML54260908144541103|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E04c
SPBTML54260908105119482|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E99d,E04c
SPBTML58260908172347161|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26t,E26q
SPBTML58260908160839908|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26t,E26q
SPBTML62260907150213226|TPRE|HENDRA L|G14a,G11a
SPBTMM09260907183526193|TPRE|ANDI ASMORO SINUHAJI|E00b,E00d
SPBTMM09260907161901108|TPRE|ANDI ASMORO SINUHAJI|F99c
SPBTMM09260907141304038|TPRE|ANDI ASMORO SINUHAJI|E00b
SPBTMM09260907110605956|TPRE|ANDI ASMORO SINUHAJI|E00d,E00b
SPBTMM09260907204949722|TPRE|ANDI ASMORO SINUHAJI|F99c
SPBTML12260907192629107|TPRE|J. RIANTO SIMAMORA|F03g,F03f
SPBTML12260907144921046|TPRE|J. RIANTO SIMAMORA|F03g,F03f
SPBTML12260907120950532|TPRE|J. RIANTO SIMAMORA|F03g
SPBTMM02260907191045766|TPRE|HENDRA L|F03e,F04e
SPBTMM02260907172635173|TPRE|EDI CANDRA|F04e,F04d
SPBTMM02260907132555214|TPRE|EDI CANDRA|F04d,F03e,F04e
SPBTML51260907131640922|TMDE|SOFYAN|G04k,G04a,G04j,G05a
SPBTML54260907184345325|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01g
SPBTML54260907143535749|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01g
SPBTML58260907204021339|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|F99c
SPBTML85260907164300971|TPRE|AGUS SIMANJUNTAK|D05d,D05c
SPBTML85260907113359308|TPRE|AGUS SIMANJUNTAK|D05b,D05c
SPBTML83260907192244947|TPRE|AGUS SIMANJUNTAK|D05c,D05d
SPBTMM95260907171339913|ASRE|PAUZAN|A06f
SPBTML58260907164155899|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|F99d,F99c
SPBTMM80260907163458969|ASRE|PADLI|B09b
SPBTMM80260907162620028|ASRE|USMAN|B09b
SPBTML83260907135951758|TPRE|AGUS SIMANJUNTAK|D05b,D05c
SPBTMM09260905161437577|TPRE|ANDI ASMORO SINUHAJI|E00d,E02b,E01e
SPBTMM09260905102558382|TPRE|ANDI ASMORO SINUHAJI|E02a,E02b
SPBTML62260905163720969|TPRE|HENDRA L|G11a,G11b,G10a
SPBTML12260906153329675|TPRE|J. RIANTO SIMAMORA|E00e,E00c
SPBTML12260906142657853|TPRE|J. RIANTO SIMAMORA|E00c
SPBTMM02260905193846629|TPRE|HENDRA L|F04d,F04e,F04c
SPBTMM02260905173836277|TPRE|EDI CANDRA|F04e,F04d,F04c
SPBTMM02260905130043566|TPRE|EDI CANDRA|F04c
SPBTML12260905194443953|TPRE|ANDI ASMORO SINUHAJI|E00b,E02b,E02a
SPBTML12260905193311535|TPRE|J. RIANTO SIMAMORA|E00c
SPBTML12260905164134946|TPRE|J. RIANTO SIMAMORA|E00c,E00e
SPBTML12260905150829563|TPRE|J. RIANTO SIMAMORA|E01f,E01e
SPBTML12260905123425824|TPRE|J. RIANTO SIMAMORA|E02a,E05c,E02b
SPBTML12260905102858719|TPRE|J. RIANTO SIMAMORA|E02a,E02b
SPBTML12260905090259688|TPRE|J. RIANTO SIMAMORA|E01f,E01e
SPBTML51260905153146200|TMDE|SOFYAN|G03c,G04i,G03a,G03l
SPBTML51260905124841393|TMDE|SOFYAN|G03d,G03m,G04i,G03a,G03b,G03c,G03l
SPBTML54260905162519914|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01g,E01f
SPBTML54260905134848509|TPRE|ANDI ASMORO SINUHAJI|E01g,E01f
SPBTMM95260905153526113|ASRE|PAUZAN|A08a
SPBTML83260905201250792|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D05b,D05a
SPBTML83260905185452913|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D05b,D05a
SPBTML83260905164257845|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D10a
SPBTML83260905152621590|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D10a,D02d
SPBTML83260905130219142|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D05i,D02d
SPBTML83260905105721620|TPRE|TOHAP ADE PUTRA LUMBAN GAOL|D10a,D02d
SPBTML58260905192008217|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01f,E01g
SPBTML58260905174604584|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01f,E01g
SPBTML58260905141347106|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E01g,E01f
SPBTMM97260904160709387|ASRE|M. SABLI|A06k
SPBTMM80260904172943998|ASRE|JULPRIANDI MANURUNG|B07a
SPBTMM02260904173201333|TPRE|EDI CANDRA|F04c,F04a,F04b
SPBTMM02260904120759664|TPRE|EDI CANDRA|F04b,F04a
SPBTML62260904190159617|TPRE|HENDRA L|G10a,G11b
SPBTML62260904135542442|TPRE|HENDRA L|G10a,G10b
SPBTMM09260904193311197|TPRE|ANDI ASMORO SINUHAJI|E05c,E05a,E01e,E05b
SPBTMM09260904173446701|TPRE|ANDI ASMORO SINUHAJI|E01e,E02b
SPBTMM09260904154248270|TPRE|ANDI ASMORO SINUHAJI|E05b,E05c
SPBTMM09260904134628524|TPRE|ANDI ASMORO SINUHAJI|E05a
SPBTMM09260904211631026|TPRE|ANDI ASMORO SINUHAJI|E02b,E05a,E02a
SPBTMM09260904110353874|TPRE|ANDI ASMORO SINUHAJI|E05b,E05a
SPBTML12260904190607598|TPRE|J. RIANTO SIMAMORA|E01e,E02b
SPBTML12260904123634282|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E05c
SPBTMM92260904105301788|APLE|ABDURRAHMAN KILKODA|A06b-P
SPBTML85260904210307215|TPRE|AGUS SIMANJUNTAK|D05i,D05e
SPBTML83260904193241666|TPRE|AGUS SIMANJUNTAK|D05i
SPBTML83260904170653517|TPRE|AGUS SIMANJUNTAK|D05i
SPBTML83260904111704331|TPRE|AGUS SIMANJUNTAK|D05g,D05h
SPBTML51260904144650672|TMDE|SOFYAN|G04h,G03f,G03e
SPBTML51260904122217493|TMDE|SOFYAN|G04h,G03f,G03e
SPBTML85260904135414253|TPRE|AGUS SIMANJUNTAK|D05i,D05h
SPBTML58260904181422553|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26t,E26u
SPBTML58260904160612845|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|C13a
SPBTMM02260903100244276|TPRE|EDI CANDRA|F04f
SPBTML12260903212347220|TPRE|ANDI ASMORO SINUHAJI|E02a
SPBTML12260903204558336|TPRE|J. RIANTO SIMAMORA|E05a
SPBTML12260903190105142|TPRE|ANDI ASMORO SINUHAJI|E05a
SPBTML12260903163301844|TPRE|ANDI ASMORO SINUHAJI|E05a,E04b,E05c
SPBTML12260903141130195|TPRE|ANDI ASMORO SINUHAJI|E05c,E04a
SPBTML12260903111003015|TPRE|ANDI ASMORO SINUHAJI|E05c
SPBTML71260903194701587|TPRE|EDI CANDRA|F04a,F04b
SPBTML71260903175437016|TPRE|HENDRA L|F04a,F04b
SPBTML71260903160645666|TPRE|EDI CANDRA|F04a
SPBTMM09260903103718166|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E05a
SPBTML83260903210749411|TPRE|AGUS SIMANJUNTAK|D05f,D05h,D05g
SPBTML62260903173425714|TPRE|J. RIANTO SIMAMORA|G10b,G10a
SPBTML62260903122008313|TPRE|HENDRA L|G10b,G10a
SPBTML62260903090032794|TPRE|SUWARDI|G10a,G10b
SPBTML51260903153731728|TMDE|SOFYAN|G03h,G03g
SPBTML51260903120102329|TMDE|SOFYAN|G03i,G03k,G03j,G03h,G03g
SPBTML85260903191836003|TPRE|AGUS SIMANJUNTAK|D05g,D05h
SPBTML85260903134339566|TPRE|AGUS SIMANJUNTAK|D05f,D05h,D05g
SPBTML83260903161837328|TPRE|AGUS SIMANJUNTAK|D05f,D05g
SPBTML83260903102750884|TPRE|AGUS SIMANJUNTAK|D05f
SPBTML58260903172805783|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26d,E26u
SPBTMM80260903155223503|ASRE|JULPRIANDI MANURUNG|B07d,B06e
SPBTML58260903152148793|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26c,E26d
SPBTMM09260902212105743|TPRE|ANDI ASMORO SINUHAJI|E04a,E05c
SPBTMM09260902192057462|TPRE|ANDI ASMORO SINUHAJI|E04a,E05c
SPBTMM09260902150119516|TPRE|ANDI ASMORO SINUHAJI|E05c,E04b,E04a
SPBTMM09260902103659097|TPRE|ANDI ASMORO SINUHAJI|E04a,E04b
SPBTML62260902125336310|TPRE|J. RIANTO SIMAMORA|G10a,G10b
SPBTMM02260902182432825|TPRE|EDI CANDRA|F04f
SPBTMM02260902124418872|TPRE|HENDRA L|F04f
SPBTML51260902162926615|TMDE|SOFYAN|G03j,G03k,G03i
SPBTML58260902204340405|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26d,E26c
SPBTMM80260902192755257|ASRE|JULPRIANDI MANURUNG|B10B
SPBTMM80260902192411498|ASRE|JULPRIANDI MANURUNG|B10B
SPBTMM80260902181842633|ASRE|USMAN|B10B
SPBTMM80260902175954531|ASRE|ARI BAHARUDIN|B10B
SPBTML54260902181942675|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E05b
SPBTML54260902171200157|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E05b
SPBTML54260902134437412|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E05b
SPBTML85260902183430105|TPRE|AGUS SIMANJUNTAK|D05d,D05g,D05f
SPBTML85260902123758852|TPRE|AGUS SIMANJUNTAK|D05e,D05f
SPBTML83260902161257911|TPRE|AGUS SIMANJUNTAK|D05e
SPBTML58260901162417442|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26h,E26c
SPBTML85260901111536810|TPRE|AGUS SIMANJUNTAK|D05d
SPBTML85260901163148127|TPRE|AGUS SIMANJUNTAK|D05e,D05d
SPBTML85260901184530938|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|D05d,D05e,D05c
SPBTML83260901135154068|TPRE|AGUS SIMANJUNTAK|D05c,D05d
SPBTML51260901140300469|TMDE|SOFYAN|G04f,G04g,G04e
SPBTML51260901160302045|TMDE|SOFYAN|G04e,G04f,G04g
SPBTML83260901203528405|TPRE|AGUS SIMANJUNTAK|D05c,D05e,D05d
SPBTMM09260901211207719|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E04a,E05c
SPBTML12260901110323078|TPRE|J. RIANTO SIMAMORA|E04b
SPBTML12260901134532585|TPRE|ANDI ASMORO SINUHAJI|E04a,E04b
SPBTML12260901165711743|TPRE|ANDI ASMORO SINUHAJI|E04b,E04a
SPBTML12260901212315182|TPRE|J. RIANTO SIMAMORA|E04a
SPBTMM02260901133711604|TPRE|HENDRA L|F04f,F04g
SPBTML62260901154743233|TPRE|J. RIANTO SIMAMORA|G10b
SPBTMM80260901171754559|ASRE|PADLI|B09a
SPBTMM02260901174734404|TPRE|HENDRA L|F04g,F04f
SPBTMM80260831125809655|ASRE|M. SABLI|B07c
SPBTMM09260831211116493|TPRE|J. RIANTO SIMAMORA|E04b
SPBTMM09260831193659878|TPRE|ANDI ASMORO SINUHAJI|E99c,E04b
SPBTMM09260831185345989|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E99c,E04a,E04b
SPBTMM09260831170749489|TPRE|ANDI ASMORO SINUHAJI|E99c
SPBTMM09260831144502539|TPRE|ANDI ASMORO SINUHAJI|E99c
SPBTMM09260831115358249|TPRE|ANDI ASMORO SINUHAJI|F01c
SPBTMM09260831100152453|TPRE|ANDI ASMORO SINUHAJI|F01c
SPBTMM02260831173448068|TPRE|EDI CANDRA|F04g,F04h
SPBTMM02260831135114857|TPRE|EDI CANDRA|F04h,F04g
SPBTML62260831174655716|TPRE|J. RIANTO SIMAMORA|G11a,G10b
SPBTML83260831192256624|TPRE|AGUS SIMANJUNTAK|D05h,D05b,D05c
SPBTML51260831155713624|TMDE|SOFYAN|G04c,G04b,G04d
SPBTML51260831131442901|TMDE|SOFYAN|G04d,G04b,G04c
SPBTML85260831173313504|TPRE|AGUS SIMANJUNTAK|D05a,D05b,D05c
SPBTML85260831125514257|TPRE|AGUS SIMANJUNTAK|D05c,D05b
SPBTML85260831102202764|TPRE|AGUS SIMANJUNTAK|D05a
SPBTML83260831152524875|TPRE|AGUS SIMANJUNTAK|D05b
SPBTML58260831161913880|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26q
SPBTML58260831150540969|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26h,E26q
SPBTML83260829192940056|TPRE|J. RIANTO SIMAMORA|D05a
SPBTML83260829095557709|TPRE|AGUS SIMANJUNTAK|D05i,D05h
SPBTML62260829155752094|TPRE|J. RIANTO SIMAMORA|G10c,G11a,G10b
SPBTML62260829140424432|TPRE|HENDRA L|G11a,G10c,G10b
SPBTMM02260829155642562|TPRE|EDI CANDRA|F04h,F03c
SPBTMM02260829115055928|TPRE|EDI CANDRA|F04i,F04h
SPBTMM09260829205615934|TPRE|ANDI ASMORO SINUHAJI|F01c,E26e
SPBTML12260829174017150|TPRE|ANDI ASMORO SINUHAJI|E04c
SPBTML12260829155554790|TPRE|ANDI ASMORO SINUHAJI|E26e,F01d
SPBTML12260829123620531|TPRE|ANDI ASMORO SINUHAJI|F01d
SPBTML85260829203549057|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|D02d
SPBTML51260829154315024|TMDE|SOFYAN|G05c,G05b,G05a
SPBTML51260829114922761|TMDE|SOFYAN|G05c,G04i,G05b,G05a,G04k,G04a,G04j
SPBTML85260829174557242|TPRE|AGUS SIMANJUNTAK|D02d
SPBTML85260829154818087|TPRE|AGUS SIMANJUNTAK|D10a
SPBTML85260829133832598|TPRE|AGUS SIMANJUNTAK|D05h,D02d,D05i
SPBTML85260829111908507|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|D05i,D05h
SPBTML58260829162642594|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26t
SPBTMM09260828201609272|TPRE|ANDI ASMORO SINUHAJI|F01c,F99b
SPBTMM09260828183625760|TPRE|CHOIRUDDIN SIREGAR|F99b
SPBTMM09260828142849836|TPRE|ANDI ASMORO SINUHAJI|F99c
SPBTMM09260828103736957|TPRE|ANDI ASMORO SINUHAJI|F99c,F99d
SPBTMM09260828092137803|TPRE|CHOIRUDDIN SIREGAR|F99d,F99c
SPBTML12260828152138616|TPRE|CHOIRUDDIN SIREGAR|F99c,F01d,F99b
SPBTML12260828130224945|TPRE|CHOIRUDDIN SIREGAR|F99d,F99b
SPBTMM02260828163017086|TPRE|EDI CANDRA|F03c
SPBTML83260828173528081|TPRE|AGUS SIMANJUNTAK|D05h,D05g
SPBTML83260828095021402|TPRE|AGUS SIMANJUNTAK|D05f,D05g,D05h
SPBTML62260828155418192|TPRE|HENDRA L|G10c,G11a,G10b
SPBTML85260828194550476|TPRE|AGUS SIMANJUNTAK|D05e,D05i
SPBTML51260828145924441|TMDE|SOFYAN|G04a,G04j,G04i,G04h,G04k
SPBTML85260828152926754|TPRE|AGUS SIMANJUNTAK|D05i,D05h
SPBTML85260828121412654|TPRE|AGUS SIMANJUNTAK|D05i,D05h,D05g
SPBTML54260828163112481|TPRE|ANDI ASMORO SINUHAJI|E99d
SPBTML58260828163741383|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26d,E26u
SPBTML58260828151154347|TPRE|JEFRI HEMANTO PANGIHUTAN HUTABARAT|E26u,E26d
"""


def execute(trans_nos=None):
	"""Perbaiki nama supir, unit, dan divisi SPB dan Security Check Point.

	Sumbernya ekspor "Surat Pengiriman Buah per Blok" tanggal 9 September 2026.
	Kolom TRANS NO di ekspor itu adalah trans_no SPB kiriman API, yang di Surat
	Pengantar Buah tersimpan di field trans_no dan di Security Check Point di
	field spb_trans_no.

	    driver_name : kolom SOPIR
	    unit        : kode di depan kolom ESTATE (TPRE, ASRE, APLE, TMDE)
	    divisi      : dicari dari master Blok, karena ekspornya tidak punya kolom
	                  divisi

	Ketiganya ditimpa walau sudah terisi: ekspor ini yang dianggap benar, dan yang
	mau diperbaiki justru nilai yang salah, bukan yang kosong.

	Satu Trans No bisa memuat sampai tujuh blok. Selama semua blok itu jatuh di
	divisi yang sama, divisinya dipakai; kalau blok satu SPB terpisah di dua
	divisi, divisinya dilewati — driver_name dan unit tetap diperbarui — lalu
	dokumennya disebut di ringkasan supaya bisa diputuskan sendiri.

	Cakupannya beda antara dua doctype ini. Security Check Point dibatasi kiriman
	API: dokumen yang diinput orang lewat UI datanya diisi petugas yang melihat
	kendaraannya langsung, dan itu lebih dipercaya daripada ekspor. SPB tidak
	disaring pemiliknya, cukup mengandalkan trans_no — field itu memang hanya
	diisi jalur API, sementara pengiriman lewat REST tidak selalu memakai user
	api@sth sehingga saringan owner justru membuat sebagian SPB terlewat.

	Ditulis lewat db.set_value karena sebagian dokumennya sudah submit, dan patch
	ini cuma membetulkan data master tanpa menyentuh angka timbangan apa pun.

	Sengaja tidak didaftarkan di patches.txt: perbaikan sekali jalan dari satu
	berkas ekspor, yang mau diawasi sendiri waktu dijalankan.

	    bench --site <site> execute sth.patches.perbaiki_supir_unit_divisi_spb_dan_security_check_point.execute

	Untuk sebagian Trans No saja:

	    from sth.patches.perbaiki_supir_unit_divisi_spb_dan_security_check_point import execute
	    execute(["SPBTML62260908155712705"])
	"""
	rekap = _baca_data(trans_nos)
	if not rekap:
		print("Perbaikan dari ekspor SPB: tidak ada Trans No yang cocok di data ekspor")
		return

	divisi_per_unit = {}
	nama_employee = {}
	jumlah = {"scp": 0, "spb": 0, "driver_code": 0}
	laporan = {
		"tanpa_scp": [],
		"tanpa_spb": [],
		"unit_asing": set(),
		"blok_asing": {},
		"divisi_campur": [],
	}

	for trans_no, baris in rekap.items():
		sopir = _sopir(baris)
		values = _nilai_baru(trans_no, baris, sopir, divisi_per_unit, laporan)

		scp_list = _get_scp(trans_no)
		if not scp_list:
			laporan["tanpa_scp"].append(trans_no)

		for scp in scp_list:
			jumlah["scp"] += _tulis("Security Check Point", scp, values)

		spb_list = _get_spb(trans_no)
		if not spb_list:
			laporan["tanpa_spb"].append(trans_no)

		for spb in spb_list:
			lepas = _lepas_driver_code(spb, sopir, nama_employee)
			jumlah["driver_code"] += len(lepas)
			jumlah["spb"] += _tulis("Surat Pengantar Buah", spb, dict(values, **lepas))

	_cetak_ringkasan(jumlah, len(rekap), laporan)


def _baca_data(trans_nos):
	if isinstance(trans_nos, str):
		trans_nos = [t.strip() for t in trans_nos.split(",")]

	diminta = {t for t in trans_nos if t} if trans_nos else None

	rekap = {}

	for baris in DATA.strip().splitlines():
		trans_no, unit, sopir, blok = baris.split("|")

		if diminta is not None and trans_no not in diminta:
			continue

		rekap[trans_no] = {
			"unit": unit,
			"sopir": sopir,
			"blok": [b for b in blok.split(",") if b],
		}

	return rekap


def _sopir(baris):
	"""Nama supir dari ekspor, atau None kalau memang tidak dicatat.

	Sopir yang di ekspornya cuma "-" jangan dipakai menghapus nama yang sudah ada
	di dokumennya, dan jangan dipakai menilai driver_code juga.
	"""
	sopir = baris["sopir"].strip()

	return sopir if sopir and sopir != "-" else None


def _nilai_baru(trans_no, baris, sopir, divisi_per_unit, laporan):
	"""Nilai yang berlaku sama untuk SPB maupun Security Check Point-nya."""
	values = {}

	if sopir:
		values["driver_name"] = sopir

	unit = baris["unit"]

	if not unit:
		return values

	if not frappe.db.exists("Unit", unit):
		laporan["unit_asing"].add(unit)
		return values

	values["unit"] = unit

	if unit not in divisi_per_unit:
		divisi_per_unit[unit] = _get_divisi_per_blok(unit)

	divisi = _cari_divisi(divisi_per_unit[unit], unit, baris["blok"], laporan["blok_asing"])

	if divisi is BEDA_DIVISI:
		laporan["divisi_campur"].append(trans_no)
	elif divisi:
		values["divisi"] = divisi

	return values


def _get_scp(trans_no):
	"""Security Check Point kiriman API untuk trans_no SPB ini.

	Dokumen batal dilewati, dan yang dari UI juga: datanya diisi petugas yang
	melihat kendaraannya langsung, dan itu lebih dipercaya daripada ekspor.

	Kembalinya daftar, bukan satu dokumen: satu trans_no SPB bisa dipakai dua
	Security Check Point — kendaraan yang masuk lalu keluar lagi lewat pos lain,
	atau kiriman kembar yang belum sempat digabung merge_duplicate_spb_trans_no.
	"""
	return frappe.get_all(
		"Security Check Point",
		filters={
			"spb_trans_no": trans_no,
			"docstatus": ["<", 2],
			"owner": ["like", "%api@sth%"],
		},
		fields=["name", "driver_name", "unit", "divisi"],
		limit_page_length=0,
	)


def _get_spb(trans_no):
	"""Surat Pengantar Buah untuk trans_no ini, kecuali yang sudah dibatalkan.

	Tanpa saringan owner — lihat penjelasan cakupan di execute(). Kembalinya
	daftar walau trans_no sudah punya penjaga kembar: merge_duplicate_spb_trans_no
	baru dijalankan belakangan, jadi sisa dokumen kembar masih mungkin ada.
	"""
	return frappe.get_all(
		"Surat Pengantar Buah",
		filters={"trans_no": trans_no, "docstatus": ["<", 2]},
		fields=["name", "driver_name", "driver_code", "unit", "divisi"],
		limit_page_length=0,
	)


def _lepas_driver_code(spb, sopir, cache):
	"""Kosongkan driver_code yang Employee-nya bukan supir di ekspor.

	driver_name diisi dari ekspor sementara driver_code menunjuk Employee; kalau
	keduanya dibiarkan beda, dokumennya menyimpan dua nama supir yang saling
	bertentangan. Employee penggantinya tidak ditebak — nama saja tidak cukup
	untuk memastikan orangnya — jadi tautannya dilepas dan diisi ulang sendiri.

	Dilepas cuma kalau ekspornya memang mencatat supir; kalau tidak, tidak ada
	dasar untuk menyatakan driver_code-nya salah.
	"""
	if not spb.driver_code or not sopir:
		return {}

	if spb.driver_code not in cache:
		cache[spb.driver_code] = frappe.db.get_value("Employee", spb.driver_code, "employee_name")

	if _samakan(cache[spb.driver_code]) == _samakan(sopir):
		return {}

	return {"driver_code": None}


def _samakan(nama):
	"""Bentuk nama untuk membandingkan ekspor dengan master Employee.

	Tanda baca dijadikan spasi lalu spasinya dirapatkan, supaya "J. RIANTO
	SIMAMORA" di ekspor tetap dianggap orang yang sama dengan "J RIANTO SIMAMORA"
	di master. Selebihnya dibandingkan apa adanya: yang beda ejaannya lebih baik
	dilepas dan dipasang ulang sendiri daripada dibiarkan menunjuk orang lain.
	"""
	return re.sub(r"[^A-Z0-9]+", " ", (nama or "").upper()).strip()


def _get_divisi_per_blok(unit):
	"""Peta kode blok -> divisi untuk satu Unit.

	Blok dicari lewat dua kunci: name dan field nama. Nama dokumen Blok pernah
	diberi prefiks kode divisi (lihat kembalikan_nama_berprefiks), jadi kode
	polos seperti "A06f" di ekspor bisa jadi cocoknya di field nama, bukan di
	nama dokumennya. Kuncinya dihurufbesarkan karena ekspor menulis "B10B"
	sementara sisanya huruf kecil.

	Kode yang menunjuk lebih dari satu divisi dibuang: tanpa pembeda lain,
	menebak salah satu lebih buruk daripada melewatinya.
	"""
	peta = {}

	for blok in frappe.get_all(
		"Blok",
		filters={"unit": unit},
		fields=["name", "nama", "divisi"],
		limit_page_length=0,
	):
		if not blok.divisi:
			continue

		for kode in (blok.name, blok.nama):
			if not kode:
				continue

			kode = kode.strip().upper()
			peta.setdefault(kode, set()).add(blok.divisi)

	return {kode: divisi.pop() for kode, divisi in peta.items() if len(divisi) == 1}


def _cari_divisi(peta, unit, blok_list, blok_asing):
	"""Divisi yang menaungi semua blok satu SPB, atau penandanya kalau bercampur."""
	ditemukan = set()

	for kode in blok_list:
		divisi = peta.get(kode.strip().upper())

		if divisi:
			ditemukan.add(divisi)
		else:
			blok_asing.setdefault((unit, kode), 0)
			blok_asing[(unit, kode)] += 1

	if not ditemukan:
		return None

	if len(ditemukan) > 1:
		return BEDA_DIVISI

	return ditemukan.pop()


def _tulis(doctype, row, values):
	"""Tulis field yang isinya belum sesuai, kembalikan 1 kalau ada yang berubah."""
	berubah = {f: v for f, v in values.items() if row.get(f) != v}

	if not berubah:
		return 0

	frappe.db.set_value(doctype, row.name, berubah, update_modified=False)

	return 1


def _cetak_ringkasan(jumlah, total, laporan):
	print(
		"Perbaikan dari ekspor SPB: {spb} Surat Pengantar Buah, "
		"{scp} Security Check Point diperbarui dari ".format(**jumlah)
		+ "{0} Trans No di ekspor".format(total)
	)

	if jumlah["driver_code"]:
		print(
			"  {0} driver_code SPB dikosongkan karena Employee-nya bukan supir di "
			"ekspor, isi ulang sendiri".format(jumlah["driver_code"])
		)

	_cetak_daftar(
		laporan["tanpa_spb"],
		"Trans No tidak punya Surat Pengantar Buah, dilewati",
	)

	_cetak_daftar(
		laporan["tanpa_scp"],
		"Trans No tidak punya Security Check Point kiriman API, dilewati",
	)

	_cetak_daftar(
		sorted(laporan["unit_asing"]),
		"kode Unit di ekspor tidak ada di master, unit dan divisinya dilewati",
	)

	_cetak_daftar(
		[
			"{0} {1} ({2} SPB)".format(u, k, n)
			for (u, k), n in sorted(laporan["blok_asing"].items())
		],
		"blok tidak ketemu di master Blok unit itu",
	)

	_cetak_daftar(
		laporan["divisi_campur"],
		"SPB bloknya terpisah di dua divisi, divisinya dilewati",
	)


def _cetak_daftar(items, keterangan):
	if not items:
		return

	print("  {0} {1}:".format(len(items), keterangan))

	for item in items[:BATAS_RINCIAN]:
		print("    {0}".format(item))

	sisa = len(items) - BATAS_RINCIAN

	if sisa > 0:
		print("    ... dan {0} lainnya".format(sisa))
