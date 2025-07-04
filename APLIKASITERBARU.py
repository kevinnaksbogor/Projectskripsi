import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from ultralytics import YOLO
import cv2
from PIL import Image, ImageTk
import threading
import time
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess
import win32gui
import win32con
import pyautogui
import pytesseract
import numpy as np
import matplotlib.ticker as mticker
import csv 
import os 
from matplotlib.ticker import MaxNLocator
from parsee import get_radar_data as parsee_radar_data 
from collections import deque
# Konfigurasi Tesseract
pytesseract.pytesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Path folder penyimpanan hasil capture
SAVE_DIR =  r"C:\Users\LENOVO\Downloads\Semester 7\Penelitian IEEE\Project APS\GUI\Hasil Capture CV"

# Path folder untuk penyimpanan hasil grafik deteksi
GRAPH_SAVE_DIR = r"C:\Users\LENOVO\Downloads\Semester 7\Penelitian IEEE\Project APS\GUI\Save Graph Detection"
if not os.path.exists(GRAPH_SAVE_DIR):
    os.makedirs(GRAPH_SAVE_DIR)
# Load the YOLOv8 model
model = YOLO("yolov8n.pt")

cap = None
stop_detection = False
radar_process = None 
detection_log = []
detection_counts = []
radar_data = []
avg_differences = []  # FIX: Tambahkan ini agar grafik average bisa update
latest_radar_ocr_data = []  # Untuk menyimpan hasil OCR radar terbaru

# ===== Variabel Global untuk Grafik Integrasi =====
match_counts = []
partial_match_counts = []
no_match_counts = []
time_steps = []

last_integration_update_time = 0  # Inisialisasi awal


MAX_LOG_ENTRIES = 100  # Batas maksimal log yang ditampilkan
# Buffer data radar per objek YOLO
last_valid_radar_data = {}  # Format: {obj_class: {"data": radar_obj, "frame_count": 0}}
BUFFER_EXPIRATION = 5  # Berapa frame sebelum buffer dianggap kadaluarsa

radar_buffer = deque(maxlen=10)
used_radar_ids = set()


def estimate_angle_from_bbox_center(center_x, frame_width, fov_deg=76):
    normalized_x = (center_x / frame_width) - 0.5
    return normalized_x * fov_deg

def get_matching_score(yolo_angle, radar_angle, yolo_dist, radar_dist, yolo_speed=0.0, radar_speed=0.0, max_angle_diff=20, max_dist_diff=2.5, max_speed_diff=3.0):
    angle_score = max(0, 1 - abs(radar_angle - yolo_angle) / max_angle_diff)
    distance_score = max(0, 1 - abs(radar_dist - yolo_dist) / max_dist_diff)
    speed_score = max(0, 1 - abs(radar_speed - yolo_speed) / max_speed_diff)

    return round((angle_score + distance_score + speed_score) / 3 * 100, 1)



