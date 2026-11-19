# Free PowerPoint Morph Reference Dataset

**Korpus hasil audit: 54 PPTX unik** dari tiga repositori GitHub publik. Semua file yang dihitung memiliki elemen native `p159:morph` pada slide yang benar-benar direferensikan oleh `presentation.xml`; SHA-256 unik dan pemeriksaan ZIP CRC lulus. Audit juga menghitung pasangan objek dengan nama/tipe sama serta perubahan geometri pada slide berurutan.

> **Penting:** ini paket indeks + manifest + downloader, bukan arsip biner berisi 54 PPTX. Lingkungan sesi ini dapat memeriksa file di GitHub secara remote tetapi tidak dapat menulis respons biner dari host tersebut langsung ke sandbox lokal. `download_and_verify.py` akan mengambil file-file asli ke komputer Anda dan memverifikasi SHA-256, jumlah slide, jumlah slide Morph, dan ZIP CRC sebelum melaporkan PASS.

## Prioritas untuk teknik pada contoh video

Prioritas A berisi teknik visual yang paling dekat dengan target:

- `pan-gradient-reference.pptx`: tiga bidang miring transparan menyapu horizontal sambil hero image mengecil dan turun ke posisi akhir.
- `wheel-rotation-reference.pptx`: custom freeform blade tanpa fill, bayangan luar, rotasi ±90° per slide, gambar latar berganti.
- `效果7.pptx`: 24 bilah putih + 24 bilah hitam membentuk radial shutter / circular aperture.
- `效果9.pptx`: lengkung emas, circular photo window, dan angka besar.
- `效果4.pptx`: 12 sektor kipas dari foto yang sama, mengembang menjadi bukaan bundar.
- `效果12.pptx`: polygon / hexagon photo mask yang berputar.
- `效果13.pptx`: blur mask dengan teks besar yang ikut bergerak.
- `效果14.pptx`: carousel foto dengan gerak push-pull.
- `效果2*`: foto dipotong menjadi pecahan panel / glass shards lalu disusun ulang.
- `效果11*`: panel foto vertikal yang bergeser lintas slide.
- `效果1.pptx`: diagonal slanted photo wipe.
- `效果3.pptx`: giant typography yang menyilang dan berinteraksi dengan foto.

## Angka korpus

| Sumber | Morph PPTX unik | Keterangan |
|---|---:|---|
| HY-hue113/ppt-effects | 24 | Repositori efek visual dengan recipe/spec; satu duplikat SHA-256 dan tiga kandidat non-Morph dikeluarkan. Salah satu deck multi-foto punya 4 slide XML orphan. |
| iOfficeAI/OfficeCLI | 28 | 2 demo Morph + 26 file style-reference. Satu kandidat style yang tidak memiliki Morph dikeluarkan. |
| SorenWang/morph_motion_pptx_skill | 2 | Referensi spesialis pan-gradient dan wheel-rotation. |
| **Total** | **54** | Tidak ada duplikat SHA-256 pada daftar terpilih. Semua 54 lolos ZIP CRC dan pemeriksaan Morph pada slide aktif. |

Kumpulan prioritas A+B berisi **22 PPTX** (sekitar 19,55 MiB total) yang paling relevan untuk mempelajari image-mask, radial aperture, cutout, panel foto, carousel, dan kontrol matching Morph. Ini memenuhi target minimum 20 file. Lihat `priority_A_B_shortlist.csv` dan `TECHNIQUE_MATCH_MAP.md`.

## Hasil deep audit pasangan objek

| Ukuran | Hasil |
|---|---:|
| File unik, SHA-256 unik | 54 / 54 |
| PPTX lulus ZIP CRC | 54 / 54 |
| Slide yang direferensikan presentasi | 517 |
| Deklarasi Morph pada slide aktif | 470 |
| Pasangan slide dengan Morph di slide tujuan | 454 |
| Pasangan dengan objek unik bertipe + bernama sama | 424 |
| Pasangan dengan objek matched yang geometri-nya berubah | 407 |
| Pasangan tanpa strict name/type match | 30 |
| Total objek matched lintas pasangan | 6.693 |
| Objek matched yang posisi/ukuran/rotasinya berubah | 2.976 |

Satu PPTX memiliki 4 slide XML fisik yang tidak direferensikan (`效果11-多图版.pptx`). Validator menggunakan 10 slide aktif dari daftar presentasi dan mencatat 4 orphan parts terpisah. Ada 30 pasangan yang tidak memiliki strict name/type match; itu adalah *warning* untuk inspeksi manual, bukan bukti pasti bahwa PowerPoint hanya melakukan Fade. Morph juga memiliki mekanisme matching internal lain.


## Cara mengunduh dan mengaudit

