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

# --- 3. AI NEURAL VOICE ---
def generate_ai_voice(full_text, index, output_audio):
    print(f"[{index}/5] 🎙️ Menyuarakan firman Tuhan...")
    cmd = [
        "edge-tts",
        "--voice", "id-ID-ArdiNeural",
        "--rate=-5%",
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
    lines_renungan = wrap_text(item['renungan'], font_renungan)
    lines_cta = wrap_text(f"💬 {item['cta']}", font_cta)
    
    y = 380  # Posisi awal untuk Referensi Kitab

    # 1. Render Referensi Kitab (Warna Emas/Gold)
    for line in lines_ref:
        try:
            w = draw.textlength(line, font=font_ref)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ref)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y + ay), line, font=font_ref, fill="black")
        draw.text((x, y), line, font=font_ref, fill="#FFD700")
        y += 65

    y += 25  # Jarak aman

    # 2. Render Ayat Alkitab (Warna Putih)
    for line in lines_ayat:
        try:
            w = draw.textlength(line, font=font_ayat)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ayat)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y + ay), line, font=font_ayat, fill="black")
        draw.text((x, y), line, font=font_ayat, fill="white")
        y += 58

    y += 35  # Jarak aman ke renungan

    # 3. Render Renungan Singkat (Warna Silver)
    for line in lines_renungan:
        try:
            w = draw.textlength(line, font=font_renungan)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_renungan)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y + ay), line, font=font_renungan, fill="black")
        draw.text((x, y), line, font=font_renungan, fill="#E0E0E0")
        y += 52

    # 4. Render CTA (Warna Cyan di Bagian Bawah)
    y_cta = 1450
    for line in lines_cta:
        try:
            w = draw.textlength(line, font=font_cta)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_cta)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y_cta + ay), line, font=font_cta, fill="black")
        draw.text((x, y_cta), line, font=font_cta, fill="cyan")
        y_cta += 50

    img.save(output_path)
    return output_path

# --- 5. EDITOR VIDEO UTAMA ---
def render_short_video(bg_video_path, audio_path, item, output_video, index):
    print(f"[{index}/5] 🎬 Merakit video latar Pexels & Teks...")
    
    # Validasi file sumber sebelum dirender
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        raise Exception(f"File audio {audio_path} tidak valid atau kosong!")
    if not os.path.exists(bg_video_path) or os.path.getsize(bg_video_path) < 50000:
        raise Exception(f"File video latar {bg_video_path} tidak valid atau kosong!")

    audio = AudioFileClip(audio_path)
    video_duration = audio.duration + 1.5 
    
    video_clip = VideoFileClip(bg_video_path)
    
    if video_clip.duration < video_duration:
        n_loops = int(video_duration // video_clip.duration) + 1
        video_clip = concatenate_videoclips([video_clip] * n_loops)
        
    video_clip = video_clip.subclipped(0, video_duration)
    video_clip = video_clip.resized(height=1920).cropped(x_center=video_clip.w/2, y_center=video_clip.h/2, width=1080, height=1920)
    
    overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.5).with_duration(video_duration)
    
    txt_img_path = os.path.join(BASE_DIR, f"text_overlay_temp_{index}.png")
    create_text_overlay_image(item, txt_img_path)
    
    if not os.path.exists(txt_img_path) or os.path.getsize(txt_img_path) == 0:
        raise Exception("Gagal membuat gambar overlay teks!")
        
    txt_clip = ImageClip(txt_img_path).with_duration(video_duration)
    
    progress_bar = ColorClip(size=(1080, 15), color=(255, 215, 0)).with_duration(video_duration)
    progress_bar = progress_bar.with_position(lambda t: (int(-1080 + (1080 * (t / video_duration))), 'bottom'))

    video = CompositeVideoClip([video_clip, overlay, txt_clip, progress_bar]).with_audio(audio)
    
    try:
        # Menggunakan preset "medium" agar enkoding lebih stabil dan menghindari file 0 byte
        video.write_videofile(
            output_video, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="medium",
            audio_fps=44100,
            pixel_format="yuv420p"
        )
    except Exception as e:
        print(f"⚠️ FFmpeg Error pada video {index}: {e}")
    
    try:
        video.close()
        audio.close()
        video_clip.close()
        if os.path.exists(txt_img_path):
            os.remove(txt_img_path)
    except Exception:
        pass
        
    time.sleep(5)
    
    file_size = os.path.getsize(output_video) if os.path.exists(output_video) else 0
    print(f"📁 Ukuran file {output_video}: {file_size} bytes")
    
    if file_size < 50000:
        if os.path.exists(output_video):
            os.remove(output_video)
        raise Exception(f"File {output_video} gagal dibuat atau ukurannya korup/0 byte!")
        
    return output_video, video_duration

