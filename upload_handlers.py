import os
import re
import json
import requests
import time
import threading
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# ─── Token persistence ─────────────────────────────────────────────────────────
TOKEN_STORE = Path.home() / '.tiktok_token.json'
CLIENT_KEY  = os.getenv('TIKTOK_CLIENT_KEY')

# Load stored tokens or environment
if TOKEN_STORE.exists():
    data = json.loads(TOKEN_STORE.read_text())
    access_token  = data.get('access_token')
    refresh_token = data.get('refresh_token')
    expires_at    = data.get('expires_at', 0)
else:
    access_token  = os.getenv('TIKTOK_ACCESS_TOKEN')
    refresh_token = os.getenv('TIKTOK_REFRESH_TOKEN')
    expires_at    = int(os.getenv('TIKTOK_EXPIRES_AT', 0))

TIKTOK_API_BASE = 'https://open.tiktokapis.com'
REFRESH_URL     = f"{TIKTOK_API_BASE}/v2/oauth/refresh_token/"
LOGIN_URL       = os.getenv('TIKTOK_LOGIN_URL', 'https://<your-site>/.netlify/functions/login')

# ─── Authentication Helper ─────────────────────────────────────────────────────
def ensure_tiktok_auth():
    """
    Ensure we have a valid TikTok access token: 
    - If still unexpired, do nothing.
    - Else if we have a refresh_token, rotate it.
    - Otherwise kick off a manual login in the browser.
    """
    global access_token, refresh_token, expires_at

    now = time.time()
    if access_token and now < expires_at:
        return

    if refresh_token and CLIENT_KEY:
        print("🔄 Refreshing TikTok access token…")
        refresh_access_token()
        start_auto_refresher()  # make sure the background thread is running
        return

    # Manual flow:
    print("\n🔐 TikTok manual authentication required:")
    print(f"→ Opening your browser to: {LOGIN_URL}")
    webbrowser.open(LOGIN_URL)
    print("When you see your JSON token response, copy it and then press Enter here.")
    input("Press Enter to paste token data (end with EOF)…\n")

    # Read multi-line JSON from stdin until EOF
    token_lines = []
    try:
        while True:
            token_lines.append(input())
    except EOFError:
        pass

    try:
        tokens = json.loads("\n".join(token_lines))
        for key in ("access_token", "refresh_token", "expires_at"):
            if key not in tokens:
                raise KeyError(f"Missing '{key}' in token data")
        access_token  = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_at    = int(tokens["expires_at"])
        save_tokens()
        print("✅ TikTok authentication complete!")
        start_auto_refresher()
    except Exception as e:
        print(f"❌ Failed to process token data: {e}")
        raise


# ─── Token Persistence ──────────────────────────────────────────────────────────
def save_tokens():
    """Write current tokens + expiry out to disk."""
    TOKEN_STORE.write_text(json.dumps({
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "expires_at":    expires_at
    }))


