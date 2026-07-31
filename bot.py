import os
import time
import random
import requests
import urllib.parse
import subprocess
import gc
from groq import Groq
from moviepy import AudioFileClip, VideoFileClip, CompositeVideoClip, ColorClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Mengunci direktori kerja agar file tidak "nyasar"
BASE_DIR = os.path.abspath(os.getcwd())

# --- KONFIGURASI GROQ AI ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# --- MANAJEMEN MEMORI (ANTI DUPLIKASI KONTEN) ---
HISTORY_FILE = "history_verses.txt"

def get_used_verses():
    """Mengambil riwayat ayat yang sudah pernah dibuat agar AI tidak mengulanginya"""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def mark_verse_as_used(verse_ref):
    """Menyimpan referensi ayat baru ke dalam memori bot"""
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{verse_ref}\n")

# --- 1. GROQ AI: GENERATOR AYAT ALKITAB & RENUNGAN ---
def generate_dynamic_content(num_videos=5):
    print(f"🕊️ Meminta Groq Llama-3.3 meracik {num_videos} naskah ayat Alkitab & kueri Pexels...")
    
    used_verses = get_used_verses()
    history_context = "\n".join(used_verses[-25:]) if used_verses else "(Belum ada riwayat, buat topik bebas)"
    
    prompt = f"""
    Bertindaklah sebagai pembuat konten rohani Kristen yang mendalam, penuh kasih, dan menguatkan.
    Buatlah {num_videos} naskah video pendek (YouTube Shorts / Reels) berisi ayat Alkitab beserta renungan singkat yang menyejukkan hati bagi mereka yang sedang lelah, cemas, atau mencari pengharapan.
    
    ATURAN MUTLAK ANTI-DUPLIKASI: 
    Dilarang keras membuat naskah dengan referensi ayat atau tema yang mirip dengan daftar ayat yang sudah pernah dibuat ini:
    {history_context}
    
    Gunakan pemisah '---' antar naskah. Format wajib persis seperti ini:
    
    REF: [Referensi Kitab dan Ayat, contoh: Yesaya 41:10 / Filipi 4:6-7 / Mazmur 23:1-3]
    AYAT: [Isi ayat Alkitab yang menyentuh hati dan relevan]
    RENUNGAN: [2-3 kalimat renungan singkat yang menguatkan iman dan mendalam tentang kasih Tuhan]
    CTA: [Ajakan berinteraksi singkat, contoh: Tulis 'Amin' di komentar jika kamu percaya.]
    PEXELS_QUERY: [Kata kunci bahasa Inggris untuk mencari video background rohani/tenang di Pexels, contoh: "peaceful mountain sunrise cinematic drone", "calm ocean waves sunset cinematic", "foggy pine forest moody cinematic"]
    """
    
    raw_text = ""
    for attempt in range(3):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Anda adalah asisten AI rohani yang patuh pada format instruksi."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2048,
            )
            raw_text = chat_completion.choices[0].message.content
            break
        except Exception as e:
            print(f"⚠️ Error Groq (Percobaan {attempt+1}/3): {e}")
            time.sleep(15)
    else:
        raise Exception("❌ Gagal total menghubungi Groq AI.")

    batch = []
    for i, chunk in enumerate(raw_text.split("---")):
        if i >= num_videos: break
        lines = [line.strip() for line in chunk.strip().split("\n") if line.strip()]
        if not lines: continue
        
        ref = "YESAYA 41:10"
        ayat = "Janganlah takut, sebab Aku menyertai engkau, janganlah bimbang, sebab Aku ini Allahmu."
        renungan = "Tuhan tidak pernah meninggalkanmu berjalan sendirian di tengah badai kehidupan."
        cta = "Ketik 'Amin' di komentar."
        pexels_query = "peaceful mountain sunrise cinematic drone"
        
        for line in lines:
            if line.startswith("REF:"): ref = line.replace("REF:", "").strip()
            elif line.startswith("AYAT:"): ayat = line.replace("AYAT:", "").strip()
            elif line.startswith("RENUNGAN:"): renungan = line.replace("RENUNGAN:", "").strip()
            elif line.startswith("CTA:"): cta = line.replace("CTA:", "").strip()
            elif line.startswith("PEXELS_QUERY:"): pexels_query = line.replace("PEXELS_QUERY:", "").strip()
                
        batch.append({
            "id": f"BIBLE_{int(time.time())}_{i}",
            "ref": ref,
            "ayat": ayat,
            "renungan": renungan,
            "cta": cta,
            "pexels_query": pexels_query
        })
        
    print(f"✅ Berhasil meracik {len(batch)} Naskah Ayat Alkitab Unik!")
    return batch