# --- 6. FACEBOOK UPLOADER ---
def upload_to_facebook(video_path, caption, index):
    print(f"[{index}/5] 🚀 Mengunggah ke Facebook Reels...")
    page_id = os.environ.get("FB_PAGE_ID")
    access_token = os.environ.get("FB_ACCESS_TOKEN")
    
    init_url = f"https://graph.facebook.com/v18.0/{page_id}/video_reels"
    init_payload = {"upload_phase": "start", "access_token": access_token}
    init_res = requests.post(init_url, data=init_payload).json()
    
    if "video_id" not in init_res:
        raise Exception(f"Gagal inisialisasi API: {init_res}")
        
    video_fbid = init_res["video_id"]
    upload_url = init_res["upload_url"]
    
    file_size = os.path.getsize(video_path)
    with open(video_path, 'rb') as f:
        video_data = f.read()
        
    headers = {
        'Authorization': f'OAuth {access_token}',
        'offset': '0',
        'file_size': str(file_size),
        'Content-Type': 'application/octet-stream'
    }
    
    requests.post(upload_url, headers=headers, data=video_data)
    print("   -> Menunggu server Meta memproses video (15 detik)...")
    time.sleep(15)
    
    publish_url = f"https://graph.facebook.com/v18.0/{page_id}/video_reels"
    publish_payload = {
        "access_token": access_token,
        "video_id": video_fbid,
        "upload_phase": "finish",
        "video_state": "PUBLISHED",
        "description": caption
    }
    
    pub_res = requests.post(publish_url, data=publish_payload).json()
    if "success" in pub_res and pub_res["success"]:
        print(f"[{index}/5] 🎉 BERHASIL DIUNGGAH KE FACEBOOK REELS!\n")
    else:
        raise Exception(f"Gagal mempublikasikan Reels: {pub_res}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("⚡ MEMULAI BOT AYAT ALKITAB GROQ AI (5 VIDEO) ⚡\n")
    
    generated_batch = generate_dynamic_content(num_videos=5)
    
    print(f"⚡ MEMPROSES {len(generated_batch)} VIDEO BARU ⚡\n")
    
    for i, item in enumerate(generated_batch, 1):
        try:
            print(f"--- MENGERJAKAN VIDEO {i} DARI 5 ---")
            suara_naskah = f"Renungan Firman Tuhan. {item['ref']}. {item['ayat']}. {item['renungan']} {item['cta']}"
            
            video_bg_file = os.path.join(BASE_DIR, f"stock_bg_{i}.mp4")
            audio_file = os.path.join(BASE_DIR, f"voice_bible_{i}.mp3")
            video_file = os.path.join(BASE_DIR, f"final_reels_{i}.mp4")
            
            caption = f"📖 Renungan Harian Firman Tuhan: {item['ref']}\n\n\"{item['ayat']}\"\n\n{item['renungan']}\n\n{item['cta']}\n\n#firmantuhan #renunganharian #ayatalkitab #rohanikristen #saatteduh #reels"
            
            download_pexels_video(item['pexels_query'], video_bg_file)
            generate_ai_voice(suara_naskah, i, audio_file)
            render_short_video(video_bg_file, audio_file, item, video_file, i)
            
            if os.path.exists(video_file) and os.path.getsize(video_file) > 50000:
                upload_to_facebook(video_file, caption, i)
            else:
                raise Exception("File video hilang atau ukurannya 0 byte sebelum di-upload!")
            
            mark_verse_as_used(item['ref'])
            gc.collect()
            
            if i < len(generated_batch):
                print("⏳ Jeda 60 detik untuk keamanan anti-spam...\n")
                time.sleep(60)
                
        except Exception as e:
            print(f"❌ Kesalahan pada video ke-{i}: {e}\n")
            gc.collect()
