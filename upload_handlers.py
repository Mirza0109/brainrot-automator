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
    Ensure we have a valid TikTok access token: refresh if expired, otherwise trigger manual auth.
    """
    global access_token, refresh_token, expires_at
    now = time.time()
    # If no token or expired
    if not access_token or now >= expires_at:
        if refresh_token and CLIENT_KEY:
            print("Refreshing TikTok access token...")
            refresh_access_token()
        else:
            print(f"\nPlease complete TikTok authentication in your browser:")
            print(f"1. Open this URL: {LOGIN_URL}")
            print("2. Log in and authorize the application")
            print("3. When you see 'Authentication Successful', copy the token data")
            print("4. Paste the token data here and press Enter:")
            
            token_data = input().strip()
            try:
                tokens = json.loads(token_data)
                # Validate token data
                if not all(k in tokens for k in ['access_token', 'refresh_token', 'expires_at']):
                    raise ValueError("Missing required token fields")
                
                # Save tokens
                access_token = tokens['access_token']
                refresh_token = tokens['refresh_token']
                expires_at = int(tokens['expires_at'])
                save_tokens()
                print("TikTok authentication complete.")
            except json.JSONDecodeError:
                print("Error: Invalid JSON format. Please copy the entire token data exactly as shown.")
                raise
            except Exception as e:
                print(f"Error processing tokens: {e}")
                raise

# ─── Auto-refresh thread ────────────────────────────────────────────────────────
def save_tokens():
    TOKEN_STORE.write_text(json.dumps({
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'expires_at':    expires_at
    }))

def refresh_access_token():
    global access_token, refresh_token, expires_at
    resp = requests.post(
        REFRESH_URL,
        data={
            'client_key':    CLIENT_KEY,
            'refresh_token': refresh_token
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    resp.raise_for_status()
    data = resp.json()['data']
    access_token  = data['access_token']
    refresh_token = data['refresh_token']
    expires_at    = int(time.time()) + data['expires_in']
    save_tokens()
    print(f"[TikTok] Token refreshed; expires at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))}")

def _auto_refresher():
    while True:
        wait = expires_at - time.time() - 60
        if wait > 0:
            time.sleep(wait)
        try:
            refresh_access_token()
        except Exception as e:
            print(f"Failed to refresh TikTok token: {e}")
            time.sleep(60)

def start_auto_refresh_thread():
    if refresh_token and CLIENT_KEY:
        t = threading.Thread(target=_auto_refresher, daemon=True)
        t.start()

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
    part = int(re.search(r'(\d+)', fname).group(1))
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


def upload_tiktok(video_path: str, json_path: str):
    # Ensure we have a valid TikTok token
    ensure_tiktok_auth()
    part = int(re.search(r'(\d+)', os.path.basename(video_path)).group(1))
    with open(json_path) as f:
        data = json.load(f)
    entry = next((v for v in data['videos'] if v.get('part') == part), None)
    if not entry or 'tiktok' not in entry:
        raise KeyError(f"No TikTok metadata for part {part}")
    tk = entry['tiktok']
    caption = tk['caption'] + ' ' + ' '.join(tk.get('hashtags', []))
    size = os.path.getsize(video_path)
    init = requests.post(f"{TIKTOK_API_BASE}/v2/post/publish/video/init/",
                         headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                         json={'post_info': {'title': caption, 'privacy_level': 'PUBLIC_TO_EVERYONE'},
                               'source_info': {'source': 'FILE_UPLOAD', 'video_size': size, 'chunk_size': size, 'total_chunk_count': 1}})
    init.raise_for_status()
    data = init.json()['data']
    publish_id, upload_url = data['publish_id'], data['upload_url']
    with open(video_path, 'rb') as fp:
        chunk = fp.read()
    put = requests.put(upload_url, headers={'Content-Type': 'video/mp4', 'Content-Range': f'bytes 0-{len(chunk)-1}/{len(chunk)}'}, data=chunk)
    put.raise_for_status()
    status = requests.get(f"{TIKTOK_API_BASE}/v2/post/publish/get_status/", headers={'Authorization': f'Bearer {access_token}'}, params={'publish_id': publish_id})
    status.raise_for_status()
    print(f"TikTok publish status: {status.json()['data']}")
    return status.json()['data']


if __name__ == '__main__':
    # Ensure authentication and start refresher
    ensure_tiktok_auth()
    start_auto_refresh_thread()

    JSON = '/path/to/stories.json'
    VID  = '/path/to/video_part1.mp4'

    check_youtube_channel()
    # upload_youtube_short(VID, JSON)
    # upload_tiktok(VID, JSON)