# --- MENGUNDUH FONT PRO ---
def get_custom_font():
    font_filename = os.path.join(BASE_DIR, "Montserrat-Black.ttf")
    if os.path.exists(font_filename) and os.path.getsize(font_filename) < 100000:
        os.remove(font_filename)
        
    if not os.path.exists(font_filename):
        print("📥 Mengunduh Font Estetik (Montserrat Black)...")
        url = "https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf"
        r = requests.get(url)
        if r.status_code == 200:
            with open(font_filename, 'wb') as f:
                f.write(r.content)
            print("✅ Font berhasil diunduh dengan sempurna!")
        else:
            raise Exception(f"Gagal mengunduh font. Status Code: {r.status_code}")
    return os.path.abspath(font_filename)

# --- 2. PEXELS VIDEO BACKGROUND DOWNLOADER DENGAN VALIDASI ---
def download_pexels_video(query, output_filename):
    print(f"🎬 Mencari video latar rohani di Pexels untuk: '{query}'...")
    api_key = os.environ.get("PEXELS_API_KEY")
    headers = {"Authorization": api_key}
    
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=5"
    
    try:
        response = requests.get(url, headers=headers, timeout=15).json()
        if "videos" in response and len(response["videos"]) > 0:
            video_obj = random.choice(response["videos"])
            video_files = video_obj["video_files"]
            hd_file = next((v for v in video_files if v["quality"] == "hd"), video_files[0])
            video_url = hd_file["link"]
            
            vid_data = requests.get(video_url, timeout=30).content
            with open(output_filename, 'wb') as f:
                f.write(vid_data)
                
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 50000:
                print("✅ Stok video Pexels berhasil diunduh dan divalidasi!")
                return output_filename
    except Exception as e:
        print(f"⚠️ Peringatan unduhan Pexels: {e}")

    print("⚠️ Menggunakan video latar cadangan universal yang tenang...")
    fallback_url = "https://api.pexels.com/videos/search?query=peaceful+nature+sunset+drone&orientation=portrait&per_page=1"
    fallback_res = requests.get(fallback_url, headers=headers).json()
    
    if "videos" in fallback_res and len(fallback_res["videos"]) > 0:
        video_obj = fallback_res["videos"][0]
        hd_file = video_obj["video_files"][0]
        vid_data = requests.get(hd_file["link"], timeout=30).content
        with open(output_filename, 'wb') as f:
            f.write(vid_data)
        return output_filename
        
    raise Exception("Gagal total mengunduh video dari Pexels API.")

# --- 3. AI NEURAL VOICE (MENGGUNAKAN SUBPROCESS AGAR AMAN DARI ERROR TERMINAL) ---
def generate_ai_voice(full_text, index, output_audio):
    print(f"[{index}/5] 🎙️ Menyuarakan firman Tuhan...")
    cmd = [
        "edge-tts",
        "--voice", "id-ID-ArdiNeural",
        "--rate=-5%",  # PERBAIKAN: Digabungkan dengan '='
        "--text", full_text,
        "--write-media", output_audio
    ]
    subprocess.run(cmd, check=True)
    return output_audio

