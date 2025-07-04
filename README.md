# Projectskripsi
Integrasi YOLOv8s dan Radar FMCW untuk Deteksi Pejalan Kaki Real-Time Berbasis GUI

Deskripsi Proyek

Proyek ini mengimplementasikan sistem deteksi pejalan kaki real-time yang mengintegrasikan kemampuan deteksi objek dari YOLOv8s dengan data jarak dan sudut dari Radar FMCW. Sistem ini dilengkapi dengan Antarmuka Pengguna Grafis (GUI) yang dibangun menggunakan tkinter untuk visualisasi feed kamera, hasil deteksi, data radar, dan grafik integrasi.

Fitur Utama

•
Deteksi Pejalan Kaki YOLOv8s: Menggunakan model YOLOv8s untuk mengidentifikasi pejalan kaki dalam feed video real-time.

•
Integrasi Data Radar FMCW: Memproses data dari Radar FMCW (melalui aplikasi eksternal) untuk mendapatkan informasi jarak dan sudut objek.

•
Pencocokan Objek: Algoritma pencocokan canggih untuk mengintegrasikan bounding box YOLO dengan data radar, memberikan informasi yang lebih akurat tentang posisi dan kecepatan pejalan kaki.

•
Antarmuka Pengguna Grafis (GUI): Tampilan interaktif untuk:

•
Menampilkan feed kamera dengan anotasi deteksi YOLO.

•
Menampilkan data radar dan status pencocokan.

•
Menyimpan hasil deteksi sebagai gambar.

•
Menyimpan log deteksi dan integrasi ke file CSV.

•
Visualisasi grafik real-time dari status integrasi (Match, Partial Match, No Match).



•
Manajemen Aplikasi Radar: Kemampuan untuk memulai dan menghentikan aplikasi Radar GUI eksternal dari dalam GUI utama.

Persyaratan Sistem

Proyek ini dirancang untuk berjalan di sistem operasi Windows karena ketergantungan pada pustaka pywin32 untuk interaksi dengan aplikasi Radar GUI eksternal.

Perangkat Keras

•
Kamera Web (untuk input video YOLOv8s)

•
Radar FMCW (dan aplikasi GUI pendukungnya, misalnya Infineon Radar GUI)

Perangkat Lunak

•
Python 3.x

•
Tesseract OCR: Diperlukan untuk membaca data dari aplikasi Radar GUI. Unduh dan instal dari https://tesseract-ocr.github.io/tessdoc/Installation.html.

•
Aplikasi Radar GUI: Aplikasi spesifik untuk Radar FMCW Anda (misalnya, Infineon Radar GUI). Jalur instalasi aplikasi ini perlu disesuaikan dalam kode.

Instalasi

1.
Kloning Repositori:

2.
Buat dan Aktifkan Lingkungan Virtual (Opsional, tapi sangat disarankan):

3.
Instal Dependensi Python:

4.
Instal Tesseract OCR:
Unduh dan instal Tesseract OCR dari tautan di bagian Persyaratan Sistem. Pastikan Anda mencatat jalur instalasinya (misalnya, C:\Program Files\Tesseract-OCR\tesseract.exe).

5.
Unduh Model YOLOv8s:
Model yolov8n.pt akan diunduh secara otomatis oleh pustaka ultralytics saat pertama kali dijalankan. Pastikan Anda memiliki koneksi internet.

6.
Konfigurasi Jalur (Penting!):
Buka src/main.py dan sesuaikan jalur absolut berikut sesuai dengan sistem Anda:

•
pytesseract.pytesseract_cmd: Atur ke jalur instalasi tesseract.exe Anda.

•
SAVE_DIR: Direktori untuk menyimpan hasil deteksi gambar.

•
GRAPH_SAVE_DIR: Direktori untuk menyimpan grafik deteksi.

•
Log Data: Direktori untuk menyimpan log CSV.

•
app_path: Jalur ke launch-tool.exe atau executable aplikasi Radar GUI Anda.

•
icon_path: Jalur ke file ikon (.ico) jika Anda ingin menggunakan ikon kustom.



7.
Modul parsee.py:
File src/parsee.py adalah placeholder. Anda perlu mengisi file ini dengan implementasi fungsi get_radar_data() yang sesuai dengan cara Anda mengambil dan mem-parsing data dari Radar FMCW Anda. Ini mungkin melibatkan komunikasi serial, TCP/IP, atau metode lain tergantung pada perangkat keras radar Anda.

Penggunaan

1.
Jalankan Aplikasi Radar GUI Anda (jika tidak dimulai secara otomatis oleh aplikasi).

2.
Jalankan Skrip Utama:

3.
Gunakan GUI: Setelah aplikasi terbuka, Anda dapat:

•
Klik "Start Detection" untuk memulai deteksi YOLOv8s dan feed kamera.

•
Klik "Start Radar Application" untuk mencoba melampirkan aplikasi Radar GUI ke dalam jendela utama (fungsi ini mungkin memerlukan penyesuaian lebih lanjut tergantung pada aplikasi radar spesifik Anda).

•
Pantau log deteksi dan grafik integrasi secara real-time.

•
Gunakan tombol "Save Detection" untuk menyimpan tangkapan layar deteksi.

•
Gunakan tombol "Download Log" dan "Save Integration Table" untuk menyimpan data log.



Struktur Proyek

Plain Text


pedestrian_detection_radar/
├── src/
│   ├── main.py             # Skrip utama aplikasi GUI
│   └── parsee.py           # Modul kustom untuk parsing data radar (placeholder)
├── models/
│   └── yolov8n.pt          # Model YOLOv8s (akan diunduh otomatis)
├── data/
│   ├── captured_images/    # Direktori untuk menyimpan gambar hasil deteksi
│   ├── graphs/             # Direktori untuk menyimpan grafik
│   └── logs/               # Direktori untuk menyimpan log CSV
├── .gitignore              # File untuk mengabaikan file/folder tertentu di Git
├── requirements.txt        # Daftar dependensi Python
└── README.md               # Dokumentasi proyek ini


Kontribusi

Jika Anda ingin berkontribusi pada proyek ini, silakan fork repositori dan buat pull request. Pastikan untuk mengikuti gaya kode yang ada dan sertakan deskripsi perubahan Anda.

Lisensi

[Pilih Lisensi Anda, contoh: MIT License]

