# LiveCut

LiveCut turns a live stream VOD into ready-to-post highlight clips, automatically and
100% on your own computer. No uploads, no accounts, no cloud, no keys.

**English** · [Português](README.pt-BR.md)

---

## What it does

Give it a Kick, Twitch or YouTube VOD (or a video file already on your PC). LiveCut finds
the most interesting moments and cuts them into short clips you can post.

It looks for moments that actually matter, not just loud parts:

- loud reactions, screams and sudden rises in the audio
- strong words in what the streamer says (swearing, hype, surprise, tension)
- how much is being said around that moment
- excited speech

Everything runs offline. Your video never leaves your machine.

## Who it's for

Streamers and small clip editors who want clips fast, without editing software or a
technical setup.

---

## Install on Windows (easiest)

1. Open the [latest release](https://github.com/matheusabdao/livecut/releases/latest).
2. Download **`LiveCut-Setup-<version>.exe`**.
3. Run it. You can install **just for you** (no admin) or **for all users**.
4. Leave the box **"download FFmpeg and the Whisper model now"** ticked. It uses your
   internet once and leaves everything ready to work offline.
5. Open **LiveCut** from the Start Menu, paste a VOD link and click **Run pipeline**.

Windows may warn about an "unknown publisher", because the installer is not code-signed
yet. Click **More info → Run anyway**. The app checks GitHub for new versions and tells you
when an update is available.

The installer is the recommended path. If you would rather run from source, keep reading.

---

## Getting started from source (manual)

You only need two things installed once: **Python** and **FFmpeg**.

### 1. Install Python

Download Python 3.10 or newer from [python.org](https://www.python.org/downloads/) and
install it.

- On Windows, tick **"Add Python to PATH"** during the install.

### 2. Get FFmpeg

Download the `essentials_build` ZIP from [here](https://www.gyan.dev/ffmpeg/builds/),
extract it, and drop the extracted folder inside the LiveCut project folder.

You should end up with something like this:

```
Live Cut/
├── ffmpeg-2026-08-09-git-6bbc22dc09-essentials_build/
│   └── bin/          <-- ffmpeg.exe and ffprobe.exe live here
├── livecut/
├── config/
├── run_gui.py
└── run_cli.py
```

LiveCut also uses a system-wide FFmpeg if you already have one, but the folder above is
the simplest option.

### 3. Install the project

Open a terminal **inside the LiveCut folder** and run these commands one by one:

```bash
# create an isolated Python environment
python -m venv .venv

# activate it
#   Windows PowerShell:  .venv\Scripts\Activate.ps1
#   Windows CMD:         .venv\Scripts\activate.bat
#   macOS / Linux:       source .venv/bin/activate

# install what LiveCut needs
pip install -r requirements.txt
```

### 4. Run it

```bash
python run_gui.py
```

A window opens. Paste a VOD link (or pick a file from your PC), choose where the clips
should be saved, and click **Run pipeline**.

---

## Using the screen

The window has three simple parts:

1. **Input source** — paste a VOD link, or click **Browse file** to pick a video on your PC.
2. **Output directory** — where the clips will be saved. Click **Open in Explorer** to see them later.
3. **Options**
   - **Quality** — `Best` keeps the original video quality (recommended).
   - **Keep downloaded VOD** — keeps the downloaded video in `temp/` after the run.
   - **Skip Whisper transcription** — much faster, but ranks clips by audio only.
   - **Skip final FFmpeg cut** — analyzes and writes a report, but does not cut clips.

Then click **Run pipeline**. Progress and messages appear in the log at the bottom.

The first run is the slowest, because Whisper has to download its model once. After that
it runs locally.

---

## What you get

Everything is saved in your output folder:

| File | What it is |
|---|---|
| `clip_01_..._score0.84.mp4` | the actual clips, ready to post |
| `report_*.txt` | why each moment was picked (scores and reasons) |
| `metadata_*.json` | the same information, in machine-readable form |

---

## Using the terminal (optional)

If you prefer the command line:

```bash
# a VOD link, best quality
python run_cli.py https://kick.com/SEU_CANAL/videos/ID -q best

# a link, custom output folder, keep the downloaded video
python run_cli.py https://www.twitch.tv/videos/1234567890 -q 720p -o "D:\Clipes" -k

# a file on your PC, skipping transcription (fast)
python run_cli.py "E:\Gravacoes\Sessao 07.mp4" --skip-transcription

# see all options
python run_cli.py --help
```

Useful options:

| Option | What it does |
|---|---|
| `-q, --quality` | `best`, `720p`, `480p` or `worst` |
| `-o, --output-dir` | where clips are saved |
| `-k, --keep-downloaded` | keep the downloaded VOD in `temp/` |
| `--skip-transcription` | faster; ranks by audio only |
| `--skip-cut` | analyze and report only, do not cut |
| `--only-download` | just download the VOD and stop |

---

## Tuning it

All settings live in `config/config.json`. You do not need to touch it to use LiveCut, but
it is how you make the clips fit your stream.

The most useful ones:

- **`clip.max_clips`** — how many clips to generate (default `8`).
- **`clip.min_duration_seconds` / `max_duration_seconds`** — clip length (default 20 to 50s).
- **`clip.target_aspect_ratio`** — set to `9:16` for vertical clips (Shorts, TikTok, Reels).
- **`transcription.language`** — `pt` for Portuguese, `en` for English, `es` for Spanish.
- **`keywords`** — words that mark a good moment. Add your own terms ("clutch", "ace", the game names, etc.).
- **`excitement_words`** — reaction words used to measure excitement (swearing, surprise, hype).
- **`scoring`** — the weight of each signal. They should add up to `1.0`.

If you speak another language or play a different game, the `keywords` and `excitement_words`
lists are the first thing to edit.

---

## Supported platforms

- **Kick** (recommended path, native download)
- **Twitch**, **YouTube**, **Facebook**, **Rumble** (through yt-dlp)
- any other site yt-dlp supports
- local video files (`.mp4`, `.mkv`, `.mov`, `.ts`, and more)

If a platform stops working, update the downloader:

```bash
pip install -U yt-dlp
```

---

## FAQ

**Does my video go to the cloud?**
No. Download, transcription, analysis and cutting all happen on your computer.

**Does it work without an NVIDIA GPU?**
Yes. It is built to run on CPU, which is fine on AMD laptops and desktops.

**Can I make vertical clips for Shorts / TikTok / Reels?**
Yes. Set `clip.target_aspect_ratio` to `9:16` in `config.json`.

**Clips are missing good moments. What do I do?**
Open `report_*.txt` in your output folder. It says why each moment was chosen.
Usually the fix is adding better `keywords` for your game or streamer.

**Can I run it on a schedule?**
Yes. `run_cli.py` returns `0` on success and `1` on failure, so it works with cron or the
Windows Task Scheduler.

**Something crashed. Where is the details?**
A window shows up with the error and a button to report it on GitHub. The diagnostic file
and the log are saved in `%APPDATA%\LiveCut\logs` (look for `crash_*.zip`). Nothing is ever
sent automatically.

---

## For developers

Main pieces:

```
livecut/
├── pipeline.py          orchestrates the whole run
├── vod_downloader.py    downloads VODs (Kick native + yt-dlp fallback)
├── audio_extractor.py   pulls the audio track
├── transcriber.py       local Whisper transcription
├── volume_analyzer.py   volume and peak detection
├── clip_selector.py     scores moments and picks the clips
├── video_cutter.py      cuts the clips with FFmpeg
├── config_loader.py     loads the config (repo or user folder)
├── app_paths.py         resolves folders in dev and packaged modes
├── provisioning.py      downloads FFmpeg + the Whisper model
├── updater.py           checks GitHub for a newer release
├── crash.py             builds the crash report and the issue link
├── logging_setup.py     rotating log file
└── app.py               single entry point (GUI / CLI / --provision)
run_cli.py               command-line entry point
run_gui.py               desktop (Tkinter) interface
packaging/               PyInstaller spec, Inno Setup script, icon
tests/                   test suite
```

Run the tests and the linter:

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

CI runs the same checks on every push and pull request
(`.github/workflows/ci.yml`). You can also run it straight from the package:
`python -m livecut --version`, `python -m livecut --help`, `python -m livecut --provision`.

Build the Windows installer (only needed when cutting a release):

```bash
pip install pyinstaller
python packaging/make_icon.py
pyinstaller packaging/livecut.spec --noconfirm
iscc packaging/installer.iss /DAppVersion=1.0.0
```

Pushing a `v*` tag runs `.github/workflows/release.yml`, which tests, builds and publishes
the installer to GitHub Releases. Bump `__version__` in `livecut/__init__.py` before tagging.

Planned next: better highlight detection (using chat reactions) and a simpler local web
interface. The design is in
[`docs/superpowers/specs/`](docs/superpowers/specs/2026-10-29-livecut-web-highlight-design.md).

---

## License

MIT. Use it however you want.
