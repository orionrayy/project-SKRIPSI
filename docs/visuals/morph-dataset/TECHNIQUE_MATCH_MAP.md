# Pemetaan Teknik Video → Referensi PPTX Morph

Kriteria target direkonstruksi dari percakapan yang dibagikan. ZIP tutorial video asal tidak terpasang pada sesi ini, sehingga pemetaan teknik bersifat berbasis deskripsi sebelumnya, bukan analisis ulang frame-by-frame dari video.

| Teknik target | Referensi Morph paling dekat | Apa yang perlu dipelajari | Kecocokan |
|---|---|---|---|
| Freeform map / photo cutout | `wheel-rotation-reference.pptx`; `效果1.pptx`; `pan-gradient-reference.pptx` | Custom freeform besar, no-fill + outer shadow, bidang parallelogram, posisi/rotasi/crop antar-slide | Tinggi untuk prinsip cutout; geometri map spesifik belum ditemukan |
| Curved photo ribbon / gallery | `效果14.pptx`; `效果11-多图版.pptx`; `效果9.pptx` | Sequencing foto, push-pull, panel berlapis, arc sebagai framing visual | Sedang; belum ada contoh ribbon foto melengkung persis |
| Circular aperture / photo mask | `效果7.pptx`; `效果9.pptx`; `效果4.pptx` | 48 radial blades dan circle reveal; foto dibagi ke 12 sektor fan; aperture dan shadow | Sangat tinggi |
| Segmented donut picture ring | `效果7.pptx`; `效果4.pptx`; `wheel-rotation-reference.pptx` | Segmentasi radial, custom freeform, mask per sektor, rotasi berurutan | Tinggi untuk radial segmentation; belum ada bukti exact donut ring dengan segmen foto penuh |
| Brush-stroke masked photo | Belum ditemukan PPTX yang sekaligus terbukti punya Morph native dan brush-stroke mask | Cari custom freeform dengan tepi tidak beraturan dan foto-fill, lalu Morph antar-slide dengan shape identity stabil | Belum terpenuhi |

## Prioritas inspeksi

1. **`SorenWang/.../pan-gradient-reference.pptx`**: dua slide; dua-duanya memiliki Morph `byObject`. Tiga bidang miring translusen bergerak horizontal, hero-image picture shape berubah dari crop/zoom besar ke ukuran akhir, frame tipis bergeser. Ini paling baik untuk memahami koordinasi beberapa objek.
2. **`SorenWang/.../wheel-rotation-reference.pptx`**: empat slide; tiga transisi Morph `byObject`. Custom freeform blade tanpa fill memakai outer shadow dan berubah ±90° tiap slide. Ini paling dekat dengan ide map/cutout berbasis kontur bebas.
3. **`HY.../效果7.pptx`**: 25 slide, 25 slide memuat Morph `byObject`; 24 blade putih + 24 blade hitam membentuk radial shutter dan bukaan lingkaran.
4. **`HY.../效果4.pptx`**: dua slide, slide tujuan Morph `byObject`; 12 image-filled fan sectors membuka menjadi lingkaran.
5. **`HY.../效果9.pptx`**: 19 slide, 11 slide memuat Morph `byObject`; arc emas, circular picture window, dan angka besar.
6. **`HY.../效果12.pptx`**: enam slide, Morph `byObject` pada semua; rotasi bentuk heksagon dan image mask.
7. **`HY.../效果13.pptx`**: lima slide, empat slide tujuan Morph `byObject`; blur mask dan tipografi bergerak.
8. **`HY.../效果14.pptx`**: 11 slide, semua slide memuat Morph; carousel foto dengan push-pull.
9. **`HY.../效果2*.pptx`**: foto dipecah menjadi shard/panel dan disusun lintas-slide.
10. **`HY.../效果11*.pptx`**: panel foto multi-gambar/vertikal bergeser.

## Brush-stroke: sumber tambahan, bukan Morph

Showeet menyediakan koleksi **41 brush-effect picture mockups** dalam PPTX, gratis dengan atribusi. Halaman sumber menyebut bentuk brush dapat diedit/diisi foto, tetapi tidak mengklaim Morph. Karena itu ini hanya sumber geometri/mask, **tidak dihitung dalam 54 PPTX Morph**: https://www.showeet.com/17/05/2017/shapes-objects/brush-effect-mockups-powerpoint/

