import uuid
import json
import os
import subprocess
import random
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs.client import ElevenLabs

# ─── Load environment variables ────────────────────────
load_dotenv()  # expects .env with OPENAI_API_KEY & ELEVENLABS_API_KEY

# ─── Clients ───────────────────────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# ─── Configuration ────────────────────────────────────
BACKGROUND_VIDEOS = [
    "videoplayback.mp4",
    # add more as needed
]
FONT_NAME    = "Arial"
FONT_SIZE    = 20      # subtitle font size
MARGIN_V     = 50      # distance from bottom
MAX_WORDS    = 5       # max words per subtitle chunk

# ─── Directory paths ────────────────────────────────────
AUDIO_SUBTITLES_DIR = "audio_and_subtitles"
VIDEOS_DIR = "videos"
os.makedirs(AUDIO_SUBTITLES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

# ─── Helper functions ──────────────────────────────────
def probe_duration(path: str) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ])
    return float(out.strip())

def fmt_ts(t: float) -> str:
    h  = int(t // 3600)
    m  = int((t % 3600) // 60)
    s  = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# ─── 1) Generate 2–4 suspenseful story parts ───────────
PROMPT_GEN = """Generate a tense, 2–3 part story, each part should be 20-30 seconds of speech, designed to hook the listener immediately and end each part on a cliffhanger. Return exactly one JSON object:
{"parts": [string, …]}

Each part must:
- Be 45–60 words (≈20 sec when read aloud)
- Select one genre: horror, psychological thriller, dark sci-fi, or mystery
- Open with a gripping first sentence hook
- Present an unsettling scenario or high-stakes dilemma
- Raise provocative questions and hint at a shocking twist
- End with a teasing indicator for the next part
- The last part should end with a clear ending

Example output:
{"parts": [
  "Part 1 text…",
  "Part 2 text…",
  "Part 3 text…"
]}"""

resp = openai_client.chat.completions.create(
    model="gpt-4",  # Changed from gpt-4o-mini to gpt-4
    messages=[{"role": "user", "content": PROMPT_GEN}]
)
data = json.loads(resp.choices[0].message.content.strip())
parts = data["parts"]

# ─── 2) Process each part: TTS, subtitle, video ────────
base_name = uuid.uuid4().hex  # random prefix to avoid name conflicts
background = random.choice(BACKGROUND_VIDEOS)

for idx, story in enumerate(parts, start=1):
    print(f"\n--- Part {idx} ---")
    # file paths
    audio_path   = os.path.join(AUDIO_SUBTITLES_DIR, f"{base_name}_part{idx}.mp3")
    srt_path     = os.path.join(AUDIO_SUBTITLES_DIR, f"{base_name}_part{idx}.srt")
    video_output = os.path.join(VIDEOS_DIR, f"{base_name}_part{idx}.mp4")

    # 2a) Generate TTS
    audio_stream = eleven_client.text_to_speech.convert(
        text=story,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # replace with your voice ID
        model_id="eleven_flash_v2_5",
        output_format="mp3_44100_128"
    )
    with open(audio_path, "wb") as f:
        for chunk in audio_stream:
            f.write(chunk)
    print(f"  Saved audio → {audio_path}")

    # 2b) Whisper transcription for precise timings
    transcript = openai_client.audio.transcriptions.create(
        file=open(audio_path, "rb"),
        model="whisper-1",
        response_format="verbose_json",
        temperature=0
    )
    segments = transcript.segments

    # 2c) Re-chunk to shorter subtitles
    new_segments = []
    for seg in segments:
        words = seg.text.strip().split()
        if not words:
            continue
        total_words = len(words)
        group_count = (total_words + MAX_WORDS - 1) // MAX_WORDS
        duration = (seg.end - seg.start) / group_count
        for i in range(group_count):
            chunk = words[i*MAX_WORDS:(i+1)*MAX_WORDS]
            start = seg.start + i * duration
            end   = start + duration
            new_segments.append({
                "start": start,
                "end":   end,
                "text":  " ".join(chunk)
            })

    # 2d) Write SRT
    with open(srt_path, "w", encoding="utf-8") as sf:
        for i, seg in enumerate(new_segments, start=1):
            sf.write(f"{i}\n")
            sf.write(f"{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}\n")
            sf.write(seg['text'] + "\n\n")
    print(f"  Wrote subtitles → {srt_path}")

    # 2e) Probe durations & pick random segment of background
    total_dur = probe_duration(audio_path)
    bg_dur    = probe_duration(background)
    max_start = max(0, bg_dur - total_dur)
    start_at  = random.uniform(0, max_start)
    print(f"  Audio {total_dur:.1f}s, BG {bg_dur:.1f}s → start at {start_at:.1f}s")

    # 2f) Build FFmpeg command
    filter_str = (
        f"subtitles='{os.path.abspath(srt_path)}':"
        f"force_style='FontName={FONT_NAME},FontSize={FONT_SIZE},"
        f"PrimaryColour=&HFFFFFF&,MarginV={MARGIN_V}'"
    )
    ffmpeg_cmd = [
        "ffmpeg",
        "-ss", str(start_at),
        "-i", background,
        "-i", audio_path,
        "-t", str(total_dur),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-vf", filter_str,
        video_output
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"  Output video → {video_output}")

# ─── 3) Generate upload metadata for TikTok, Instagram & YouTube Shorts ────
metadata_prompt = f"""
You are a social-media growth expert. For each of these video scripts (part 1 to part {len(parts)}), generate optimized metadata for TikTok, Instagram, and YouTube Shorts:

1. TikTok:
   • caption (≤150 characters)
   • 8–12 trending hashtags

2. Instagram:
   • caption (≤2,200 characters, include a clear CTA)
   • 15–20 hashtags

3. YouTube Shorts:
   • title (≤60 characters, include "#Shorts")
   • description (≤150 characters, include "#Shorts" & a CTA)
   • 5–10 relevant tags (must include "#Shorts")

Return exactly one JSON object with this structure:

{{
  "videos": [
    {{
      "part": 1,
      "tiktok":    {{ "caption": "...", "hashtags": ["#…", …] }},
      "instagram": {{ "caption": "...", "hashtags": ["#…", …] }},
      "youtube_shorts": {{
        "title": "...",
        "description": "...",
        "tags": ["…", …]
      }}
    }},
    …
  ]
}}

Here are the scripts:
{json.dumps(parts, indent=2)}
"""

resp_meta = openai_client.chat.completions.create(
    model="gpt-4",  # Changed from gpt-4o-mini to gpt-4
    messages=[{"role": "user", "content": metadata_prompt}]
)
metadata = json.loads(resp_meta.choices[0].message.content)

# Save metadata for your automation pipeline
meta_out = os.path.join(AUDIO_SUBTITLES_DIR, f"{base_name}_metadata.json")
with open(meta_out, "w", encoding="utf-8") as mf:
    json.dump(metadata, mf, ensure_ascii=False, indent=2)
print(f"Saved upload metadata → {meta_out}")
