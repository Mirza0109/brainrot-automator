---
layout: default
title: Project README
---

<a href="https://spiffy-mousse-25906f.netlify.app/netlify/functions/login">Login with TikTok</a>

# Auto Upload CLI for TikTok & YouTube Shorts with AI Story Generation & Voiceover

A command-line Python tool that:

1. **Generates** multi-part suspenseful stories via OpenAI
2. **Converts** those scripts to voiceovers using ElevenLabs TTS
3. **Creates** subtitle files and overlays them on background videos via FFmpeg
4. **Automatically uploads** the finished videos to TikTok and/or YouTube Shorts

This end-to-end pipeline enables you to go from idea to published content with a single script.

---

## 🔍 Description

`auto_upload.py` orchestrates the full content creation process:

1. **Story generation**: calls OpenAI to produce 2–4 part narratives, each \~20–30s long, with cliffhangers.
2. **Voiceover**: uses ElevenLabs to generate high-quality MP3 narrations for each part.
3. **Subtitles**: transcribes the TTS output (via Whisper), re-chunks into timed segments, and writes SRT files.
4. **Video composition**: overlays subtitles on a random background clip using FFmpeg, syncing with the audio.
5. **Publishing**: uploads the final MP4s to TikTok and/or YouTube Shorts with metadata from a JSON file.

---

## ⚙️ Features

* **AI Story Generation**: automatically crafts tense, cliffhanger-driven story scripts.
* **Voiceover & Subtitles**: integrates ElevenLabs TTS and Whisper for narration plus accurate subtitles.
* **Multi-platform Upload**: CLI supports TikTok, YouTube Shorts, or both in one run.
* **Part-aware metadata**: filenames extract `part` numbers to match JSON entries for captions/tags.
* **End-to-end automation**: from script to published video, schedulable via cron, GitHub Actions, etc.

---

## 🛠 Prerequisites

* **Python 3.7+**
* **FFmpeg** installed and on your PATH
* **Dependencies** (install via pip):

  ```bash
  pip install openai python-dotenv elevenlabs requests google-auth-oauthlib google-api-python-client whisper

  cd netlify/functions
  npm init -y
  npm install node-fetch@2 dotenv
  ```
* **Environment variables** in a `.env` file or exported:

  * `OPENAI_API_KEY` – your OpenAI API key
  * `ELEVENLABS_API_KEY` – your ElevenLabs API key
  * `TIKTOK_ACCESS_TOKEN` – TikTok OAuth2 token (valid 24h)
  * `YOUTUBE_CLIENT_SECRETS_FILE` – path to client\_secrets.json for YouTube OAuth

---

## ⚡️ Installation

1. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/auto-upload.git
   cd auto-upload
   ```
2. **Install FFmpeg** (if not already):

   * macOS: `brew install ffmpeg`
   * Ubuntu: `sudo apt install ffmpeg`
3. **Install Python deps**

   ```bash
   pip install openai python-dotenv elevenlabs requests google-auth-oauthlib google-api-python-client whisper
   ```
4. **Create a `.env` file** in the project root:

   ```dotenv
   OPENAI_API_KEY=sk-...
   ELEVENLABS_API_KEY=eleven-...
   TIKTOK_ACCESS_TOKEN=...
   YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
   ```

---

## 🚀 Usage

```bash
python auto_upload.py \
  --video /path/to/backgrounds/videoplayback.mp4 \
  --meta /path/to/stories.json \
  --platform both
```

* **`--video`**: path to a background clip directory or single file (will randomize).
* **`--meta`**: JSON file for upload metadata (captions, hashtags, tags).
* **`--platform`**: `tiktok`, `youtube`, or `both`.

The script will generate story scripts, voiceovers, subtitles, videos, and then upload them, printing API responses.

---

## 🔐 OAuth Callback Endpoint

TikTok's OAuth flow requires a publicly accessible HTTPS Redirect URI to receive the authorization `code`. Simply hosting your code in a public Git repository does **not** provide this endpoint—you’ll still need one of the following:

**Local Server + ngrok**

   * Run a small Flask (or similar) app on your machine (e.g., on port 8090) to handle `/oauth/callback`.
   * Expose it via ngrok:

     ```bash
     ngrok http 8090
     ```
   * Add the generated `https://<your_id>.ngrok.io/oauth/callback` URL as your Redirect URI in the TikTok Developer Portal.

---

## 📅 Scheduling

Automate the entire pipeline via:

* **cron (Linux/macOS)**: e.g. `0 9 * * * python /path/auto_upload.py --…`
* **Windows Task Scheduler**
* **GitHub Actions**: use a `schedule` workflow for serverless runs on GitHub’s servers.

---

## 📝 License

This project is licensed under the [MIT License](LICENSE).

---

*Ready to generate, voice, and publish? Let's go!*, voice, and publish? Let's go!\*
