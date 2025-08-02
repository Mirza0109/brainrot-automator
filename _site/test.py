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
    "[FREE]Subway surfers video for background.mp4",
    # add more as needed
]
FONT_NAME    = "Arial"
FONT_SIZE    = 20      # subtitle font size
MARGIN_V     = 50      # distance from bottom
MAX_WORDS    = 5       # max words per subtitle chunk

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
PROMPT_GEN = """Generate a tense, 2–4 part story designed to hook the listener immediately and end each part on a cliffhanger. Return exactly one JSON object:
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
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": PROMPT_GEN}]
)
data = json.loads(resp.choices[0].message.content.strip())
parts = data["parts"]

# Print the generated story parts
print("\nGenerated Story Parts:")
for i, part in enumerate(parts, 1):
    print(f"\nPart {i}:")
    print(part)
print()
