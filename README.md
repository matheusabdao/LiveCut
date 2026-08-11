# 🎬 LiveCut

**100% local, offline** automatic highlight clip generator for VODs.
Point it at a **Kick / Twitch / YouTube** VOD URL (or a local video file) and get:

* 📋 A ranked shortlist of the **most interesting moments** (peak volume + transcription keywords + speech density + excitement terms)
* 🎥 Individual MP4 clips ready to share, cut with **frame accuracy** and high-quality encoding
* 📝 Full human-readable report + JSON metadata per run

No cloud APIs, no video uploads, no keys. Everything runs on your machine.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Multi-platform ingest** | 🔴 **Kick.com** (native TLS-impersonating extractor — bypasses Cloudflare 403) · 🟣 **Twitch** · 🔴 **YouTube** · 👥 Facebook · 🎙 Rumble · Any platform supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp) · Local video files (`.mp4/.mkv/.mov/.ts/…`) |
| **Whisper transcription** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with **per-word timestamps** and VAD filtering. Works great on **CPU only** (`int8` quantization) — perfect for AMD laptops/desktops without CUDA. |
| **Smart peak detection** | Dual-pass scipy `find_peaks`: RMS volume + **sudden-surge detection** (build-up + variation metrics). Adaptive thresholding per video — no manual tuning needed for different streamers. |
| **Composite scoring** | 35% volume · 30% keywords · 15% speech density · 20% excitement words — fully tuneable in `config.json`. |
| **Peak-aware positioning** | The detected peak is placed at **~62% of each clip** so you see the **action, then the reaction**, not both chopped off. |
| **High quality cuts** | Frame-accurate FFmpeg (2-pass seek + re-encode). `preset=slow`, `CRF=18`, `profile:v high`, yuv420p, AAC 256kbps @ 48 kHz. |
| **Anti-overlap selection** | Greedy ranking + 28% overlap guard — you get a diverse set of highlights, not the same 60 seconds sliced 8 ways. |
| **Two interfaces** | 💻 **CLI** for power users / cron automation. 🖱 **Tkinter GUI** for casual use — paste URL, pick a folder, click *Run*. |
| **Portable FFmpeg** | Looks for an `ffmpeg-*/bin/` folder in the project root first — no installers, no PATH pollution, no system-wide dependencies beyond Python 3.10+. |

---

## ⚡ Quick start (Windows / Linux / macOS)

