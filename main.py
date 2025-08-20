# app.py — YouTube Downloader Pro (Portfolio Edition)
# Dépendances: yt-dlp, customtkinter, pillow
# Arbo recommandée:
# convertisseur-pro/
#   ├─ app.py
#   ├─ icon.ico        (optionnel)
#   ├─ history.json    (auto-créé)
#   └─ bin/
#       └─ ffmpeg.exe  (et ffprobe.exe si dispo)
#   └─ src/
#       ├─ logo.png
#       ├─ mp3.png
#       ├─ mp4.png
#       ├─ batch.png
#       └─ folder.png

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading, os, sys, json, re, time
import yt_dlp
from PIL import Image
from pathlib import Path

APP_TITLE = "YouTube Downloader Pro"

data_dir = Path.home() / ".main.py"
data_dir.mkdir(exist_ok=True)

HISTORY_FILE = data_dir / "history.json"

# ---------- Langues ----------
LANGUAGES = {
    "fr": {
        "download_mp3": "Télécharger MP3",
        "download_mp4": "Télécharger MP4",
        "batch": "Batch (.txt)",
        "open_folder": "Ouvrir dossier",
        "url_label": "URL / Playlist :",
        "quality_mp3": "Qualité MP3:",
        "quality_mp4": "Qualité MP4:",
        "mode_batch": "Mode Batch:",
        "playlist": "Mode playlist (dossier auto)",
        "keep_raw": "Garder le fichier brut (.m4a/.webm)",
        "journal": "Journal d'activité",
        "history": "Historique",
        "theme_dark": "Thème : Sombre",
        "theme_light": "Thème : Clair",
        "success": "Téléchargement terminé !",
        "success_info": "Votre fichier est prêt dans le dossier choisi.",
        "error_url": "Veuillez entrer une URL (YouTube ou playlist).",
        "error_file": "Le fichier ne contient aucune URL.",
        "error_dl": "Le téléchargement a échoué.",
        "info_batch": "téléchargements réussis.",
        "info_history": "Historique vidé.",
        "conversion": "Conversion en cours...",
        "preparing": "Préparation...",
        "paste": "Coller",
        "clear_history": "❌ Vider l'historique"
    },
    "en": {
        "download_mp3": "Download MP3",
        "download_mp4": "Download MP4",
        "batch": "Batch (.txt)",
        "open_folder": "Open folder",
        "url_label": "URL / Playlist:",
        "quality_mp3": "MP3 Quality:",
        "quality_mp4": "MP4 Quality:",
        "mode_batch": "Batch Mode:",
        "playlist": "Playlist mode (auto folder)",
        "keep_raw": "Keep raw file (.m4a/.webm)",
        "journal": "Activity log",
        "history": "History",
        "theme_dark": "Theme: Dark",
        "theme_light": "Theme: Light",
        "success": "Download complete!",
        "success_info": "Your file is ready in the chosen folder.",
        "error_url": "Please enter a URL (YouTube or playlist).",
        "error_file": "The file contains no URL.",
        "error_dl": "Download failed.",
        "info_batch": "downloads succeeded.",
        "info_history": "History cleared.",
        "conversion": "Converting...",
        "preparing": "Preparing...",
        "paste": "Paste",
        "clear_history": "❌ Clear history"
    }
}
current_lang = "fr"

def tr(key):
    return LANGUAGES[current_lang].get(key, key)

# ---------- FFmpeg embarqué ----------
if getattr(sys, 'frozen', False):
    FFMPEG_DIR = os.path.join(sys._MEIPASS, "bin")
else:
    FFMPEG_DIR = os.path.join(os.path.dirname(__file__), "bin")

def ffmpeg_path_candidates():
    # yt-dlp accepte un dossier ou un binaire; on tente dossier local sinon PATH système
    if os.path.isdir(FFMPEG_DIR):
        return FFMPEG_DIR
    return None  # laisser yt-dlp trouver ffmpeg dans le PATH

# ---------- Utilitaires ----------
def ensure_history():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def load_history():
    ensure_history()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(history_list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_list, f, ensure_ascii=False, indent=2)

