import os
import uuid
import json
import random
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from upload_handlers import ensure_tiktok_auth, start_auto_refresher, upload_tiktok, upload_youtube_short

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Configuration
BACKGROUND_VIDEOS = ["videoplayback.mp4"]
FONT_NAME = "Arial"
FONT_SIZE = 20
MARGIN_V = 50
MAX_WORDS = 5
AUDIO_SUBDIR = Path("audio_and_subtitles")
VIDEO_SUBDIR = Path("videos")
AUDIO_SUBDIR.mkdir(exist_ok=True)
VIDEO_SUBDIR.mkdir(exist_ok=True)

# 1) Prompt definitions
def generate_story_parts(model="gpt-4"):
    prompt = (
        """
            Create an irresistibly addictive micro-epic that grabs readers by the throat and refuses to let go. Set your tale in the blood-soaked world of ancient myth—Rome's marble halls, Viking longships cutting through storm-dark seas, or beneath the shadow of Greek temples where gods walk among mortals.

            STRUCTURE: Craft exactly 3 parts, each designed to be consumed in 30-40 seconds when read aloud (roughly 75-100 words per part).

            ADDICTION FORMULA:
            • Part 1: PERSONAL TERROR + INSTANT CONNECTION - Open with visceral, life-threatening danger using second person ("you") so readers feel the blade at their throat. But immediately ground them with essential context: who you are, why this matters, what you're fighting for. The terror is personal because the reader understands the stakes—your family, your honor, your sacred oath. Fear AND emotional investment within the first 30 seconds.

            • Part 2: BETRAYAL THAT CUTS DEEP + DIVINE ESCALATION - Reveal who betrayed you and why it destroys everything you believed in. Make the betrayal personal—your brother, your mentor, your beloved. The gods intervene not randomly, but because of YOUR choices, YOUR bloodline, YOUR broken promises. Readers must feel the betrayal as their own wound.

            • Part 3: YOUR IMPOSSIBLE CHOICE + CLIFFHANGER - Force a soul-crushing decision that readers feel in their bones: save your child or your people, honor your oath or save your love, preserve your soul or protect the innocent. Make readers desperate to know what THEY would choose. End mid-decision, with consequences about to unfold.

            LANGUAGE REQUIREMENTS:
            - Archaic flavor but modern clarity ("thou" sparingly, focus on powerful verbs)
            - Each sentence must hit like a war hammer—short, brutal, unforgettable
            - Rich sensory details: taste of blood, smell of burning temples, sound of breaking oaths
            - Every word must earn its place or be cut without mercy

            EMOTIONAL INVESTMENT REQUIREMENTS:
            - Give the reader a clear identity and relationships they care about instantly
            - Make every threat personal—to YOUR family, YOUR honor, YOUR sacred bonds
            - Use specific, relatable motivations: protecting loved ones, keeping promises, seeking justice
            - The reader should feel like they're living this nightmare, not just watching it

            Output as pure JSON with no additional text:
            {"parts":[
            "Part 1 text that makes readers' hearts race...",
            "Part 2 text that twists the knife...",
            "Part 3 text that leaves them desperate for more..."
            ]}
        """
    )
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    data = json.loads(resp.choices[0].message.content)
    return data['parts']

# 2) Utilities
def probe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ])
    return float(out.strip())

def fmt_ts(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# 3) Process part: TTS, SRT, video creation
def process_part(text: str, idx: int, base: str):
    audio_file = AUDIO_SUBDIR / f"{base}_part{idx}.mp3"
    srt_file = AUDIO_SUBDIR / f"{base}_part{idx}.srt"
    video_file = VIDEO_SUBDIR / f"{base}_part{idx}.mp4"

    # TTS
    stream = eleven_client.text_to_speech.convert(text=text, voice_id="21m00Tcm4TlvDq8ikWAM", model_id="eleven_flash_v2_5", output_format="mp3_44100_128")
    with open(audio_file, "wb") as f:
        for chunk in stream:
            f.write(chunk)

    # WHISPER transcription
    transcription = openai_client.audio.transcriptions.create(
        file=open(audio_file, "rb"), model="whisper-1", response_format="verbose_json", temperature=0
    )
    segments = transcription.segments

    # Re-chunk
    new_segments = []
    for seg in segments:
        words = seg.text.split()
        if not words: continue
        group_count = (len(words) + MAX_WORDS - 1) // MAX_WORDS
        dur = (seg.end - seg.start) / group_count
        for i in range(group_count):
            start = seg.start + i * dur
            end = start + dur
            chunk_txt = " ".join(words[i*MAX_WORDS:(i+1)*MAX_WORDS])
            new_segments.append({"start": start, "end": end, "text": chunk_txt})

    # Write SRT
    with open(srt_file, "w", encoding="utf-8") as sf:
        for i, seg in enumerate(new_segments, 1):
            sf.write(f"{i}\n{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}\n{seg['text']}\n\n")

    # Video render
    audio_dur = probe_duration(audio_file)
    bg = random.choice(BACKGROUND_VIDEOS)
    bg_dur = probe_duration(bg)
    start_at = random.uniform(0, max(0, bg_dur - audio_dur))
    filter_str = (
        f"subtitles='{srt_file}':force_style='FontName={FONT_NAME},"
        f"FontSize={FONT_SIZE},PrimaryColour=&HFFFFFF&,MarginV={MARGIN_V}'"
    )
    cmd = ["ffmpeg", "-ss", str(start_at), "-i", bg, "-i", str(audio_file), "-t", str(audio_dur),
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac", "-vf", filter_str, str(video_file)]
    subprocess.run(cmd, check=True)
    return video_file

# 4) Metadata generation
def generate_metadata(parts: list):
    prompt = f"""
        You are a social-media growth expert. For each of these video scripts (part 1 to part {len(parts)}), generate optimized metadata for TikTok, Instagram, and YouTube Shorts:

        1. TikTok:
        • caption (≤150 characters)
        • 5 trending hashtags

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
    resp = openai_client.chat.completions.create(model="gpt-4", messages=[{"role":"user","content":prompt}])
    return json.loads(resp.choices[0].message.content)

# Main orchestration
def main():
    # Ensure TikTok auth is ready
    ensure_tiktok_auth()
    start_auto_refresher()

    parts = generate_story_parts()
    print(parts)
    base = uuid.uuid4().hex
    video_paths = []
    for idx, text in enumerate(parts, 1):
        print(f"Processing part {idx}")
        video_paths.append(process_part(text, idx, base))
    
    metadata = generate_metadata(parts)
    meta_file = AUDIO_SUBDIR / f"{base}_metadata.json"
    meta_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"Metadata saved to {meta_file}")

    # Upload videos to platforms
    for video_path in video_paths:
        print(f"\nUploading {video_path.name}...")
        try:
            print("Uploading to YouTube Shorts...")
            youtube_response = upload_youtube_short(str(video_path), str(meta_file))
            print(f"YouTube upload complete! Video ID: {youtube_response['id']}")
        except Exception as e:
            print(f"YouTube upload failed: {e}")

        try:
            print("Uploading to TikTok...")
            tiktok_response = upload_tiktok(str(video_path), str(meta_file))
            print(f"TikTok upload complete! Status: {tiktok_response}")
        except Exception as e:
            print(f"TikTok upload failed: {e}")

if __name__ == '__main__':
    main()