# --- 4. TEXT OVERLAY GENERATOR (DYNAMIC FLOW LAYOUT) ---
def create_text_overlay_image(item, output_path, img_size=(1080, 1920)):
    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_path = get_custom_font()
    font_ref = ImageFont.truetype(font_path, 50)
    font_ayat = ImageFont.truetype(font_path, 44)
    font_renungan = ImageFont.truetype(font_path, 40)
    font_cta = ImageFont.truetype(font_path, 40)
    
    max_width = img_size[0] - 120  # Margin 60px kiri-kanan
    
    def wrap_text(text, font):
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            try:
                w_test = draw.textlength(test_line, font=font)
            except AttributeError:
                w_test = draw.textbbox((0, 0), test_line, font=font)[2]
                
            if w_test <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    lines_ref = [f"✨ {item['ref']} ✨"]
    lines_ayat = wrap_text(f'"{item["ayat"]}"', font_ayat)
    lines_renungan = wrap_text(item['renunganimport os
import time
import random
import requests
import urllib.parse
import subprocess
import gc
from groq import Groq
from moviepy import AudioFileClip, VideoFileClip, CompositeVideoClip, ColorClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Mengunci direktori kerja agar file tidak "nyasar"
BASE_DIR = os.path.abspath(os.getcwd())

# --- KONFIGURASI GROQ AI ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# --- MANAJEMEN MEMORI (ANTI DUPLIKASI KONTEN) ---
HISTORY_FILE = "history_verses.txt"

def get_used_verses():
    """Mengambil riwayat ayat yang sudah pernah dibuat agar AI tidak mengulanginya"""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def mark_verse_as_used(verse_ref):
    """Menyimpan referensi ayat baru ke dalam memori bot"""
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{verse_ref}\n")

# --- 1. GROQ AI: GENERATOR AYAT ALKITAB & RENUNGAN ---
def generate_dynamic_content(num_videos=5):
    print(f"🕊️ Meminta Groq Llama-3.3 meracik {num_videos} naskah ayat Alkitab & kueri Pexels...")
    
    used_verses = get_used_verses()
    history_context = "\n".join(used_verses[-25:]) if used_verses else "(Belum ada riwayat, buat topik bebas)"
    
    prompt = f"""
    Bertindaklah sebagai pembuat konten rohani Kristen yang mendalam, penuh kasih, dan menguatkan.
    Buatlah {num_videos} naskah video pendek (YouTube Shorts / Reels) berisi ayat Alkitab beserta renungan singkat yang menyejukkan hati bagi mereka yang sedang lelah, cemas, atau mencari pengharapan.
    
    ATURAN MUTLAK ANTI-DUPLIKASI: 
    Dilarang keras membuat naskah dengan referensi ayat atau tema yang mirip dengan daftar ayat yang sudah pernah dibuat ini:
    {history_context}
    
    Gunakan pemisah '---' antar naskah. Format wajib persis seperti ini:
    
    REF: [Referensi Kitab dan Ayat, contoh: Yesaya 41:10 / Filipi 4:6-7 / Mazmur 23:1-3]
    AYAT: [Isi ayat Alkitab yang menyentuh hati dan relevan]
    RENUNGAN: [2-3 kalimat renungan singkat yang menguatkan iman dan mendalam tentang kasih Tuhan]
    CTA: [Ajakan berinteraksi singkat, contoh: Tulis 'Amin' di komentar jika kamu percaya.]
    PEXELS_QUERY: [Kata kunci bahasa Inggris untuk mencari video background rohani/tenang di Pexels, contoh: "peaceful mountain sunrise cinematic drone", "calm ocean waves sunset cinematic", "foggy pine forest moody cinematic"]
    """
    
    raw_text = ""
    for attempt in range(3):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Anda adalah asisten AI rohani yang patuh pada format instruksi."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2048,
            )
            raw_text = chat_completion.choices[0].message.content
            break
        except Exception as e:
            print(f"⚠️ Error Groq (Percobaan {attempt+1}/3): {e}")
            time.sleep(15)
    else:
        raise Exception("❌ Gagal total menghubungi Groq AI.")

    batch = []
    for i, chunk in enumerate(raw_text.split("---")):
        if i >= num_videos: break
        lines = [line.strip() for line in chunk.strip().split("\n") if line.strip()]
        if not lines: continue
        
        ref = "YESAYA 41:10"
        ayat = "Janganlah takut, sebab Aku menyertai engkau, janganlah bimbang, sebab Aku ini Allahmu."
        renungan = "Tuhan tidak pernah meninggalkanmu berjalan sendirian di tengah badai kehidupan."
        cta = "Ketik 'Amin' di komentar."
        pexels_query = "peaceful mountain sunrise cinematic drone"
        
        for line in lines:
            if line.startswith("REF:"): ref = line.replace("REF:", "").strip()
            elif line.startswith("AYAT:"): ayat = line.replace("AYAT:", "").strip()
            elif line.startswith("RENUNGAN:"): renungan = line.replace("RENUNGAN:", "").strip()
            elif line.startswith("CTA:"): cta = line.replace("CTA:", "").strip()
            elif line.startswith("PEXELS_QUERY:"): pexels_query = line.replace("PEXELS_QUERY:", "").strip()
                
        batch.append({
            "id": f"BIBLE_{int(time.time())}_{i}",
            "ref": ref,
            "ayat": ayat,
            "renungan": renungan,
            "cta": cta,
            "pexels_query": pexels_query
        })
        
    print(f"✅ Berhasil meracik {len(batch)} Naskah Ayat Alkitab Unik!")
    return batch

# --- MENGUNDUH FONT PRO ---
def get_custom_font():
    font_filename = os.path.join(BASE_DIR, "Montserrat-Black.ttf")
    if os.path.exists(font_filename) and os.path.getsize(font_filename) < 100000:
        os.remove(font_filename)
        
    if not os.path.exists(font_filename):
        print("📥 Mengunduh Font Estetik (Montserrat Black)...")
        url = "https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf"
        r = requests.get(url)
        if r.status_code == 200:
            with open(font_filename, 'wb') as f:
                f.write(r.content)
            print("✅ Font berhasil diunduh dengan sempurna!")
        else:
            raise Exception(f"Gagal mengunduh font. Status Code: {r.status_code}")
    return os.path.abspath(font_filename)

# --- 2. PEXELS VIDEO BACKGROUND DOWNLOADER DENGAN VALIDASI ---
def download_pexels_video(query, output_filename):
    print(f"🎬 Mencari video latar rohani di Pexels untuk: '{query}'...")
    api_key = os.environ.get("PEXELS_API_KEY")
    headers = {"Authorization": api_key}
    
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=5"
    
    try:
        response = requests.get(url, headers=headers, timeout=15).json()
        if "videos" in response and len(response["videos"]) > 0:
            video_obj = random.choice(response["videos"])
            video_files = video_obj["video_files"]
            hd_file = next((v for v in video_files if v["quality"] == "hd"), video_files[0])
            video_url = hd_file["link"]
            
            vid_data = requests.get(video_url, timeout=30).content
            with open(output_filename, 'wb') as f:
                f.write(vid_data)
                
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 50000:
                print("✅ Stok video Pexels berhasil diunduh dan divalidasi!")
                return output_filename
    except Exception as e:
        print(f"⚠️ Peringatan unduhan Pexels: {e}")

    print("⚠️ Menggunakan video latar cadangan universal yang tenang...")
    fallback_url = "https://api.pexels.com/videos/search?query=peaceful+nature+sunset+drone&orientation=portrait&per_page=1"
    fallback_res = requests.get(fallback_url, headers=headers).json()
    
    if "videos" in fallback_res and len(fallback_res["videos"]) > 0:
        video_obj = fallback_res["videos"][0]
        hd_file = video_obj["video_files"][0]
        vid_data = requests.get(hd_file["link"], timeout=30).content
        with open(output_filename, 'wb') as f:
            f.write(vid_data)
        return output_filename
        
    raise Exception("Gagal total mengunduh video dari Pexels API.")

# --- 3. AI NEURAL VOICE (MENGGUNAKAN SUBPROCESS AGAR AMAN DARI ERROR TERMINAL) ---
def generate_ai_voice(full_text, index, output_audio):
    print(f"[{index}/5] 🎙️ Menyuarakan firman Tuhan...")
    cmd = [
        "edge-tts",
        "--voice", "id-ID-ArdiNeural",
        "--rate=-5%",  # PERBAIKAN: Digabungkan dengan '='
        "--text", full_text,
        "--write-media", output_audio
    ]
    subprocess.run(cmd, check=True)
    return output_audio

# --- 4. TEXT OVERLAY GENERATOR (DYNAMIC FLOW LAYOUT) ---
def create_text_overlay_image(item, output_path, img_size=(1080, 1920)):
    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_path = get_custom_font()
    font_ref = ImageFont.truetype(font_path, 50)
    font_ayat = ImageFont.truetype(font_path, 44)
    font_renungan = ImageFont.truetype(font_path, 40)
    font_cta = ImageFont.truetype(font_path, 40)
    
    max_width = img_size[0] - 120  # Margin 60px kiri-kanan
    
    def wrap_text(text, font):
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            try:
                w_test = draw.textlength(test_line, font=font)
            except AttributeError:
                w_test = draw.textbbox((0, 0), test_line, font=font)[2]
                
            if w_test <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    lines_ref = [f"✨ {item['ref']} ✨"]
    lines_ayat = wrap_text(f'"{item["ayat"]}"', font_ayat)
    lines_renungan = wrap_text(item['renungan