def add_history_entry(title, url, file_path):
    try:
        history = load_history()
        history.append({
            "title": title or "",
            "url": url or "",
            "file": file_path or "",
            "date": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        save_history(history)
    except Exception as e:
        log_message(f"Impossible d'ajouter à l'historique: {e}", "WARN")

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", (name or "")).strip()

def open_path(path):
    if not path:
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        log_message(f"Ouverture impossible: {e}", "WARN")

# ---------- Logs UI ----------
text_log = None  # défini après création UI

def log_message(msg, tag="INFO"):
    global text_log
    if text_log is None:
        print(f"[{tag}] {msg}")
        return
    try:
        text_log.configure(state="normal")
        text_log.insert("end", f"[{tag}] {msg}\n")
        text_log.see("end")
    finally:
        text_log.configure(state="disabled")

# ---------- Popups ----------
def show_error_popup(msg, title="Erreur"):
    try:
        messagebox.showerror(title, msg)
    except Exception:
        log_message(f"{title}: {msg}", "ERROR")

def show_info_popup(msg, title="Info"):
    try:
        messagebox.showinfo(title, msg)
    except Exception:
        log_message(f"{title}: {msg}", "INFO")

def show_success_popup():
    popup = ctk.CTkToplevel(root)
    popup.title(tr("success"))
    popup.geometry("400x250")
    popup.resizable(False, False)
    popup.configure(fg_color="#23272f")
    try:
        popup.iconbitmap("icon.ico")
    except Exception:
        pass
    ctk.CTkLabel(popup, text=tr("success"), font=("Segoe UI", 20, "bold")).pack(pady=(30, 10))
    ctk.CTkLabel(popup, text=tr("success_info"), font=("Segoe UI", 14)).pack(pady=(0, 18))
    ctk.CTkButton(popup, text="OK", command=popup.destroy).pack(pady=(10, 20))

# ---------- yt-dlp Helpers ----------
current_file_hint = [None]   # dernière piste de fichier reçue par hook
last_download_folder = [None]

def progress_hook(d):
    # capture indice de fichier si fourni
    fn = d.get("filename") or (d.get("info_dict") or {}).get("_filename")
    if fn:
        current_file_hint[0] = fn

    status = d.get("status")
    if status == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes", 0)
        if total and total > 0:
            try:
                progress_bar.set(downloaded / total)
            except Exception:
                pass
        percent = d.get("_percent_str", "0%")
        m = re.search(r"(\d{1,3}\.\d)%", percent)
        if m:
            percent_clean = f"{int(float(m.group(1)))}%"
        else:
            percent_clean = percent
        try:
            label_status.configure(text=f"⬇️ {tr('preparing') if total == 0 else 'Téléchargement... ' + percent_clean}")
        except Exception:
            pass
    elif status == "finished":
        try:
            progress_bar.set(1)
            label_status.configure(text=tr("conversion"))
        except Exception:
            pass

def guess_final_file(path_hint: str):
    if not path_hint:
        return None
    base, _ = os.path.splitext(path_hint)
    for p in [
        path_hint,
        base + ".mp3", base + ".m4a", base + ".mp4",
        base + ".webm", base + ".mkv", base + ".m4v"
    ]:
        if os.path.exists(p):
            return p
    return None

def base_ydl_opts(outtmpl, keep_raw=False):
    ffmpeg_loc = ffmpeg_path_candidates()
    return {
        "outtmpl": outtmpl,
        "progress_hooks": [progress_hook],
        **({"ffmpeg_location": ffmpeg_loc} if ffmpeg_loc else {}),
        "sanitize_filename": True,
        "windowsfilenames": True,
        "trim_file_name": 200,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "geo_bypass": True,
        "ignoreerrors": False,
        "overwrites": True,
        "keepvideo": keep_raw,       # garder le fichier brut si demandé
        "noprogress": False,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36")
        }
    }

def build_formats(mode, kbps_audio, res_video):
    if mode == "mp3":
        fmt = "bestaudio[ext=m4a]/bestaudio/best"
        post = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(kbps_audio),
        }]
        extra = {}
    else:
        fmt = f"bestvideo[height<={res_video}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        post = [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}]  # <-- corrige ici
        extra = {"merge_output_format": "mp4"}
    return fmt, post, extra