def distance_matching(yolo_boxes, radar_data):
    """
    Mencocokkan deteksi YOLO dengan data Radar menggunakan metode yang lebih toleran,
    dengan buffering dan penggabungan data radar dari beberapa frame terakhir.
    """
    global last_valid_radar_data, radar_buffer  # Pastikan variabel buffer ini bisa diakses
    matched_objects = []

    # Gabungkan semua data radar dari buffer
    combined_radar_data = []
    for frame_data in radar_buffer:
        combined_radar_data.extend(frame_data)

    print(f"[BUFFER] Radar total dalam buffer: {len(combined_radar_data)} data dari {len(radar_buffer)} frame")

    for yolo_box in yolo_boxes:
        x, y, w, h, obj_class, confidence = yolo_box
        bbox_center_x = x + (w // 2)  # Titik tengah bounding box YOLO
        yolo_angle = estimate_angle_from_bbox_center(bbox_center_x, 640)
    
    # Validasi sudut objek YOLO: hanya proses jika masih dalam FOV radar
        if abs(yolo_angle) > 38:
            print(f"[SKIP] Objek YOLO berada di luar jangkauan FOV radar: {yolo_angle:.2f}°")
            continue


        best_match = None
        min_distance = float('inf')

        for radar_obj in combined_radar_data:
            if "distance" not in radar_obj or "angle" not in radar_obj:
                continue

            radar_distance = radar_obj["distance"]
            radar_angle = radar_obj["angle"]

    # ⬇️ Pindahkan baris ini ke sini (SEBELUM pengecekan sudut)
            radar_x = int(((radar_angle + 38) / 76) * 640)
            # Gantilah validasi berbasis ID dengan validasi berbasis posisi angle & distance yang hampir sama
            already_used = False
            for used in matched_objects:
                used_radar = used[1]
                if abs(radar_obj["angle"] - used_radar["angle"]) < 2 and abs(radar_obj["distance"] - used_radar["distance"]) < 0.2:
                   already_used = True
                   break
            if already_used:
                continue

    # ✅ Sekarang aman pakai validasi ini
            if abs(radar_angle - yolo_angle) > 20:
                continue

            if abs(radar_x - bbox_center_x) < 120 and radar_distance < min_distance:
                min_distance = radar_distance
                best_match = radar_obj

        unique_id = f"{obj_class}_{bbox_center_x}"  # Biar tiap objek unik berdasarkan posisi

        if best_match:
            if unique_id not in last_valid_radar_data:

                last_valid_radar_data[obj_class] = {"data": best_match, "frame_count": 0}
            else:
                last_valid_radar_data[obj_class]["data"] = best_match
                last_valid_radar_data[obj_class]["frame_count"] = 0
                # ✅ Tambahkan ini agar radar ID tidak dipakai dua kali
            used_radar_ids.add(best_match["id"])
            bbox_center_x = x + (w // 2)
            yolo_angle = estimate_angle_from_bbox_center(bbox_center_x, 640)

# Estimasi jarak default (misalnya 2 meter) jika tidak ada alat pengukur langsung dari YOLO
            # Estimasi jarak adaptif dari tinggi bounding box
            yolo_dist = min(max(0.5, 1500 / h), 6.0)



            score = get_matching_score(yolo_angle, best_match["angle"], yolo_dist, best_match["distance"])

            # Jika speed = 0, tetap izinkan matching asal sudut dan jarak cocok
            if score >= 80:
                status = f"Match ({score}%)"
            elif score >= 50:
                status = f"Partial Match ({score}%)"
            else:
                status = f"No Match ({score}%)"



            best_match["matching_score"] = score
            best_match["matching_status"] = status

            matched_objects.append((yolo_box, best_match))

        elif unique_id in last_valid_radar_data:
            last_valid_radar_data[unique_id]["frame_count"] += 1
            if last_valid_radar_data[unique_id]["frame_count"] < BUFFER_EXPIRATION:
                matched_objects.append((yolo_box, last_valid_radar_data[obj_class]["data"]))
            else:
                del last_valid_radar_data[unique_id]


    print(f"📌 Jumlah Objek YOLO: {len(yolo_boxes)}, Jumlah Data Radar: {len(combined_radar_data)}")
    y_text_offset = 20
    for i, (yolo_box, radar_obj) in enumerate(matched_objects):
        x, y, w, h, obj_class, confidence = yolo_box
        text = f"{confidence:.2f} | D:{radar_obj['distance']}m | A:{radar_obj['angle']}° | V:{radar_obj['speed']}m/s"
        y_text = max(y - 15 - (i * y_text_offset), 20)
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

    expired_keys = [key for key, value in last_valid_radar_data.items() if value["frame_count"] >= BUFFER_EXPIRATION]
    for key in expired_keys:
        del last_valid_radar_data[key]

    return matched_objects


def write_log(message):
    log_text.config(state=tk.NORMAL)
    log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
    log_text.config(state=tk.DISABLED)
    log_text.yview(tk.END)


def start_human_detection():
    global detection_log
    global start_detection_time

    detection_log = []
    global cap, stop_detection
    if cap is None:
        stop_detection = False
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            messagebox.showerror("Error", "Camera could not be opened.")
            cap = None
        else:
            start_detection_time = time.time()  # <- disini saja
            messagebox.showinfo("Info", "Human Detection started.")
            camera_status_label.config(text="Camera: ON", fg="lime")


            threading.Thread(target=show_camera_feed, daemon=True).start()
            threading.Thread(target=radar_reader_loop, daemon=True).start()

    else:
        messagebox.showwarning("Warning", "Human Detection is already running.")
    


def stop_human_detection():
    global cap, stop_detection
    if cap is not None:
        stop_detection = True
        cap.release()
        cap = None
        camera_status_label.config(text="Camera: OFF", fg="red")
        messagebox.showinfo("Info", "Human Detection stopped.")
        empty_image = ImageTk.PhotoImage(image=Image.new("RGB", (360, 360), "#2e3238"))
        detection_label.imgtk = empty_image
        detection_label.config(image=empty_image)


def show_camera_feed():
    global cap, stop_detection, detection_log, radar_data, detection_counts
    prev_time = 0
    MAX_ENTRIES = 1000  # Batas maksimal jumlah data grafik

    if cap is None or not cap.isOpened():
        print("[ERROR] Kamera tidak tersedia.")
        return

    while cap.isOpened() and not stop_detection:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[WARNING] Frame tidak terbaca, keluar dari loop.")
            break

        frame = cv2.flip(frame, 1)
        results = model(frame)
        annotated_frame = results[0].plot()

        # Hitung FPS
        current_time = time.time()
        fps = 1 / (current_time - prev_time) if prev_time > 0 else 0
        fps_label.config(text=f"FPS: {fps:.2f}")

        prev_time = current_time

        # cv2.putText(annotated_frame, f"FPS: {fps:.2f}", (40, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Ambil data YOLO
        yolo_boxes = [(int(box.xyxy[0][0]), int(box.xyxy[0][1]),
                       int(box.xyxy[0][2] - box.xyxy[0][0]),
                       int(box.xyxy[0][3] - box.xyxy[0][1]),
                       int(box.cls[0]), float(box.conf[0]))
                      for box in results[0].boxes if int(box.cls[0]) == 0]

        # Ambil dan cocokkan data Radar
        radar_buffer.append(latest_radar_ocr_data)
        matched_objects = distance_matching(yolo_boxes, list(radar_buffer))
        # Hitung jumlah status integrasi
        match = 0
        partial = 0
        no_match = 0

        for yolo_box, radar_obj in matched_objects:
            status = radar_obj.get("matching_status", "")
            if "Match" in status and not "Partial" in status:
                match += 1
            elif "Partial" in status:
                partial += 1
            elif "No Match" in status:
                no_match += 1

# Setelah semua status dihitung
        total = match + partial + no_match

        if total > 0:
            match_percent = (match / total) * 100
            partial_percent = (partial / total) * 100
            no_match_percent = (no_match / total) * 100
        else:
            match_percent = partial_percent = no_match_percent = 0
            
        # Tetap tambahkan waktu meski tidak ada deteksi
        elapsed_time = int(current_time - start_detection_time)
        match_counts.append(match_percent)
        partial_match_counts.append(partial_percent)
        no_match_counts.append(no_match_percent)
        time_steps.append(elapsed_time)
        avg_differences.append(0 if len(avg_differences)==0 else avg_differences[-1])


        


        if len(match_counts) > 1:
            diff = abs(match_counts[-1] - match_counts[-2])
            avg_differences.append(diff)
        else:
            avg_differences.append(0)

        MAX_GRAPH_POINTS = 2000  # Maksimal 10 menit data real-time (1 titik = 1 detik)

        if len(match_counts) > MAX_GRAPH_POINTS:
            match_counts.pop(0)
            partial_match_counts.pop(0)
            no_match_counts.pop(0)
        global last_integration_update_time

        current_time = time.time()
        

        
        # ========== Update Treeview (Tabel Integrasi Radar–YOLO) ==========
        integration_tree.delete(*integration_tree.get_children())  # Hapus semua isi sebelumnya

        for i, (yolo_box, radar_obj) in enumerate(matched_objects):
            integration_tree.insert("", "end", values=(
                str(i+1),  # Kolom ID menjadi angka saja
                f"{radar_obj['distance']:.2f}",
                f"{radar_obj['angle']:.1f}",
                f"{radar_obj['speed']:.2f}",
                radar_obj.get("matching_status", "N/A")

            ))


        # Tambahkan data ke grafik secara sinkron
        radar_val = latest_radar_val

        detection_counts.append(len(yolo_boxes))
        radar_data.append(radar_val)
        MAX_DETECTION_POINTS = 300  # Sama, 5 menit deteksi

        if len(detection_counts) > MAX_DETECTION_POINTS:
            detection_counts = detection_counts[-MAX_DETECTION_POINTS:]
            radar_data = radar_data[-MAX_DETECTION_POINTS:]

        # Logging data deteksi
        timestamp = time.strftime("%H:%M:%S")
        difference = len(yolo_boxes) - radar_val
        detection_log.append([timestamp, len(yolo_boxes), radar_val, difference])
        
        write_log(f"YOLO Detected: {len(yolo_boxes)} | Radar: {radar_val} | Δ: {difference}")



        # Jaga agar panjang list sinkron
        min_len = min(len(detection_counts), len(radar_data))
        detection_counts = detection_counts[:min_len]
        radar_data = radar_data[:min_len]

        # Batasi panjang list ke MAX_ENTRIES
        if len(detection_counts) > MAX_ENTRIES:
            detection_counts = detection_counts[-MAX_ENTRIES:]
            radar_data = radar_data[-MAX_ENTRIES:]


        # Tambahkan teks radar ke bounding box dengan validasi nilai angle
        y_text_offset = 20
        for i, (yolo_box, radar_obj) in enumerate(matched_objects):
            x, y, w, h, obj_class, confidence = yolo_box
            status = radar_obj.get("matching_status", "")

    # Validasi nilai angle agar angka pasti muncul tanpa "??"
            angle_val = radar_obj['angle']
            if angle_val is None or not isinstance(angle_val, (int, float)):
               angle_text = "0.0"
            else:
                angle_text = f"{angle_val:.1f}"

            text = f"{confidence:.2f} | D:{radar_obj['distance']:.2f}m | A:{angle_text}° | V:{radar_obj['speed']:.2f}m/s | {status}"

            y_text = max(y - 15 - (i * y_text_offset), 20)
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated_frame, (x, y_text - text_height - 5),
                          (x + text_width, y_text + 5), (0, 0, 0), -1)
            cv2.putText(annotated_frame, text, (x, y_text),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Tampilkan ke GUI
        img = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        img = img.resize((360, 360))
        imgtk = ImageTk.PhotoImage(image=img)
        detection_label.imgtk = imgtk
        detection_label.config(image=imgtk)


def save_detection():
    """Menyimpan hasil deteksi YOLOv8 dengan bounding box dalam format gambar (.jpg) di folder tujuan."""
    if cap is not None:
        ret, frame = cap.read()
        if ret:
            # Flip frame untuk menyesuaikan tampilan seperti di GUI
            frame = cv2.flip(frame, 1)

            # Gunakan YOLOv8 untuk mendeteksi objek
            results = model(frame)

            # Ambil hasil deteksi dan gambar bounding box pada frame
            annotated_frame = results[0].plot()  # Menggambar bounding box langsung

            # Buat nama file dengan timestamp agar unik
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            file_name = f"detection_{timestamp}.jpg"
            save_path = os.path.join(SAVE_DIR, file_name)

            # Simpan gambar dengan bounding box
            cv2.imwrite(save_path, annotated_frame)

            # Beri notifikasi ke user
            messagebox.showinfo("Info", f"Deteksi berhasil disimpan dengan bounding box:\n{save_path}")
        else:
            messagebox.showerror("Error", "Gagal menangkap gambar dari kamera.")
    else:
        messagebox.showwarning("Warning", "Kamera belum aktif. Jalankan Human Detection terlebih dahulu.")

def download_log():
    """Menyimpan log hasil deteksi dalam format CSV sesuai format foto yang diminta."""
    if detection_log:
        save_dir = r"C:\Users\LENOVO\Downloads\Semester 7\Penelitian IEEE\Project APS\GUI\Log Data"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        timestamp_file = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = os.path.join(save_dir, f"detection_log_{timestamp_file}.csv")

        with open(file_path, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "YOLOv8 Detection", "Radar Detection", "Difference"])
            writer.writerows(detection_log)

        messagebox.showinfo("Info", f"Detection log saved at:\n{file_path}")
    else:
        messagebox.showwarning("Warning", "No detection data to download.")

        
def download_integration_log():
    if not integration_tree.get_children():
        messagebox.showwarning("Warning", "No integration data available.")
        return

    save_dir = r"C:\Users\LENOVO\Downloads\Semester 7\Penelitian IEEE\Project APS\GUI\Log Data"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    file_path = os.path.join(save_dir, f"integration_log_{timestamp}.csv")

    with open(file_path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Objek ID", "Distance (m)", "Angle (°)", "Speed (m/s)", "Matching Status"])

        for child in integration_tree.get_children():
            row = integration_tree.item(child)["values"]
            writer.writerow(row)

    messagebox.showinfo("Info", f"Integration log saved at:\n{file_path}")


# ========== FUNGSI RADAR ==========
def read_target_list_id():
    x, y = 1594, 695
    width, height = 299, 177
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    text = pytesseract.image_to_string(screenshot, lang='eng')
    try:
        lines = text.splitlines()
        count = sum(1 for line in lines if line.strip() and line[0].isdigit())
        return count
    except Exception as e:
        return 0
    
def radar_reader_loop():
    global latest_radar_val, latest_radar_ocr_data, stop_detection
    while not stop_detection:
        try:
            latest_radar_val = read_target_list_id()  # Ini tetap
            latest_radar_ocr_data = parsee_radar_data()  # ⬅️ Tambahkan OCR radar di sini
        except Exception as e:
            print(f"[Radar Reader ERROR] {e}")
            latest_radar_val = 0
            latest_radar_ocr_data = []
        time.sleep(1)  # Update tiap 1 detik



    

def start_radar_application():
    global radar_process
    app_path = r"C:\\Infineon\\Tools\\Radar GUI\\2.8.2.202205190911\\resources\\launch-tool.exe"
    if not app_path:
        messagebox.showerror("Error", "Application path not specified.")
        return
    try:
        radar_process = subprocess.Popen(app_path)
        messagebox.showinfo("Info", "Radar application started.")
        time.sleep(2)
        hwnd = win32gui.FindWindow(None, "Radar GUI")
        if hwnd:
            win32gui.SetParent(hwnd, radar_frame.winfo_id())
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0,
                                   radar_frame.winfo_width(),
                                   radar_frame.winfo_height(),
                                   win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW)
            radar_status_label.config(text="Radar: ON", fg="lime")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start application: {e}")

def stop_radar_application():
    global radar_process
    radar_status_label.config(text="Radar: OFF", fg="red")

    if radar_process:
        try:
            radar_process.terminate()
            radar_process = None
        except Exception as e:
            print(f"[Radar STOP] Terminate failed: {e}")

    messagebox.showinfo("Info", "Radar status dimatikan.\nJika jendela aplikasi radar masih terbuka, silakan klik tombol X pada jendela radar secara manual.")



# ========== FUNGSI GRAFIK ==========
# Status untuk pembaruan grafik
graph_running = False  


def update_integration_graph():
    global ax_integration, canvas_integration, graph_running

    if not graph_running:
        return
    if 'canvas_integration' not in globals() or 'ax_integration' not in globals():
        return
    if not hasattr(canvas_integration, 'figure'):
        return

    ax_integration.clear()

    if len(match_counts) == 0:
        ax_integration.set_title("Integration Match Over Time", fontsize=12)
        ax_integration.set_xlabel("Detection Time (seconds)", fontsize=10)
        ax_integration.set_ylabel("Percentage (%)", fontsize=10)
        ax_integration.grid(True, linestyle='--', alpha=0.7)
        ax_integration.legend(fontsize=8)
        canvas_integration.draw()
        if graph_running:
            graph_frame.after(500, update_integration_graph)
        return

    adjusted_time_steps = [t - graph_start_time for t in time_steps]



    # Plot semua data
    ax_integration.plot(adjusted_time_steps, match_counts, color='#0055FF', label='Match (%)', linewidth=3)
    ax_integration.plot(adjusted_time_steps, partial_match_counts, color='#FFA500', label='Partial Match (%)', linestyle=(0, (5,5)), linewidth=2, alpha=0.8)
    ax_integration.plot(adjusted_time_steps, no_match_counts, color='#FF4040', label='No Match (%)', linestyle=':', linewidth=2, alpha=0.8)
    ax_integration.grid(which='major', linestyle='--', alpha=0.7)  # Major grid tetap jelas
    ax_integration.grid(which='minor', linestyle=':', alpha=0.2)   # Minor grid lebih halus


    ax_integration.xaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax_integration.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax_integration.xaxis.set_major_locator(mticker.MultipleLocator(2))



    # Fokus tampilan ke 50 detik terakhir saja (Auto-Scroll)
    if adjusted_time_steps:
        max_time = adjusted_time_steps[-1]
        window_size = 10  # Durasi jendela tampil, bisa disetting mau 10 detik, 20 detik, bebas
        if max_time > window_size:
            ax_integration.set_xlim(max_time - window_size, max_time)
        else:
            ax_integration.set_xlim(0, window_size)
    else:
        ax_integration.set_xlim(0, 10)




    ax_integration.set_ylim(0, 110)  # Persentase Match (%) dari 0 sampai 110%
    ax_integration.set_title("Integration Match Over Time", fontsize=12)
    ax_integration.set_xlabel("Detection Time (seconds)", fontsize=10)
    ax_integration.set_ylabel("Percentage (%)", fontsize=10)
    ax_integration.grid(True, linestyle='--', alpha=0.7)
    ax_integration.legend(fontsize=8)

    canvas_integration.flush_events()
    canvas_integration.draw()

    if graph_running:
        graph_frame.after(1000, update_integration_graph)




def open_graph_window():
    global graph_running, ax_integration, canvas_integration
    global graph_start_time
    graph_start_time = time_steps[0] if time_steps else 0

    graph_running = True

    # Bersihkan isi graph_frame sebelumnya
    for widget in graph_frame.winfo_children():
        widget.destroy()

    fig_integration = Figure(figsize=(5, 4), dpi=100)
    ax_integration = fig_integration.add_subplot(111)
    canvas_integration = FigureCanvasTkAgg(fig_integration, master=graph_frame)
    canvas_integration.get_tk_widget().pack(pady=(0, 0), padx=(0, 0))

    # Setup awal grafik
    ax_integration.set_title("Integration Match Over Time", fontsize=12)
    ax_integration.set_xlabel("Detection Time (seconds)", fontsize=10)
    ax_integration.set_ylabel("Percentage (%)", fontsize=10)
    ax_integration.grid(True, linestyle='--', alpha=0.7)

    update_integration_graph()  # Mulai update
    fig_integration.tight_layout(pad=2.0)  # Supaya label sumbu tidak terpotong
    canvas_integration.draw()

    print("[GRAPH] Integration Match Over Time aktif - Data avg_differences:", len(avg_differences))




def stop_graph_update():
    global graph_running
    graph_running = False

    # Bersihkan semua isi frame grafik
    for widget in graph_frame.winfo_children():
        widget.destroy()


def save_full_graph():
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    save_path = os.path.join(GRAPH_SAVE_DIR, f"integration_graph_{timestamp}.png")

    fig_save = Figure(figsize=(7, 5), dpi=100)
    ax_save = fig_save.add_subplot(111)

    # Plot full data ke ax_save (figure baru)
    time_steps_plot = time_steps  # Pakai time_steps penuh

    ax_save.plot(time_steps_plot, match_counts, color='#0055FF', label='Match (%)', linewidth=3)
    ax_save.plot(time_steps_plot, partial_match_counts, color='#FFA500', label='Partial Match (%)', linestyle=(0, (5,5)), linewidth=2, alpha=0.8)
    ax_save.plot(time_steps_plot, no_match_counts, color='#FF4040', label='No Match (%)', linestyle=':', linewidth=2, alpha=0.8)

    ax_save.set_title("Integration Match Over Time", fontsize=14)
    ax_save.set_xlabel("Detection Time (seconds)", fontsize=12)
    ax_save.set_ylabel("Percentage (%)", fontsize=12)
    # Hitung batas kanan sumbu X dibulatkan ke kelipatan 10
    max_x = ((max(time_steps_plot) + 9) // 10) * 10
    ax_save.set_xlim(0, max_x)

    ax_save.xaxis.set_major_locator(mticker.MultipleLocator(20))  # Grid mayor tiap 10 detik
    ax_save.xaxis.set_minor_locator(mticker.AutoMinorLocator())   # Grid minor otomatis

    
    ax_save.set_ylim(0, 110)
    ax_save.grid(which='major', linestyle='--', alpha=0.7)
    ax_save.grid(which='minor', linestyle=':', alpha=0.2)


    ax_save.xaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax_save.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax_save.legend(fontsize=10)

    fig_save.savefig(save_path)
    messagebox.showinfo("Info", f"Integration graph saved:\n{save_path}")






        
def on_hover(event):
    event.widget.config(bg="#4fa8dc")  # Warna saat hover (lebih terang)

def on_leave(event):
    event.widget.config(bg="#61afef")  # Warna normal setelah hover






# GUI Setup
root = tk.Tk()
icon_path = r"C:\Users\LENOVO\Downloads\Semester 7\Penelitian IEEE\Project APS\GUI\Logo UPI Terbaru\logoupi.ico"
try:
    root.iconbitmap(icon_path)
except:
    print("⚠️ Icon file not found, skipped setting custom icon.")

root.title("Pedestrian Detection System with YOLOv8s and FMCW Radar - Real-Time Monitoring")
root.geometry("1400x800")
root.configure(bg="#282c34")

button_style = {
    "font": ("Helvetica", 10, "bold"),
    "bg": "#007acc",               # Biru profesional
    "fg": "white",
    "activebackground": "#005f99"  # Hover biru gelap
}


frame_human = tk.Frame(root, bg="#3b4048", width=300, height=600)
frame_human.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")

frame_human.configure(width=300, height=620)  # Penyesuaian ukuran frame Human Detection

# Frame untuk tombol tambahan di tengah
middle_frame = tk.Frame(root, bg ="#3b4048", width=500, height=800)
middle_frame.grid(row=0, column=1, padx=5, pady=10, sticky="nsew")

# Pastikan frame bisa berkembang mengikuti isinya
middle_frame.grid_propagate(False)

# Frame dan tombol YOLOv8S Detection
tk.Label(frame_human, text="YOLOv8s Detection", font=("Arial Black", 14, "bold"), bg="#3b4048", fg="#FFD700").pack(pady=15)
btn_start = tk.Button(frame_human, text="Start Detection", command=start_human_detection, **button_style)
btn_start.pack(pady=10)
btn_start.bind("<Enter>", on_hover)
btn_start.bind("<Leave>", on_leave)

btn_stop = tk.Button(frame_human, text="Stop Detection", command=stop_human_detection,
                     font=("Helvetica", 10, "bold"), bg="#d9534f", fg="white", activebackground="#c9302c")
btn_stop.pack(pady=10)
btn_stop.bind("<Enter>", on_hover)
btn_stop.bind("<Leave>", on_leave)

btn_save = tk.Button(frame_human, text="Save Detection", command=save_detection, **button_style)
btn_save.pack(pady=10)
btn_save.bind("<Enter>", on_hover)
btn_save.bind("<Leave>", on_leave)


# Label status kamera
camera_status_label = tk.Label(frame_human, text="Camera: OFF", bg="#3b4048", fg="red", font=("Helvetica", 10, "bold"))
camera_status_label.pack(pady=5)

# Bingkai untuk menampilkan kamera diperbesar
detection_frame = tk.Frame(frame_human, bg="#2e3238", width=480, height=480, relief="solid", bd=5)
detection_frame.pack(pady=10)
detection_frame.grid_propagate(False)

# Spasi untuk jarak show graph detection agar tidak terlalu ke atas
spacer = tk.Frame(middle_frame, height=100, bg="#3b4048")  # Spacer untuk mendorong elemen ke bawah
spacer.pack()

middle_title = tk.Label(middle_frame, text="Real-Time Integration Monitoring",
                        font =("Arial Black", 16, "bold"), bg="#3b4048", fg="#32CD32", anchor="center")
middle_title.grid(row=0, column=1, columnspan=1, padx=30, pady=15, sticky="nsew")

# Frame khusus untuk tombol Show Graph Detection dan Grafik
grap_section = tk.Frame(middle_frame, bg="#3b4048")
grap_section.pack(pady=2, fill="x")
show_graph_btn = tk.Button(grap_section, text="Show Graph", command=open_graph_window, 
                           font=("Helvetica", 9, "bold"), width=18, height=1, bg="#61afef", fg="#ffffff")

show_graph_btn.pack(pady=5)  # Pastikan ada jarak agar tidak menempel dengan tombol lain

stop_graph_btn = tk.Button(grap_section, text="Stop Graph", command=stop_graph_update,
                           font=("Helvetica", 9, "bold"), width=18, height=1,
                           bg="#d9534f", fg="white", activebackground="#c9302c")


stop_graph_btn.pack(pady=5) # Tombol akan langsung muncul di bawah tombol "Show Graph Detection"

stop_graph_btn.bind("<Enter>", on_hover)
stop_graph_btn.bind("<Leave>", on_leave)

save_graph_btn = tk.Button(grap_section, text="Save Graph", command=save_full_graph,
                           font=("Helvetica", 9, "bold"), width=18, height=1, bg="#007acc", fg="white")

save_graph_btn.pack(pady=5)
save_graph_btn.bind("<Enter>", on_hover)
save_graph_btn.bind("<Leave>", on_leave)

show_graph_btn.pack(pady=(2, 2))
stop_graph_btn.pack(pady=(2, 2))
save_graph_btn.pack(pady=(2, 2))


# Frame untuk menampilkan grafik Show Graph Detection
graph_frame = tk.Frame(grap_section, bg="#3b4048", width=700, height=600, relief="solid", bd=5)
graph_frame.pack(pady=2, padx=2, fill="both", expand=True)  # PERUBAHAN PADDING


# Mencegah frame mengecil otomatis
graph_frame.grid_propagate(False)

# Memastikan grafik bisa menyesuaikan ukuran frame dengan proporsi yang baik
graph_frame.columnconfigure(0, weight=1)
graph_frame.rowconfigure(0, weight=1)

# Konfigurasi grap_section agar log text tidak turun ke bawah
grap_section.pack_propagate(False)  
grap_section.config(width=700, height=600)  # Tambahkan width agar lebih stabil


# Frame khusus untuk Log
log_section = tk.Frame(middle_frame, bg="#3b4048", height=300)
log_section.pack(side="bottom", padx=2, pady=0, fill="x")
log_section.pack_propagate(False)


# Tambahkan tombol "Download Log" dan "Save Integration Table" di sini
log_button_frame = tk.Frame(log_section, bg="#3b4048")
log_button_frame.pack(side="top", fill="x", pady=(0, 5))

tk.Button(log_button_frame, text="Download Log", command=download_log, 
          font=("Helvetica", 9), width=20, bg="#007acc", fg="white").pack(side="left", padx=5)


detection_label = tk.Label(detection_frame, bg="#2e3238")
empty_image = ImageTk.PhotoImage(image=Image.new("RGB", (360, 360), "#2e3238"))
detection_label.imgtk = empty_image

detection_label.config(image=empty_image)
detection_label.pack(fill="both", expand=True)
fps_label = tk.Label(frame_human, text="FPS: 0.00", bg="#3b4048", fg="#00FF00", font=("Helvetica", 10, "bold"))
fps_label.pack(pady=(0, 10))

#Tabel hasil integrasi Radar-YOLO
# Tabel hasil integrasi Radar–YOLO
integration_tree = ttk.Treeview(frame_human, columns=("id", "distance", "angle", "speed", "status"), show="headings", height=5)

integration_tree.heading("id", text="ID")
integration_tree.heading("distance", text="Distance (m)")
integration_tree.heading("angle", text="Angle (°)")
integration_tree.heading("speed", text="Speed (m/s)")
integration_tree.heading("status", text="Status")

integration_tree.column("id", width=25, anchor="center", stretch=False)
integration_tree.column("distance", width=100, anchor="center", stretch=False)
integration_tree.column("angle", width=67, anchor="center", stretch=False)
integration_tree.column("speed", width=90, anchor="center", stretch=False)
integration_tree.column("status", width=180, anchor="center", stretch=True)

integration_tree.pack(pady=(0, 10), padx=(0, 1))




log_frame = tk.Frame(log_section, bg="#3b4048", width=450, height=180)
log_frame.pack(side="left", padx=5, pady=5)
log_frame.config(width=450, height=180)

# Scrollbar untuk logframe
scrollbar = tk.Scrollbar(log_frame)
scrollbar.pack(side="right", fill="y")

# Frame log tetap di bawah dengan ukuran konsisten
log_text = tk.Text(log_frame, wrap="word", bg="#2e3238", fg="#ffffff",
                   font=("Helvetica", 10), height=8, width=40, yscrollcommand=scrollbar.set)

log_text.pack(side="left", padx=0, pady=0)
log_text.config(state=tk.DISABLED)
log_section.pack_propagate(False)




# Frame Radar
frame_radar = tk.Frame(root, bg="#3b4048", width=890, height=1000)
frame_radar.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
frame_radar.configure(width=500)  # Penyesuaian ukuran frame Radar
tk.Label(frame_radar, text="FMCW Radar", font=("Arial Black", 18, "bold"), bg="#3b4048", fg="#00BFFF").pack(pady=15)
# Label status radar
radar_status_label = tk.Label(frame_radar, text="Radar: OFF", bg="#3b4048", fg="red", font=("Helvetica", 10, "bold"))
radar_status_label.pack()
radar_frame = tk.Frame(frame_radar, width=890, height=900, bg="#1e1e1e")
radar_frame.pack(pady=10)


tk.Button(root, text="Start Radar Application", command=start_radar_application, **{**button_style, "width": 20}).grid(row=1, column=2, pady=10)
tk.Button(root, text="Stop Radar Application", command=stop_radar_application, **{**button_style, "width": 20}).grid(row=2, column=2, pady=5)

tk.Button(root, text="Save Integration Table", command=download_integration_log,
          font=("Helvetica", 9), bg="#007acc", fg="white", width=22)\
    .grid(row=1, column=0, padx=80, pady=(0, 20), sticky="sw")



frame_human.grid_propagate(False)
frame_radar.grid_propagate(False)

root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=10)
root.grid_rowconfigure(0, weight=1)

footer = tk.Label(root, text="© 2025 - Final Project by Kevin Kennedy Tampubolon - Universitas Pendidikan Indonesia",
                  bg="#282c34", fg="gray", font=("Helvetica", 9, "italic"))
footer.grid(row=3, column=0, columnspan=3, pady=(0, 10))

root.mainloop()
