import os
import time
import random
import requests
import urllib.parse
import subprocess
import gc
from groq import Groq
from moviepy import (
    AudioFileClip,
    VideoFileClip,
    CompositeVideoClip,
    ColorClip,
    ImageClip,
    concatenate_videoclips,
    CompositeAudioClip,
)
from PIL import Image, ImageDraw, ImageFont

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

# --- 1. GROQ AI: GENERATOR 3 VIDEO ---
def generate_dynamic_content(num_videos=3):
    print(f"🕊️ Meminta Groq Llama-3 (8B Instant) meracik {num_videos} naskah Firman Tuhan & kueri video Pexels...")
    
    used_verses = get_used_verses()
    history_context = "\n".join(used_verses[-30:]) if used_verses else "(Belum ada riwayat, buat topik bebas)"
    
    prompt = f"""
    Bertindaklah sebagai pembuat konten rohani Kristen yang mendalam, penuh kasih, dan menguatkan iman.
    Buatlah {num_videos} naskah video pendek (Reels) berisi ayat Alkitab beserta renungan singkat yang menyejukkan hati.
    
    ATURAN MUTLAK: 
    1. Kalimat renungan HARUS SANGAT SINGKAT, padat, puitis, maksimal 1 kalimat pendek agar muat di layar video.
    2. Dilarang keras membuat naskah dengan referensi ayat atau tema yang mirip dengan daftar ini: {history_context}
    
    Gunakan pemisah '---' antar naskah. Format wajib persis seperti ini:
    
    REF: [Referensi Kitab dan Ayat, contoh: Yesaya 41:10]
    AYAT: [Isi ayat Alkitab yang menyentuh hati dan relevan]
    RENUNGAN: [1 kalimat pendek renungan yang menguatkan iman]
    CTA: [Ajakan interaksi singkat, contoh: Tulis 'Amin' di komentar.]
    PEXELS_QUERY: [Kata kunci bahasa Inggris untuk mencari video background rohani/tenang di Pexels, contoh: "peaceful mountain sunrise cinematic drone", "calm ocean waves sunset cinematic"]
    """
    
    raw_text = ""
    for attempt in range(3):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Anda adalah asisten AI rohani yang patuh pada format instruksi."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.7,
                max_tokens=1500,
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
        
        ref = f"YESAYA 4{i}:10"
        ayat = "Janganlah takut, sebab Aku menyertai engkau."
        renungan = "Tuhan tidak pernah meninggalkanmu."
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
        
    print(f"✅ Berhasil meracik {len(batch)} Naskah Firman Tuhan Unik!")
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

# --- 2. PEXELS VIDEO DOWNLOADER ---
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

# --- 3. PENGUBAH FORMAT AYAT & AI NEURAL VOICE ---
def fix_verse_for_tts(ref_text):
    tts_text = ref_text
    if ":" in tts_text:
        parts = tts_text.split(":")
        book_chapter = parts[0].strip()
        verse = parts[1].strip()
        tts_text = f"{book_chapter} ayat {verse}"
    return f"Bacaan Firman Tuhan dari {tts_text}."

def generate_ai_voice(full_text, index, output_audio):
    print(f"[{index}] 🎙️ Menyuarakan firman Tuhan...")
    cmd = [
        "edge-tts",
        "--voice", "id-ID-ArdiNeural",
        "--rate=-5%",
        "--text", full_text,
        "--write-media", output_audio
    ]
    subprocess.run(cmd, check=True)
    return output_audio

# --- 4. TEXT OVERLAY GENERATOR (UKURAN FONT DIPERBESAR) ---
def create_text_overlay_image(item, output_path, img_size=(1080, 1920)):
    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_path = get_custom_font()
    # UKURAN FONT DIPERBESAR AGAR SANGAT JELAS DIBACA DI LAYAR HP
    font_ref = ImageFont.truetype(font_path, 60)
    font_ayat = ImageFont.truetype(font_path, 48)
    font_renungan = ImageFont.truetype(font_path, 42)
    font_cta = ImageFont.truetype(font_path, 40)
    
    def chunk_text_by_word_count(text, words_per_line=3):
        words = text.split()
        lines = []
        for i in range(0, len(words), words_per_line):
            line = " ".join(words[i:i+words_per_line])
            lines.append(line)
        return lines

    lines_ref = [f"✨ {item['ref']} ✨"]
    lines_ayat = chunk_text_by_word_count(f'"{item["ayat"]}"', words_per_line=3)
    lines_renungan = chunk_text_by_word_count(item['renungan'], words_per_line=3)
    lines_cta = chunk_text_by_word_count(f"💬 {item['cta']}", words_per_line=3)
    
    y = 300  

    for line in lines_ref:
        try:
            w = draw.textlength(line, font=font_ref)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ref)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y + ay), line, font=font_ref, fill="black")
        draw.text((x, y), line, font=font_ref, fill="#FFD700")
        y += 85

    y += 20  

    for line in lines_ayat:
        try:
            w = draw.textlength(line, font=font_ayat)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ayat)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y + ay), line, font=font_ayat, fill="black")
        draw.text((x, y), line, font=font_ayat, fill="white")
        y += 70

    y += 30  

    for line in lines_renungan:
        try:
            w = draw.textlength(line, font=font_renungan)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_renungan)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y + ay), line, font=font_renungan, fill="black")
        draw.text((x, y), line, font=font_renungan, fill="#E0E0E0")
        y += 60

    y_cta = 1500
    for line in lines_cta:
        try:
            w = draw.textlength(line, font=font_cta)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_cta)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y_cta + ay), line, font=font_cta, fill="black")
        draw.text((x, y_cta), line, font=font_cta, fill="cyan")
        y_cta += 55

    img.save(output_path)
    return output_path