# ---------- Téléchargement principal ----------
def do_download_single(url, folder, mode, kbps_audio, res_video, playlist_mode, keep_raw):
    """
    Télécharge UNE URL (vidéo seule ou playlist entière).
    Retourne True si ok, False sinon.
    """
    # Chemin de sortie
    if playlist_mode:
        outtmpl = os.path.join(folder, "%(playlist_title)s", "%(playlist_index)03d - %(title)s.%(ext)s")
    else:
        outtmpl = os.path.join(folder, "%(title)s.%(ext)s")

    fmt, post, extra = build_formats(mode, kbps_audio, res_video)
    ydl_opts = base_ydl_opts(outtmpl, keep_raw)
    ydl_opts.update({
        "format": fmt,
        "postprocessors": post,
        "noplaylist": (not playlist_mode),   # plus fiable que yesplaylist
        **extra
    })

    current_file_hint[0] = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Playlist
            if playlist_mode and info and "entries" in info:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    title = sanitize_filename(entry.get("title", ""))
                    final_guess = guess_final_file(current_file_hint[0]) if current_file_hint[0] else ""
                    add_history_entry(title, entry.get("webpage_url", url), final_guess or "")
            else:
                # Vidéo seule
                title = sanitize_filename((info or {}).get("title", ""))
                final_file = guess_final_file(current_file_hint[0]) if current_file_hint[0] else ""
                add_history_entry(title, url, final_file or "")
        return True
    except Exception as e:
        log_message(f"Erreur yt-dlp: {e}", "ERROR")
        return False

def start_download(mode):
    url = entry_url.get().strip()
    if not url:
        show_error_popup(tr("error_url"))
        return

    folder = filedialog.askdirectory(title="Choisissez un dossier de téléchargement")
    if not folder:
        return
    last_download_folder[0] = folder

    kbps_audio = int(audio_quality_var.get().replace(" kbps", ""))
    res_video = int(video_quality_var.get().replace("p", ""))

    playlist_mode = playlist_var.get()
    keep_raw = keep_raw_var.get()

    def worker():
        try:
            progress_bar.set(0)
            label_status.configure(text=tr("preparing"))
            log_message(f"Dossier: {folder}", "START")
            log_message(f"URL: {url}", "START")
            log_message(f"Mode: {mode.upper()} | Playlist: {playlist_mode} | Keep raw: {keep_raw}", "START")

            ok = do_download_single(url, folder, mode, kbps_audio, res_video, playlist_mode, keep_raw)
            if ok:
                show_success_popup()
                log_message("Téléchargement terminé avec succès ✅", "DONE")
            else:
                show_error_popup(tr("error_dl"))
                log_message("Échec du téléchargement ❌", "ERROR")
        finally:
            progress_bar.set(0)
            label_status.configure(text="")

    threading.Thread(target=worker, daemon=True).start()

# ---------- Batch (.txt) ----------
def start_batch():
    path = filedialog.askopenfilename(
        title="Sélectionnez un fichier .txt contenant une URL par ligne",
        filetypes=[("Texte", "*.txt"), ("Tous les fichiers", "*.*")]
    )
    if not path:
        return

    folder = filedialog.askdirectory(title="Choisissez un dossier de téléchargement")
    if not folder:
        return
    last_download_folder[0] = folder

    kbps_audio = int(audio_quality_var.get().replace(" kbps", ""))
    res_video = int(video_quality_var.get().replace("p", ""))

    playlist_mode = playlist_var.get()
    keep_raw = keep_raw_var.get()

    mode = mode_batch_var.get()

    with open(path, "r", encoding="utf-8") as f:
        urls = [ln.strip() for ln in f.readlines() if ln.strip()]

    if not urls:
        show_error_popup(tr("error_file"))
        return

    def worker():
        success = 0
        total = len(urls)
        for i, url in enumerate(urls, start=1):
            label_status.configure(text=f"Tâche {i}/{total}…")
            log_message(f"({i}/{total}) {url}", "BATCH")
            ok = do_download_single(url, folder, mode, kbps_audio, res_video, playlist_mode, keep_raw)
            if ok:
                success += 1
        show_info_popup(f"✅ {success}/{total} {tr('info_batch')}", title="Batch terminé")
        log_message(f"BATCH terminé: {success}/{total} OK ✅", "DONE")
        progress_bar.set(0)
        label_status.configure(text="")

    threading.Thread(target=worker, daemon=True).start()

# ---------- Thème ----------
def toggle_theme():
    cur = theme_var.get()
    if cur == "Sombre":
        ctk.set_appearance_mode("light")
        theme_var.set("Clair")
    else:
        ctk.set_appearance_mode("dark")
        theme_var.set("Sombre")
    # maj texte bouton selon langue
    theme_btn.configure(text=tr("theme_dark") if theme_var.get() == "Sombre" else tr("theme_light"))

# ---------- Ouvrir dossier ----------
def open_download_folder():
    if last_download_folder[0]:
        open_path(last_download_folder[0])
        return
    folder = filedialog.askdirectory(title="Ouvrir un dossier…")
    if folder:
        open_path(folder)

