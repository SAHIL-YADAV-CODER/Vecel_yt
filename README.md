# YT Vault — YouTube Downloader

A sleek Python/Flask web app to download YouTube videos and audio in multiple qualities.

## Features

- 🎬 **Download videos** in any available quality (144p → 4K)
- 🎵 **Extract audio only** in MP3, M4A, WAV, FLAC, or OGG
- 📊 **Real-time progress bar** with speed, ETA, and size tracking
- 🔍 **Fetches video metadata** — thumbnail, title, channel, views, duration
- ⚡ **Background downloads** — non-blocking with threaded processing

## Setup

### 1. Install FFmpeg (required for merging video+audio)

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

## Usage

1. Paste a YouTube URL into the input box
2. Click **Fetch Info** to load video details and available formats
3. Switch between **Video** and **Audio Only** tabs
4. Select your preferred quality
5. For audio, choose your output format (MP3, M4A, WAV, etc.)
6. Click **Start Download** and watch the progress bar
7. Save your file when complete

## Project Structure

```
yt-downloader/
├── app.py              # Flask backend
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Frontend UI
└── downloads/          # Temporary download storage (auto-created)
```

## Notes

- Downloaded files are stored temporarily in the `downloads/` folder.
- For production use, add periodic cleanup of old files.
- Respect YouTube's Terms of Service. For personal use only.