def refresh_access_token():
    """
    Hit TikTok’s refresh endpoint to rotate both access & refresh tokens.
    """
    global access_token, refresh_token, expires_at
    resp = requests.post(
        REFRESH_URL,
        data={ "client_key": CLIENT_KEY, "refresh_token": refresh_token },
        headers={ "Content-Type": "application/x-www-form-urlencoded" }
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    access_token  = data["access_token"]
    refresh_token = data["refresh_token"]
    expires_at    = int(time.time()) + data["expires_in"]
    save_tokens()
    print(f"[TikTok] Token refreshed; next expiry at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))}")


# ─── Background Auto‐Refresh ────────────────────────────────────────────────────
def _auto_refresher():
    """Sleep until 60s before expiry, then refresh, looping forever."""
    while True:
        wait = expires_at - time.time() - 60
        if wait > 0:
            time.sleep(wait)
        try:
            refresh_access_token()
        except Exception as e:
            print(f"⚠️  Auto‐refresh failed: {e}")
            time.sleep(60)


def start_auto_refresher():
    """Spawn the daemon thread if we have a refresh_token already."""
    if refresh_token and CLIENT_KEY:
        t = threading.Thread(target=_auto_refresher, daemon=True)
        t.start()


# ─── TikTok Upload Function ────────────────────────────────────────────────────
def upload_tiktok(video_path: str, json_path: str):
    """
    Upload a single video (partN.mp4) to TikTok using the direct‐post API.
    """
    ensure_tiktok_auth()

    # 1) Determine which “part” we’re uploading
    fname = os.path.basename(video_path)
    m = re.search(r"part(\d+)", fname)
    if not m:
        raise ValueError(f"Cannot extract part number from '{fname}'")
    part = int(m.group(1))

    # 2) Load metadata (caption + hashtags)
    with open(json_path) as f:
        data = json.load(f)
    entry = next((v for v in data.get("videos", []) if v.get("part") == part), None)
    if not entry or "tiktok" not in entry:
        raise KeyError(f"No TikTok metadata for part {part}")
    tk = entry["tiktok"]
    caption = tk.get("caption", "") + " " + " ".join(tk.get("hashtags", []))

    # 3) INIT: get publish_id + upload_url
    size = os.path.getsize(video_path)
    init_url = f"{TIKTOK_API_BASE}/v2/post/publish/video/init/"
    init_resp = requests.post(
        init_url,
        headers={ "Authorization": f"Bearer {access_token}", "Content-Type": "application/json" },
        json={
            "post_info":   { "title": caption, "privacy_level": "PUBLIC_TO_EVERYONE" },
            "source_info": { "source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1 }
        }
    )
    if init_resp.status_code != 200:
        print(f"❌ TikTok init failed ({init_resp.status_code}): {init_resp.text}")
        init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    publish_id, upload_url = init_data["publish_id"], init_data["upload_url"]

    # 4) PUT: upload the MP4
    with open(video_path, "rb") as fp:
        chunk = fp.read()
    put_resp = requests.put(
        upload_url,
        headers={ "Content-Type": "video/mp4", "Content-Range": f"bytes 0-{len(chunk)-1}/{len(chunk)}" },
        data=chunk
    )
    if put_resp.status_code != 200:
        print(f"❌ TikTok upload failed ({put_resp.status_code}): {put_resp.text}")
        put_resp.raise_for_status()

    # 5) POLL status
    status_resp = requests.get(
        f"{TIKTOK_API_BASE}/v2/post/publish/get_status/",
        headers={ "Authorization": f"Bearer {access_token}" },
        params={ "publish_id": publish_id }
    )
    status_resp.raise_for_status()
    status = status_resp.json().get("data")
    print(f"✅ TikTok publish status: {status}")
    return status

# ─── YouTube Shorts ────────────────────────────────────────────────────────────
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ─── YouTube Configuration ─────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.absolute()
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE', SCRIPT_DIR / 'client_secret.json')
YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'
]
YOUTUBE_API_SERVICE = ('youtube', 'v3')


def _get_youtube_client():
    flow = InstalledAppFlow.from_client_secrets_file(str(YOUTUBE_CLIENT_SECRETS_FILE), YOUTUBE_SCOPES)
    creds = flow.run_local_server(port=0)
    youtube = build(YOUTUBE_API_SERVICE[0], YOUTUBE_API_SERVICE[1], credentials=creds)
    channel = youtube.channels().list(part='snippet', mine=True).execute().get('items', [])
    if channel:
        info = channel[0]['snippet']
        print(f"Connected to YouTube channel: {info['title']}")
    return youtube


def check_youtube_channel():
    youtube = _get_youtube_client()
    resp = youtube.channels().list(part='snippet', mine=True).execute()
    print(resp)
    return resp['items'][0]['snippet']


def upload_youtube_short(video_path: str, json_path: str):
    fname = os.path.basename(video_path)
    # Extract part number from filename like "uuid_part1.mp4"
    part = int(re.search(r'part(\d+)', fname).group(1))
    with open(json_path) as f:
        data = json.load(f)
    entry = next((v for v in data['videos'] if v.get('part') == part), None)
    if not entry or 'youtube_shorts' not in entry:
        raise KeyError(f"No YouTube metadata for part {part}")
    meta = entry['youtube_shorts']
    youtube = _get_youtube_client()
    body = {
        'snippet': { 'title': meta['title'], 'description': meta['description'], 'tags': meta.get('tags', []), 'categoryId': '22' },
        'status': { 'privacyStatus': 'public' }
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




if __name__ == '__main__':
    # Ensure authentication and start refresher
    ensure_tiktok_auth()
    start_auto_refresher()

    JSON = '/path/to/stories.json'
    VID  = '/path/to/video_part1.mp4'

    check_youtube_channel()
    # upload_youtube_short(VID, JSON)
    # upload_tiktok(VID, JSON)