# ---------- Helpers UI ----------
def load_img(path, size):
    try:
        if os.path.exists(path):
            return ctk.CTkImage(light_image=Image.open(path), size=size)
    except Exception as e:
        log_message(f"Image manquante/illisible: {path} ({e})", "WARN")
    return None

def change_language(lang):
    global current_lang
    current_lang = lang
    # textes
    btn_mp3.configure(text=tr("download_mp3"))
    btn_mp4.configure(text=tr("download_mp4"))
    btn_batch.configure(text=tr("batch"))
    btn_open.configure(text=tr("open_folder"))
    url_label.configure(text=tr("url_label"))
    entry_url.configure(placeholder_text=tr("url_label"))
    paste_btn.configure(text=tr("paste"))
    label_quality_mp3.configure(text=tr("quality_mp3"))
    label_quality_mp4.configure(text=tr("quality_mp4"))
    label_mode_batch.configure(text=tr("mode_batch"))
    chk_playlist.configure(text=tr("playlist"))
    chk_keepraw.configure(text=tr("keep_raw"))
    theme_btn.configure(text=tr("theme_dark") if theme_var.get() == "Sombre" else tr("theme_light"))
    history_btn.configure(text=tr("history"))
    label_journal.configure(text="  " + tr("journal"))

# ---------- UI ----------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

root = ctk.CTk()
root.title(APP_TITLE)
root.geometry("860x640")
root.resizable(False, False)  # <-- Empêche le redimensionnement
try:
    root.iconbitmap("icon.ico")
except Exception:
    pass

# Header
header = ctk.CTkFrame(root)
header.pack(fill="x", padx=12, pady=(12, 0))

logo_img = load_img("./src/logo.png", (80, 80))
logo_lbl = ctk.CTkLabel(header, image=logo_img, text="" if logo_img else "YouTube MP3/MP4")
logo_lbl.pack(side="left", padx=(10, 4), pady=10)

title_lbl = ctk.CTkLabel(header, text="YouTube MP3 / MP4", font=("Segoe UI", 22, "bold"))
title_lbl.pack(side="left", padx=10, pady=10)

theme_var = ctk.StringVar(value="Sombre")
theme_btn = ctk.CTkButton(header, text=tr("theme_dark"), width=150, command=toggle_theme)
theme_btn.pack(side="right", padx=10, pady=10)

lang_var = ctk.StringVar(value="fr")
lang_menu = ctk.CTkOptionMenu(header, values=["fr", "en"], variable=lang_var, width=80,
                              command=lambda l: change_language(l))
lang_menu.pack(side="right", padx=(0, 10), pady=10)

history_btn = ctk.CTkButton(header, text=tr("history"), width=140,
                             command=lambda: show_history())
history_btn.pack(side="right", padx=(0, 10), pady=10)

main = ctk.CTkFrame(root, corner_radius=16)
main.pack(fill="both", expand=True, padx=12, pady=12)

# URL
url_row = ctk.CTkFrame(main)
url_row.pack(pady=(14, 6))
url_label = ctk.CTkLabel(url_row, text=tr("url_label"), font=("Segoe UI", 14))
url_label.grid(row=0, column=0, padx=(0, 8))
entry_url = ctk.CTkEntry(url_row, width=600, height=40, placeholder_text=tr("url_label"))
entry_url.grid(row=0, column=1, padx=(0, 8))
def safe_paste():
    try:
        txt = root.clipboard_get()
    except Exception:
        txt = ""
    entry_url.delete(0, "end")
    entry_url.insert(0, txt)
paste_btn = ctk.CTkButton(url_row, text=tr("paste"), width=90, command=safe_paste)
paste_btn.grid(row=0, column=2)

# Options
opts = ctk.CTkFrame(main)
opts.pack(pady=8)

# Qualité audio
audio_quality_var = ctk.StringVar(value="192 kbps")
label_quality_mp3 = ctk.CTkLabel(opts, text=tr("quality_mp3"))
label_quality_mp3.grid(row=0, column=0, padx=8, pady=6, sticky="e")
audio_menu = ctk.CTkOptionMenu(opts, values=["128 kbps", "192 kbps", "320 kbps"], variable=audio_quality_var, width=140)
audio_menu.grid(row=0, column=1, padx=8, pady=6, sticky="w")

