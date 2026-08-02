import os
import time
import random
import requests
import urllib.parse
import subprocess
import gc
import textwrap
from bs4 import BeautifulSoup
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
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def mark_verse_as_used(verse_ref):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{verse_ref}\n")

# --- FUNGSI AMBIL AYAT DARI API ALTERNATIF YANG LEBIH FLEKSIBEL ---
def fetch_api_bible_verse(reference_query):
    """
    Mengambil isi ayat Alkitab dari Alkitab API publik secara langsung.
    Contoh input: "Yohanes 3:16", "1 Yohanes 4:4", "Mazmur 23:1"
    """
    print(f"📖 Mengambil teks resmi Alkitab untuk: {reference_query}...")
    try:
        # Menggunakan API Alkitab Terjemahan Baru (TB) publik yang sangat toleran terhadap format penulisan
        encoded_ref = urllib.parse.quote(reference_query)
        url = f"https://api.alkitab.app/v1/passage?search={encoded_ref}&translation=TB"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            # Memeriksa struktur respons API
            if "verses" in data and len(data["verses"]) > 0:
                # Menggabungkan ayat jika lebih dari satu ayat
                verse_texts = [v.get("text", "") for v in data["verses"]]
                clean_text = " ".join(verse_texts).strip()
                if len(clean_text) > 5:
                    print(f"✅ Berhasil memverifikasi: {clean_text[:60]}...")
                    return clean_text
            elif "text" in data:
                clean_text = data["text"].strip()
                if len(clean_text) > 5:
                    print(f"✅ Berhasil memverifikasi: {clean_text[:60]}...")
                    return clean_text
                    
        # CADANGAN KEDUA: Menggunakan bolls.life API secara langsung jika API utama butuh format lain
        print("⚠️ Mencoba jalur pencarian alternatif bolls.life...")
        parts = reference_query.split()
        if len(parts) >= 2:
            verse_part = parts[-1]
            book_part = " ".join(parts[:-1])
            if ":" in verse_part:
                ch, vs = verse_part.split(":")
                alt_url = f"https://bolls.life/find-verse/TB/{urllib.parse.quote(book_part)}/{ch}/{vs}/"
                alt_res = requests.get(alt_url, timeout=10)
                if alt_res.status_code == 200:
                    alt_data = alt_res.json()
                    if isinstance(alt_data, list) and len(alt_data) > 0:
                        raw_text = alt_data[0].get("text", "")
                        clean_text = BeautifulSoup(raw_text, "html.parser").get_text(strip=True)
                        if len(clean_text) > 5:
                            print(f"✅ Berhasil memverifikasi dari jalur alternatif: {clean_text[:60]}...")
                            return clean_text
                            
    except Exception as e:
        print(f"⚠️ Gagal menghubungkan ke Alkitab API: {e}")
        
    return None