# --- 5. EDITOR VIDEO UTAMA ---
def render_short_video(bg_video_path, audio_path, item, output_video, index, bg_music_path=None):
    print(f"[{index}] 🎬 Merakit video latar Pexels, Teks & Musik...")
    
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
        raise Exception(f"File audio {audio_path} tidak valid atau kosong!")
    if not os.path.exists(bg_video_path) or os.path.getsize(bg_video_path) < 50000:
        raise Exception(f"File video latar {bg_video_path} tidak valid atau kosong!")

    voice_audio = AudioFileClip(audio_path)
    video_duration = voice_audio.duration + 1.5 
    
    if bg_music_path and os.path.exists(bg_music_path):
        print("   -> Memasang musik latar belakang rohani...")
        bg_music = AudioFileClip(bg_music_path).with_duration(video_duration).with_volume_scaled(0.12)
        final_audio = CompositeAudioClip([voice_audio, bg_music])
    else:
        final_audio = voice_audio
    
    video_clip = VideoFileClip(bg_video_path)
    
    if video_clip.duration < video_duration:
        n_loops = int(video_duration // video_clip.duration) + 1
        video_clip = concatenate_videoclips([video_clip] * n_loops)
        
    video_clip = video_clip.subclipped(0, video_duration)
    video_clip = video_clip.resized(height=1920).cropped(x_center=video_clip.w/2, y_center=video_clip.h/2, width=1080, height=1920)
    
    overlay = ColorClip(size=(1080, 1920), color=(0,0,0)).with_opacity(0.55).with_duration(video_duration)
    
    txt_img_path = os.path.join(BASE_DIR, f"text_overlay_temp_{index}.png")
    create_text_overlay_image(item, txt_img_path)
    
    if not os.path.exists(txt_img_path) or os.path.getsize(txt_img_path) == 0:
        raise Exception("Gagal membuat gambar overlay teks!")
        
    txt_clip = ImageClip(txt_img_path).with_duration(video_duration)
    
    progress_bar = ColorClip(size=(1080, 15), color=(255, 215, 0)).with_duration(video_duration)
    progress_bar = progress_bar.with_position(lambda t: (int(-1080 + (1080 * (t / video_duration))), 'bottom'))

    video = CompositeVideoClip([video_clip, overlay, txt_clip, progress_bar], size=(1080, 1920)).with_audio(final_audio)
    
    try:
        video.write_videofile(
            output_video, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="medium",
            bitrate="5000k",
            audio_fps=44100,
            pixel_format="yuv420p",
            threads=4
        )
    except Exception as e:
        print(f"⚠️ FFmpeg Error pada video {index}: {e}")
    
    try:
        video.close()
        voice_audio.close()
        video_clip.close()
        if os.path.exists(txt_img_path):
            os.remove(txt_img_path)
    except Exception:
        pass
        
    time.sleep(7)
    
    file_size = os.path.getsize(output_video) if os.path.exists(output_video) else 0
    print(f"📁 Ukuran file {output_video}: {file_size} bytes")
    
    if file_size < 50000:
        if os.path.exists(output_video):
            os.remove(output_video)
        raise Exception(f"File {output_video} gagal dibuat atau ukurannya korup/0 byte!")
        
    return output_video, video_duration

# --- 6. FACEBOOK UPLOADER ---
def upload_to_facebook(video_path, caption, index):
    print(f"[{index}] 🚀 Mengunggah ke Facebook Reels...")
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
        print(f"[{index}] 🎉 BERHASIL DIUNGGAH KE FACEBOOK REELS!\n")
    else:
        raise Exception(f"Gagal mempublikasikan Reels: {pub_res}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("⚡ MEMULAI BOT AYAT ALKITAB GROQ AI (3 VIDEO) ⚡\n")
    
    bg_music_file = os.path.join(BASE_DIR, "bg_music.mp3")
    if not os.path.exists(bg_music_file):
        print("⚠️ Info: File 'bg_music.mp3' tidak ditemukan. Video akan berjalan tanpa musik latar.")
        bg_music_file = None
    
    # Menghasilkan 3 video per eksekusi
    generated_batch = generate_dynamic_content(num_videos=3)
    
    print(f"⚡ MEMPROSES {len(generated_batch)} VIDEO BARU ⚡\n")
    
    for i, item in enumerate(generated_batch, 1):
        try:
            print(f"--- MENGERJAKAN VIDEO {i} DARI {len(generated_batch)} ---")
            
            clean_spoken_ref = fix_verse_for_tts(item['ref'])
            suara_naskah = f"{clean_spoken_ref} \"{item['ayat']}\" {item['renungan']} {item['cta']}"
            
            video_bg_file = os.path.join(BASE_DIR, f"stock_bg_{i}.mp4")
            audio_file = os.path.join(BASE_DIR, f"voice_bible_{i}.mp3")
            video_file = os.path.join(BASE_DIR, f"final_reels_{i}.mp4")
            
            caption = f"📖 Renungan Harian Firman Tuhan: {item['ref']}\n\n\"{item['ayat']}\"\n\n{item['renungan']}\n\n{item['cta']}\n\n#firmantuhan #renunganharian #ayatalkitab #rohanikristen #saatteduh #reels"
            
            download_pexels_video(item['pexels_query'], video_bg_file)
            generate_ai_voice(suara_naskah, i, audio_file)
            render_short_video(video_bg_file, audio_file, item, video_file, i, bg_music_file)
            
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