# Qualité vidéo
video_quality_var = ctk.StringVar(value="720p")
label_quality_mp4 = ctk.CTkLabel(opts, text=tr("quality_mp4"))
label_quality_mp4.grid(row=0, column=2, padx=8, pady=6, sticky="e")
video_menu = ctk.CTkOptionMenu(opts, values=["480p", "720p", "1080p"], variable=video_quality_var, width=140)
video_menu.grid(row=0, column=3, padx=8, pady=6, sticky="w")

# Choix du mode batch
mode_batch_var = ctk.StringVar(value="mp3")
label_mode_batch = ctk.CTkLabel(opts, text=tr("mode_batch"))
label_mode_batch.grid(row=2, column=0, padx=8, pady=6, sticky="e")
mode_batch_menu = ctk.CTkOptionMenu(opts, values=["mp3", "mp4"], variable=mode_batch_var, width=140)
mode_batch_menu.grid(row=2, column=1, padx=8, pady=6, sticky="w")

# Checkboxes
playlist_var = ctk.BooleanVar(value=False)
keep_raw_var = ctk.BooleanVar(value=False)
chk_playlist = ctk.CTkCheckBox(opts, text=tr("playlist"), variable=playlist_var)
chk_playlist.grid(row=1, column=0, columnspan=2, padx=8, pady=6, sticky="w")
chk_keepraw = ctk.CTkCheckBox(opts, text=tr("keep_raw"), variable=keep_raw_var)
chk_keepraw.grid(row=1, column=2, columnspan=2, padx=8, pady=6, sticky="w")

# Images pour les boutons
mp3_img = load_img("./src/mp3.png", (24, 24))
mp4_img = load_img("./src/mp4.png", (24, 24))
batch_img = load_img("./src/batch.png", (24, 24))
folder_img = load_img("./src/folder.png", (24, 24))
journal_img = load_img("./src/journal.png", (24, 24))

# Boutons action
btns = ctk.CTkFrame(main)
btns.pack(pady=10)
mode_var = ctk.StringVar(value="mp3")  # utilisé par le batch
btn_mp3 = ctk.CTkButton(btns, text=tr("download_mp3"), width=200, height=42, image=mp3_img,
                        command=lambda: (mode_var.set("mp3"), start_download("mp3")))
btn_mp3.grid(row=0, column=0, padx=8)

btn_mp4 = ctk.CTkButton(btns, text=tr("download_mp4"), width=200, height=42, image=mp4_img,
                        command=lambda: (mode_var.set("mp4"), start_download("mp4")))
btn_mp4.grid(row=0, column=1, padx=8)

btn_batch = ctk.CTkButton(btns, text=tr("batch"), width=160, height=42, image=batch_img, command=start_batch)
btn_batch.grid(row=0, column=2, padx=8)

btn_open = ctk.CTkButton(btns, text=tr("open_folder"), width=160, height=42, image=folder_img, command=open_download_folder)
btn_open.grid(row=0, column=3, padx=8)

# Progress
progress_bar = ctk.CTkProgressBar(main, width=760)
progress_bar.set(0)
progress_bar.pack(pady=(12, 4))

label_status = ctk.CTkLabel(main, text="", font=("Segoe UI", 13))
label_status.pack(pady=(0, 10))

# Logs
label_journal = ctk.CTkLabel(main, text=("  " + tr("journal")), font=("Segoe UI", 14, "italic"),
                             image=journal_img, compound="left")
label_journal.pack()
text_log = ctk.CTkTextbox(main, width=780, height=220, font=("Consolas", 11))
text_log.pack(pady=(6, 10))
text_log.configure(state="disabled")

# Historique viewer
def show_history():
    hist = load_history()
    win = ctk.CTkToplevel(root)
    win.title(tr("history"))
    win.geometry("800x480")
    try:
        win.iconbitmap("icon.ico")
    except Exception:
        pass
    box = ctk.CTkTextbox(win, width=760, height=380, font=("Consolas", 11))
    box.pack(padx=12, pady=12)
    for item in hist:
        line = f"- [{item.get('date','')}] {item.get('title','')}  →  {item.get('file','')}  ({item.get('url','')})\n"
        box.insert("end", line)
    box.configure(state="disabled")
    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=(0, 12))
    ctk.CTkButton(btn_row, text=tr("open_folder"), command=open_download_folder).grid(row=0, column=0, padx=6)
    ctk.CTkButton(btn_row, text=tr("clear_history"),
                  command=lambda: (save_history([]), win.destroy(), show_info_popup(tr("info_history")))).grid(row=0, column=1, padx=6)

# ---------- Démarrage ----------
ensure_history()
root.mainloop()
# Fin du script
