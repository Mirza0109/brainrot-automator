import os
import re
import json
import requests
from pathlib import Path

# ─── YouTube Shorts ────────────────────────────────────────────────────────────
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── Configuration ─────────────────────────────────────────────────────────────
# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

# Get client secrets filename from env var, default to the standard name if not set
YOUTUBE_CLIENT_SECRETS_FILE = os.path.join(
    SCRIPT_DIR,
    os.getenv('YOUTUBE_CLIENT_SECRETS_FILE', 'client_secret_782352390431-j1d1tq1ks5b34r86rin3l4738nckfpia.apps.googleusercontent.com.json')
)

if not os.path.exists(YOUTUBE_CLIENT_SECRETS_FILE):
    raise FileNotFoundError(f"YouTube client secrets file not found at: {YOUTUBE_CLIENT_SECRETS_FILE}")

YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]
YOUTUBE_API_SERVICE = ('youtube', 'v3')
TIKTOK_API_BASE = 'https://open.tiktokapis.com'
TIKTOK_ACCESS_TOKEN = os.getenv('TIKTOK_ACCESS_TOKEN')


def _get_youtube_client():
    flow = InstalledAppFlow.from_client_secrets_file(
        YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_SCOPES
    )
    creds = flow.run_local_server(port=0)
    youtube = build(YOUTUBE_API_SERVICE[0], YOUTUBE_API_SERVICE[1], credentials=creds)
    
    # Get and print channel info
    channel_response = youtube.channels().list(
        part='snippet',
        mine=True
    ).execute()
    
    if channel_response['items']:
        channel = channel_response['items'][0]['snippet']
        print(f"Connected to YouTube channel: {channel['title']} ({channel['customUrl'] if 'customUrl' in channel else 'no custom URL'})")
    
    return youtube

def check_youtube_channel():
    youtube = _get_youtube_client()
    channel_response = youtube.channels().list(
        part='snippet',
        mine=True
    ).execute()
    print(channel_response)
    return channel_response['items'][0]['snippet']

def upload_youtube_short(video_path: str, json_path: str):
    """
    Uploads a ≤60s video as a YouTube Short using metadata in json_path.
    """
    fname = os.path.basename(video_path)
    m = re.search(r'(\d+)', fname)
    if not m:
        raise ValueError(f"Cannot extract part number from '{fname}'")
    part = int(m.group(1))

    with open(json_path, 'r') as f:
        data = json.load(f)
    entry = next((v for v in data['videos'] if v.get('part') == part), None)
    if not entry or 'youtube_shorts' not in entry:
        raise KeyError(f"No YouTube Shorts metadata for part {part}")

    meta = entry['youtube_shorts']
    youtube = _get_youtube_client()

    body = {
        'snippet': {
            'title':       meta['title'],
            'description': meta['description'],
            'tags':        meta.get('tags', []),
            'categoryId':  '22'
        },
        'status': {
            'privacyStatus': 'public'
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    req = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)

    print("Uploading to YouTube…")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}% done")
    print(f"Uploaded! Video ID: {resp['id']}")
    return resp


def upload_tiktok(video_path: str, json_path: str):
    """
    Uploads a TikTok video via the Content Posting API.
    """
    if not TIKTOK_ACCESS_TOKEN:
        raise EnvironmentError("Set TIKTOK_ACCESS_TOKEN")

    fname = os.path.basename(video_path)
    m = re.search(r'(\d+)', fname)
    if not m:
        raise ValueError(f"Cannot extract part number from '{fname}'")
    part = int(m.group(1))

    with open(json_path, 'r') as f:
        data = json.load(f)
    entry = next((v for v in data['videos'] if v.get('part') == part), None)
    if not entry or 'tiktok' not in entry:
        raise KeyError(f"No TikTok metadata for part {part}")

    tk = entry['tiktok']
    caption = tk['caption'] + ' ' + ' '.join(tk.get('hashtags', []))

    # 1) Initialize upload
    init = requests.post(
        f"{TIKTOK_API_BASE}/v1/media/upload/init/",
        headers={'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}'},
        json={
            'upload_name': os.path.basename(video_path),
            'upload_method': 'POST'
        }
    ).json()
    upload_id  = init['data']['upload_id']
    upload_url = init['data']['upload_url']

    # 2) Transfer the file
    with open(video_path, 'rb') as fp:
        files = {'file': fp}
        r = requests.post(upload_url, files=files)
        r.raise_for_status()

    # 3) Publish
    pub = requests.post(
        f"{TIKTOK_API_BASE}/v1/media/publish/",
        headers={'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}'},
        json={'upload_id': upload_id, 'caption': caption}
    ).json()

    print("TikTok response:", pub)
    return pub


if __name__ == '__main__':
    JSON = '/path/to/stories.json'
    VID = '/path/to/video_part1.mp4'

    check_youtube_channel()

    # Upload to YouTube Shorts
    #upload_youtube_short(VID, JSON)

    # Upload to TikTok
    #upload_tiktok(VID, JSON)
