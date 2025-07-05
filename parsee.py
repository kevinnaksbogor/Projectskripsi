import pytesseract
from PIL import ImageGrab
import cv2
import numpy as np
import re
import time

# Koordinat area Target List di GUI Radar
x1, y1, x2, y2 = 1555, 685, 1880, 805





# Batas deteksi sesuai pengaturan GUI Radar
MAX_RANGE = 15.0  # Sesuaikan dengan yang diatur di GUI
MIN_RANGE = 0.1

# Interval update Radar (disesuaikan dengan kecepatan GUI Radar)
RADAR_UPDATE_INTERVAL = 0.1  # Update setiap 100ms

def format_number(value):
    """ Mengubah format angka agar bisa terbaca dengan benar (mengatasi koma/titik). """
    value = value.replace(",", ".").strip()  # Ubah koma menjadi titik
    try:
        return float(value) if "." in value else float(value[0] + "." + value[1:])
    except ValueError:
        return None  # Jika gagal parsing, kembalikan None

def get_radar_data():
    """ Mengambil data Radar melalui OCR dan mengembalikan daftar objek terdeteksi. """
    # Ambil screenshot area Target List di GUI Radar
    # Ambil screenshot area Target List di GUI Radar
    screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
    img = np.array(screenshot)

# Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Resize untuk memperjelas angka (2 kali lipat)
    resized_img = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

# GaussianBlur untuk mengurangi noise ringan
    blurred_img = cv2.GaussianBlur(resized_img, (3, 3), 0)

# Adaptive Thresholding agar angka jelas terbaca
    processed_img = cv2.adaptiveThreshold(
        blurred_img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
)

# Simpan hasil untuk debugging
    cv2.imwrite("processed_radar.png", processed_img)


    # Gunakan OCR untuk membaca teks dari gambar
    ocr_text = pytesseract.image_to_string(
    processed_img, 
    config="--psm 6 -c tessedit_char_whitelist=0123456789.-"
    )
    print("\n🔍 Hasil OCR Mentah (Debugging):\n", ocr_text)


    # Regex yang bisa tangani nilai float dan negatif
    pattern = r"(\d+)\s+([-+]?\d+[.,]?\d*)\s+([-+]?\d+[.,]?\d*)\s+([-+]?\d+[.,]?\d*)"
    matches = re.findall(pattern, ocr_text)


    radar_data = []
    for m in matches:
        try:
            radar_id = int(m[0])
            distance = format_number(m[1])  # Misal: 1.2
            angle = format_number(m[2])     # Misal: -12.3
            # Filter tambahan: anggap angle 0.0° sebagai gagal OCR, skip data
            if angle is None or abs(angle) < 0.5 or abs(angle) > 76:
                continue  # nilai sudut tidak masuk akal atau tidak terbaca

            try:
                if m[3] and re.match(r'^-?\d+(\.\d+)?$', m[3]):
                    speed = format_number(m[3])
                else:
                    speed = 0.0
            except:
                speed = 0.0



            # Filter berdasarkan range GUI Radar
            if distance is None or distance < MIN_RANGE or distance > MAX_RANGE:
                continue
            if angle is None:
                continue

            radar_data.append({
                "id": radar_id,
                "distance": distance,
                "angle": angle,
                "speed": speed
            })
        except Exception as e:
            print(f"⚠️ Gagal parsing data Radar: {m} | Error: {e}")
            continue

    print("[DEBUG] Semua hasil OCR Radar:")
    for m in matches:
        print(f"Raw Match: {m}")

    print(f"\n📡 Jumlah data radar berhasil diproses: {len(radar_data)}")
    for obj in radar_data:
        print(f"[VALID] ID:{obj['id']} | Jarak:{obj['distance']} m | Sudut:{obj['angle']}° | Kecepatan:{obj['speed']} m/s")
    for obj in radar_data:
        print(f"  ID:{obj['id']} | D:{obj['distance']} m | A:{obj['angle']}° | V:{obj['speed']} m/s")
    # Jika tidak ada objek dengan speed > 0, anggap data tidak valid
    # Selalu return radar_data meskipun speed = 0
    return radar_data




if __name__ == "__main__":
    last_radar_update = time.time()

    while True:
        if time.time() - last_radar_update > RADAR_UPDATE_INTERVAL:
            radar_data = get_radar_data()
            last_radar_update = time.time()

            print("\n" + "="*50)
            if radar_data:
                print("📡 Data Radar yang Didapatkan")
                print("="*50)
                print(f"{'🛰️ ID':<8} {'📏 Jarak (m)':<15} {'🎯 Sudut (°)':<15} {'🚀 Kecepatan (m/s)':<20}")
                print("-"*50)
                for obj in radar_data:
                    print(f"{obj['id']:<8} {obj['distance']:<15} {obj['angle']:<15} {obj['speed']:<20}")
            else:
                print("⚠️ Tidak ada data Radar yang terbaca atau di luar range!")
            print("="*50 + "\n")

        time.sleep(0.05)  # Tambahkan sedikit delay agar CPU tidak terlalu berat