## Prinsip teknis yang harus dipertahankan

- Morph harus diterapkan pada slide tujuan N+1.
- Dua objek yang harus dipaksa match dapat diberi nama unik dengan awalan `!!` yang sama pada dua slide berurutan; PowerPoint mensyaratkan pemetaan 1:1 dan tipe objek yang cocok untuk force matching.
- Jangan mengandalkan shape ID yang berbeda lintas-slide; pertahankan nama, tipe, z-order, crop, dan struktur geometry objek yang bergerak.
- Morph `byObject`, `byWord`, `byChar` berbeda; dataset kontrol iOfficeAI menguji ketiganya.
- `<p:fade/>` dalam `mc:Fallback` hanya jalur fallback untuk renderer yang tidak mendukung Morph. Bukti Morph yang dihitung adalah `<p159:morph>`.
- Kehadiran XML Morph membuktikan deklarasi transisi, bukan playback. Playback final tetap perlu diuji di PowerPoint Desktop.

Rujukan resmi: Microsoft Morph tips & tricks (naming `!!`, object mapping, image crop/zoom): https://support.microsoft.com/en-us/powerpoint/morph-transition-tips-and-tricks


## Hasil audit pasangan objek aktif (19 November 2026)

Audit mengikuti urutan slide yang benar-benar tercantum dalam `ppt/presentation.xml`, bukan sekadar menghitung file `slideN.xml` di ZIP. Untuk setiap transisi Morph aktif, pemeriksa mencari objek unik dengan tipe + nama sama pada dua slide berurutan, kemudian membandingkan `x`, `y`, `cx`, `cy`, dan `rot`.

| Referensi | Morph destination pairs | Pair dengan object-name/type match | Pair dengan perubahan geometri | Catatan |
|---|---:|---:|---:|---|
| Pan-gradient | 1 | 1 | 1 | 5 objek matched, seluruh 5 berubah geometri; 1 gambar utama zoom/settle + 3 freeform bidang diagonal + frame |
| Wheel-rotation | 3 | 3 | 3 | Custom freeform blade berubah rotasi di ketiga pasangan; total 11 object-pairs matched, 6 geometri berubah |
| Efek 1 diagonal | 1 | 1 | 1 | 5 objek matched; gambar dan freeform berubah posisi/ukuran |
| Efek 2 glass shards (long) | 18 | 18 | 17 | 114 object-pairs matched; 79 geometri berubah |
| Efek 3 typography | 11 | 11 | 11 | 137 object-pairs matched; 110 geometri berubah |
| Efek 4 fan sectors | 1 | 1 | 1 | 16 objek matched; 12 geometri berubah |
| Efek 7 radial ring | 24 | 20 | 20 | 4 pasangan tidak menemukan nama+tipe yang sama; jangan menganggap seluruh 24 pasangan pasti menginterpolasi objek |
| Efek 9 circular arc | 11 | 8 | 8 | 3 pasangan tidak menemukan nama+tipe yang sama |
| Efek 11 multi-panel | 9 | 9 | 9 | 71 object-pairs matched; 45 geometri berubah; ada 4 slide XML orphan yang tidak direferensikan presentasi |
| Efek 12 hexagon | 5 | 5 | 5 | 19 object-pairs matched; 16 geometri berubah |
| Efek 13 blur mask | 4 | 4 | 2 | 20 object-pairs matched; 8 geometri berubah; 2 pasangan mempertahankan geometri (bisa untuk konten/format lain) |
| Efek 14 carousel | 10 | 10 | 10 | 105 object-pairs matched; 29 geometri berubah |

**Implikasi:** korpus tidak semuanya setara. Prioritaskan pan-gradient, wheel-rotation, effect 1, effect 2, effect 3, fan sectors, hexagon, blur-mask, dan carousel. Efek 7 dan 9 tetap relevan secara visual, tetapi sebagian transisi Morph-nya tidak menunjukkan pasangan objek unik berdasarkan nama/tipe; perlu playback QA per pasangan sebelum diadopsi.

Audit nama/tipe adalah heuristic yang ketat; Morph engine dapat memakai heuristik internal lainnya. Karena itu `pairs_without_name_match` berarti *strict pair not found*, bukan kepastian bahwa PowerPoint akan Fade. Playback aktual tetap hanya bisa diputuskan di PowerPoint Desktop.