### Prerequisites
* Python **3.10 or newer** (3.11 / 3.12 / 3.13 recommended)
* [FFmpeg binaries](https://www.gyan.dev/ffmpeg/builds/) — download the `essentials_build` ZIP and **extract it next to the project** so you end up with:

```
Live Cut/
├── ffmpeg-*-essentials_build/
│   └── bin/          ← ffmpeg.exe, ffprobe.exe, ffplay.exe live here
├── livecut/          ← this repo's Python package
├── config/
├── output/
├── run_cli.py
└── run_gui.py
```

> LiveCut also falls back to system-installed FFmpeg if the local folder is absent.

### 1. Clone / install

```bash
git clone <your-repo-url> livecut && cd livecut

# Create a virtualenv (highly recommended)
python -m venv .venv

# Activate it:
#   Windows PowerShell:  .venv\Scripts\Activate.ps1
#   Windows CMD:         .venv\Scripts\activate.bat
#   macOS/Linux:         source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Launch the GUI

```bash
python run_gui.py
```

You will see this minimal window:

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🎬 LiveCut — Local VOD Highlight Generator                           │
│                                                                      │
│ 1. Input source (VOD URL or local file)                              │
│    [ https://kick.com/user/videos/UUID______________________ ] [Browse][Paste] │
│                                                                      │
│ 2. Output directory (where clips are saved)                          │
│    [ C:\Users\You\Videos\LiveCut Clips______________ ] [Browse] [Open in Explorer] │
│                                                                      │
│ 3. Options                                                           │
│    Quality      [Best (stream-copy, lossless) ▾]    ☑ Keep VOD file │
│                 ☐ Skip Whisper  |  ☐ Skip cut (report only)         │
│                                                                      │
│ [ ▶ Run pipeline ]  [Stop]                   [progress bar]  Running │
│                                                                      │
│ 4. Log output                                                        │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ Welcome to LiveCut! Paste a VOD URL…                             │ │
│ │ …                                                                │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 3. Or use the CLI

```bash
# Kick VOD — full HD stream-copy (best quality + fastest)
python run_cli.py https://kick.com/sheviii2k/videos/019fec54-f6b8-76e8-a24f-036e9d09b15a --quality best

# Twitch VOD — custom output folder, keep downloaded VOD
python run_cli.py https://www.twitch.tv/videos/1234567890 -q 720p -o "D:\Stream clips" -k

# YouTube — only download, no analysis
python run_cli.py https://www.youtube.com/watch?v=dQw4w9WgXcQ --only-download

# Local file, skip transcription (very fast, peaks-only ranking)
python run_cli.py "E:\Recordings\Session 07.mp4" --skip-transcription

# Print full help
python run_cli.py --help
```

---

## 📂 Project structure

```
Live Cut/
├── livecut/                       # 🧠 Main Python package (importable)
│   ├── __init__.py                # Public API re-exports + version
│   ├── pipeline.py                # Core orchestrator: 7 stages wired together
│   ├── config_loader.py           # Loads config/config.json with defaults
│   ├── ffmpeg_utils.py            # Auto-detect local ffmpeg / ffprobe
│   ├── vod_downloader.py          # Kick extractor + generic yt-dlp fallback
│   ├── audio_extractor.py         # WAV 16 kHz mono via ffmpeg
│   ├── transcriber.py             # faster-whisper (CPU, int8, word timestamps)
│   ├── volume_analyzer.py         # Librosa RMS + scipy peak detection
│   ├── clip_selector.py           # Scoring, ranking, anti-overlap filter
│   └── video_cutter.py            # Frame-accurate FFmpeg clip cutting
├── config/
│   └── config.json                # ⚙️ ALL tunable parameters live here
├── run_cli.py                     # 💻 Command-line entrypoint
├── run_gui.py                     # 🖱 Tkinter GUI entrypoint
├── requirements.txt               # pip deps
├── output/                        # Generated clips + reports + metadata
├── temp/                          # Downloaded VODs + WAVs (auto-cleaned by default)
├── examples/                      # Example configs / snippets (optional)
└── tests/                         # Unit tests (optional, pytest-friendly)
```

---

## 🏗 Pipeline architecture

Each run is a linear 7-stage pipeline (`livecut.pipeline.run_pipeline`):

```
  [1] LOAD CONFIG ──► [2] INGEST ──► [3] AUDIO EXTRACT
                                           │
                                           ▼
                       [6] CUT CLIPS ◄─ [5] PEAK DETECT ◄─ [4] WHISPER TRANSCRIBE
                             │
                             ▼
                          [7] REPORT / METADATA JSON → output/
```

### Stage breakdown

1. **Config merge** — `config/config.json` (if missing, it is created with defaults on first run) merged with CLI/GUI overrides.
2. **Ingest** — URL? → dispatch to `Kick` extractor or `yt-dlp` fallback. Local path? → just validate it exists.
3. **Audio extraction** — `ffmpeg -vn -ac 1 -ar 16000 -sample_fmt s16 -acodec pcm_s16le` (Whisper-optimised WAV).
4. **Transcription** — `faster-whisper.small` (default) with `vad_filter=True`, `beam_size=5`, per-word timestamps.
5. **Peak detection** — `librosa.feature.rms` then **two passes** of `scipy.signal.find_peaks`: one for absolute level, one for the first difference (sudden *jumps* in volume — e.g., scream, reaction).
6. **Clip selection** — each peak gets placed in a 20–50 s window centred ~62 % in (context first, peak second), scored with the 4-component formula, then a greedy non-overlap pick.
7. **Cutting + output** — frame-accurate FFmpeg cuts + `report_*.txt` + `metadata_*.json`.

---

## ⚙️ Configuration guide

All knobs are in **`config/config.json`**.

| Section | Common things to tweak |
|---|---|
| **`clip`** | `max_clips` (default 8), `min_duration_seconds` / `max_duration_seconds` (20/50 s), `target_aspect_ratio` (default `16:9`, change to `9:16` if you want TikTok/Shorts-style crops) |
| **`audio`** | `volume_peak_threshold` (default 0.55; lower = more, noisier peaks). `peak_min_distance_seconds` — gap between independent peaks. |
| **`transcription`** | `whisper_model` — try `medium` if small is missing words; `language` — set to `en` for English streams, `es` for Spanish etc. (or `None` for auto-detect). |
| **`scoring`** | Weights — sum should be 1.0. Increase `keyword_weight` if you want keyword hits to dominate; increase `volume_weight` for pure "loud = good" behaviour. |
| **`keywords`** | List of lowercase strings. Portuguese defaults are included (profane reactions, exclamations, "ganhei"/"perdi" etc.). **Add your streamer/game-specific terms here.** |
| **`ffmpeg`** | `preset` (slow/medium/fast — slower = smaller file / better compression ratio), `crf` (18 visually lossless, 23 default, 28 small). |

### Tuning example — English CS:GO streamer

```json
{
  "transcription": { "whisper_model": "small", "language": "en" },
  "keywords": [
    "nice", "lets go", "clutch", "ace", "insane", "unreal",
    "what the fuck", "holy shit", "no way", "pog", "w", "clutched",
    "he's cheating", "smurf", "team kill", "knifed", "deagle", "awp"
  ]
}
```

---

## 🛠 Platform-specific notes

### 🔴 Kick.com
Kick actively blocks generic scrapers. LiveCut ships a **native extractor** in `vod_downloader.py` that uses `curl_cffi` with Chrome 131 TLS impersonation and a regex m3u8 extraction.
* This is the **recommended** path. Kick videos will be downloaded with `-c copy` (stream-copy, zero quality loss) when `--quality best`.

### 🟣 Twitch / 🔴 YouTube / Facebook / Rumble
Falls back to `yt-dlp`. Format selection is mapped from your `--quality` choice:

| Quality | yt-dlp format |
|---|---|
| `best` | `bv*+ba/b` — best video + best audio merged |
| `720p` | height ≤ 720, prefer `bv*[height<=720]` |
| `480p` | height ≤ 480 |
| `worst` | `worst` (tiny file for quick testing) |

Make sure your yt-dlp is up to date if a platform breaks: `pip install -U yt-dlp`.

### Local files
Just pass any ffmpeg-readable video. Nothing special needed.

---

## ❓ FAQ

### **Does this send my video to the cloud?**
No. 100 % of the work — downloads, transcription (Whisper model runs locally), volume analysis, and cutting — happens on your CPU/GPU.

### **Can I use this on AMD hardware without CUDA?**
Yes. That is the primary target environment. `compute_type=int8` + `device=cpu` on `faster-whisper` works great on Ryzen 7000/8000/9000 mobile and desktop CPUs.

### **How long does a 3-hour VOD take?**
Rough rule of thumb on a Ryzen AI 9 HX 370 with Whisper `small`:
* Download (1080p Kick): ~real time or faster
* Transcription: ~0.4–0.7× real time (so 3h video ≈ 1–2h)
* Everything else: a few minutes total
* Cutting 8 clips: 30 s – 2 min at preset slow

If you want **fastest possible turns**, run with `--skip-transcription` to use peaks-only ranking. Clips will be ready in minutes.

### **How can I make clips vertical for Shorts / TikTok / Reels?**
Edit `config.json` → set:
```json
"clip": { "target_aspect_ratio": "9:16", "fallback_aspect_ratio": "16:9" }
```
LiveCut applies a **center crop** and re-encodes. For best results, re-encode with `preset=slow / crf=20`.

### **Clips are still missing good moments. How do I debug?**
Check `output/report_*.txt` — every clip shows component scores and the rationale.
* If keyword scores are always 0 → add better keywords.
* If peak count is 0 → lower `volume_peak_threshold` in `config.json`.
* If every clip is 1 star → your keywords don't match the stream's vocabulary. Add 10–20 more.

### **Can I run this on a schedule / cron?**
Absolutely. `run_cli.py` returns Unix exit codes (0 = success, 1 = failure), prints logs to stdout, and accepts fully-scriptable options. Wrap it in `powershell` / `bash` + `cron`/Task Scheduler.

---

## 🧪 Running the tests

Tests are optional. `pytest`-compatible:

```bash
pip install pytest
pytest tests/ -v
```

---

## 📄 License

MIT — do whatever you want with it. Attribution appreciated but not required.

## 🤝 Contributing

Pull requests welcome! Top 3 things that would make LiveCut better:
1. Scene-detect scoring (opencv / ffprobe scene changes).
2. "Shorts mode" = smart face/gamplay region crops instead of center crop.
3. Playlist / bulk VOD queueing + thumbnail export for each clip.