Python 3.9+ cukup; tidak memerlukan venv atau paket tambahan.

```bash
python -m unittest -v test_downloader.py
python download_and_verify.py --priority B --workers 2
```

Perintah ini mengunduh contoh prioritas A+B (22 file). Untuk prioritas A saja (15 file), gunakan `--priority A`. Untuk seluruh korpus:

```bash
python download_and_verify.py
```

Untuk hanya 20 pertama:

```bash
python download_and_verify.py --limit 20
```

Hasil disimpan ke folder `Morph_PPTX_Dataset/source/...`, dengan laporan `verification_report.json`. Setiap hasil PASS berarti hash cocok, ZIP CRC valid, urutan slide aktif dari `presentation.xml` cocok, jumlah Morph aktif, pasangan nama/tipe, dan statistik perubahan geometri cocok dengan audit awal. Validator juga menghitung orphan slide parts secara terpisah. Script telah diuji dengan fixture PPTX sintetis yang memuat Morph, pasangan objek bernama sama, perubahan geometri, serta satu slide orphan.

### Menjalankan di Android / Termux

Tidak perlu venv atau dependensi pip. Setelah ZIP dataset diekstrak ke folder, jalankan:

```bash
pkg install python unzip -y
cd morph_pptx_dataset
python download_and_verify.py --priority B --workers 2
```

Untuk semua 54 file, hilangkan `--priority B`. Pada koneksi lambat, gunakan `--workers 1` atau `2`.

## Bukti vs playback

- `OOXML_P159_MORPH_VERIFIED` = file PPTX mengandung `<p159:morph>` pada slide yang direferensikan presentasi. Ini membuktikan deklarasi transition native ada di jalur slide aktif.
- Pasangan nama/tipe yang konsisten dan geometri berubah merupakan bukti struktural yang lebih kuat bahwa ada objek yang disiapkan untuk interpolasi. Itu **tetap tidak** membuktikan transisi benar-benar dimainkan dengan interpolasi oleh setiap renderer. LibreOffice, Google Slides, preview PDF, dan thumbnail tidak layak dipakai untuk menyimpulkan playback Morph.
- Playback harus diuji di PowerPoint Desktop. Pastikan objek yang sama tetap memiliki nama/identitas, tipe, z-order, dan bentuk/relasi geometri konsisten antar-slide.
- Semua deck Morph dapat memiliki `<p:fade/>` sebagai fallback untuk aplikasi yang tidak mendukung Morph. Fallback bukan bukti bahwa slide hanya Fade; verifikasi dilakukan pada keberadaan `p159:morph` yang terpisah.

## Lisensi dan penggunaan

- `iOfficeAI/OfficeCLI`: repositori menerbitkan lisensi Apache-2.0. Ini tidak otomatis meniadakan hak pihak ketiga di setiap gambar/media tertanam; cek file sumber sebelum redistribusi.
- `HY-hue113/ppt-effects`: README menyatakan code/tools MIT dan dokumentasi CC BY 4.0, tetapi foto referensi adalah milik penulis. Download untuk inspeksi; jangan menganggap foto tertanam bebas dipakai ulang atau dibagikan lagi.
- `SorenWang/morph_motion_pptx_skill`: tidak ditemukan file LICENSE di tree repo saat audit. File dapat diakses publik, tetapi hak redistribusi/derivative-use tidak jelas. Gunakan sebagai referensi inspeksi, bukan untuk dipaketkan ulang.

Karena itu indeks ini menyimpan URL sumber resmi dan hash, bukan menyalin isi PPTX ke paket. Pertahankan atribusi dan baca lisensi aset masing-masing sebelum menggunakan output di proyek komersial atau menyebarkan deck turunan.

## Sumber

- https://github.com/HY-hue113/ppt-effects
- https://github.com/iOfficeAI/OfficeCLI/tree/main/skills/morph-ppt
- https://github.com/SorenWang/morph_motion_pptx_skill

## Berkas

- `dataset_manifest.csv`: spreadsheet-compatible inventory, URL unduh, ukuran, jumlah slide, jumlah slide Morph, opsi dan SHA-256.
- `dataset_manifest.json`: manifest terstruktur, termasuk active pairs dan hasil pair-matching.
- `deep_morph_audit.csv`: audit pasangan objek pada seluruh 54 file.
- `AUDIT_SUMMARY.json`: ringkasan hitungan korpus dan anomali.
- `download_and_verify.py`: downloader + validator offline-dependency-free, termasuk hash, ukuran, ZIP CRC, Morph option, pasangan objek, dan perubahan geometri.
- `test_downloader.py`: regression tests offline untuk slide aktif, orphan slide, pair-matching, geometri, dan deteksi Morph option mismatch.