# --- 1. GROQ AI: GENERATOR 3 VIDEO ---
def generate_dynamic_content(num_videos=3):
    print(f"🕊️ Meminta Groq Llama-3 (8B Instant) meracik referensi ayat & kueri video Pexels...")
    
    used_verses = get_used_verses()
    history_context = "\n".join(used_verses[-30:]) if used_verses else "(Belum ada riwayat)"
    
    prompt = f"""
    Bertindaklah sebagai pembuat konten rohani Kristen. Berikan beberapa referensi Kitab dan Ayat Alkitab populer yang menguatkan (contoh format: "Yesaya 41:10", "Filipi 4:6", "Mazmur 23:1", "1 Yohanes 4:4"), beserta renungan singkat dan kata kunci video Pexels. Berikan cadangan referensi lebih dari {num_videos} jika diperlukan.
    
    ATURAN MUTLAK: 
    1. Jangan gunakan referensi ayat ini: {history_context}
    2. Kalimat renungan HARUS SANGAT SINGKAT (1 kalimat pendek).
    
    Format wajib persis seperti ini:
    
    REF: [Referensi Kitab dan Ayat yang valid, cth: Yesaya 41:10]
    RENUNGAN: [1 kalimat pendek renungan yang menguatkan iman]
    CTA: [Ajakan interaksi singkat, cth: Tulis 'Amin' di komentar.]
    PEXELS_QUERY: [Kata kunci bahasa Inggris singkat untuk latar Pexels, cth: "peaceful nature sunrise"]
    ---
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
    chunks = raw_text.split("---")
    
    for chunk in chunks:
        if len(batch) >= num_videos: 
            break
        lines = [line.strip() for line in chunk.strip().split("\n") if line.strip()]
        if not lines: 
            continue
        
        ref = ""
        renungan = "Tuhan tidak pernah meninggalkanmu."
        cta = "Ketik 'Amin' di komentar."
        pexels_query = "peaceful nature sunrise"
        
        for line in lines:
            if line.startswith("REF:"): ref = line.replace("REF:", "").strip()
            elif line.startswith("RENUNGAN:"): renungan = line.replace("RENUNGAN:", "").strip()
            elif line.startswith("CTA:"): cta = line.replace("CTA:", "").strip()
            elif line.startswith("PEXELS_QUERY:"): pexels_query = line.replace("PEXELS_QUERY:", "").strip()
                
        if not ref:
            continue

        # AMBIL ISI AYAT DARI API
        official_ayat = fetch_api_bible_verse(ref)
        
        if not official_ayat:
            print(f"❌ Peringatan: Referensi '{ref}' gagal diverifikasi di Alkitab API. Melewati ayat ini.")
            continue
            
        batch.append({
            "id": f"BIBLE_{int(time.time())}_{len(batch)}",
            "ref": ref,
            "ayat": official_ayat,
            "renungan": renungan,
            "cta": cta,
            "pexels_query": pexels_query
        })
        
    if len(batch) == 0:
        raise Exception("❌ Gagal mendapatkan satupun ayat terverifikasi dari Alkitab API.")
        
    print(f"✅ Berhasil menyiapkan {len(batch)} Naskah terverifikasi 100% akurat dari Alkitab API!")
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

# --- 2. PEXELS VIDEO DOWNLOADER (DIPERKUAT DENGAN CADANGAN OTOMATIS) ---
def download_pexels_video(query, output_filename):
    print(f"🎬 Mencari video latar rohani di Pexels untuk: '{query}'...")
    api_key = os.environ.get("PEXELS_API_KEY")
    
    if not api_key:
        print("⚠️ Peringatan: PEXELS_API_KEY tidak ditemukan di environment variables!")
    
    headers = {"Authorization": api_key} if api_key else {}
    safe_query = urllib.parse.quote(query.strip() if query else "peaceful nature")
    url = f"https://api.pexels.com/videos/search?query={safe_query}&orientation=portrait&per_page=5"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "videos" in data and len(data["videos"]) > 0:
                video_obj = random.choice(data["videos"])
                video_files = video_obj["video_files"]
                hd_file = next((v for v in video_files if v.get("quality") == "hd"), video_files[0])
                video_url = hd_file["link"]
                
                vid_data = requests.get(video_url, timeout=30).content
                with open(output_filename, 'wb') as f:
                    f.write(vid_data)
                    
                if os.path.exists(output_filename) and os.path.getsize(output_filename) > 50000:
                    print("✅ Stok video Pexels berhasil diunduh dan divalidasi!")
                    return output_filename
    except Exception as e:
        print(f"⚠️ Peringatan unduhan Pexels: {e}")

    # PENCADANGAN DARURAT (FALLBACK) AGAR VIDEO TIDAK KOSONG
    print("⚠️ Menggunakan video latar cadangan universal (nature cinematic)...")
    fallback_url = "https://api.pexels.com/videos/search?query=nature+cinematic+vertical&orientation=portrait&per_page=1"
    try:
        fallback_res = requests.get(fallback_url, headers=headers, timeout=15).json()
        if "videos" in fallback_res and len(fallback_res["videos"]) > 0:
            video_obj = fallback_res["videos"][0]
            hd_file = video_obj["video_files"][0]
            vid_data = requests.get(hd_file["link"], timeout=30).content
            with open(output_filename, 'wb') as f:
                f.write(vid_data)
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 50000:
                print("✅ Video cadangan berhasil digunakan!")
                return output_filename
    except Exception as ex:
        print(f"❌ Gagal total mengambil video cadangan: {ex}")
        
    raise Exception("Gagal total mengunduh video dari Pexels API maupun cadangan.")

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

# --- 4. TEXT OVERLAY GENERATOR ---
def create_text_overlay_image(item, output_path, img_size=(1080, 1920)):
    img = Image.new("RGBA", img_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_path = get_custom_font()
    font_ref = ImageFont.truetype(font_path, 75)
    font_ayat = ImageFont.truetype(font_path, 55)
    font_renungan = ImageFont.truetype(font_path, 48)
    font_cta = ImageFont.truetype(font_path, 45)
    
    lines_ref = textwrap.wrap(f"✨ {item['ref']} ✨", width=22)
    lines_ayat = textwrap.wrap(f'"{item["ayat"]}"', width=28)
    lines_renungan = textwrap.wrap(item['renungan'], width=34)
    lines_cta = textwrap.wrap(f"💬 {item['cta']}", width=38)
    
    y = 350  
    for line in lines_ref:
        try:
            w = draw.textlength(line, font=font_ref)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ref)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y + ay), line, font=font_ref, fill="black")
        draw.text((x, y), line, font=font_ref, fill="#FFD700")
        y += 95

    y += 40  

    for line in lines_ayat:
        try:
            w = draw.textlength(line, font=font_ayat)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_ayat)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-4,0), (4,0), (0,-4), (0,4), (-4,-4), (4,4), (-4,4), (4,-4)]:
            draw.text((x + ax, y + ay), line, font=font_ayat, fill="black")
        draw.text((x, y), line, font=font_ayat, fill="white")
        y += 75

    y += 50  

    for line in lines_renungan:
        try:
            w = draw.textlength(line, font=font_renungan)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_renungan)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y + ay), line, font=font_renungan, fill="black")
        draw.text((x, y), line, font=font_renungan, fill="#E0E0E0")
        y += 65

    y_cta = 1550
    for line in lines_cta:
        try:
            w = draw.textlength(line, font=font_cta)
        except AttributeError:
            w = draw.textbbox((0, 0), line, font=font_cta)[2]
        x = (img_size[0] - w) // 2
        for ax, ay in [(-3,0), (3,0), (0,-3), (0,3), (-3,-3), (3,3), (-3,3), (3,-3)]:
            draw.text((x + ax, y_cta + ay), line, font=font_cta, fill="black")
        draw.text((x, y_cta), line, font=font_cta, fill="cyan")
        y_cta += 60

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
    print("⚡ MEMULAI BOT AYAT ALKITAB API (3 VIDEO) ⚡\n")
    
    bg_music_file = os.path.join(BASE_DIR, "bg_music.mp3")
    if not os.path.exists(bg_music_file):
        print("⚠️ Info: File 'bg_music.mp3' tidak ditemukan. Video akan berjalan tanpa musik latar.")
        bg_music_file = None
    
    # Menghasilkan 3 video terverifikasi API per eksekusi
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
