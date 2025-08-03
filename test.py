import uuid
import json
import os
import subprocess
import random
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from pathlib import Path
from upload_handlers import (
    ensure_tiktok_auth,
    start_auto_refresher,
    upload_youtube_short,
    upload_tiktok
)

# ─── Load environment variables ────────────────────────
load_dotenv()  # expects .env with OPENAI_API_KEY & ELEVENLABS_API_KEY

def upload_all_videos():
    """Upload all videos from the videos directory to YouTube and TikTok."""
    # Setup paths
    videos_dir = Path("videos")
    metadata_dir = Path("audio_and_subtitles")
    
    # Verify YouTube client secrets file exists
    client_secrets_file = os.getenv('YOUTUBE_CLIENT_SECRETS_FILE')
    
    if not client_secrets_file:
        print("❌ YOUTUBE_CLIENT_SECRETS_FILE not set in .env!")
        print("Please add the path to your client_secret.json file in your .env file.")
        return

    client_secrets_path = Path(client_secrets_file)
    if not client_secrets_path.exists():
        print(f"❌ YouTube client secrets file not found at: {client_secrets_file}")
        print("Please check that the path in your .env file is correct.")
        return

    # Ensure TikTok authentication is ready
    try:
        print("\n🔑 Checking TikTok authentication...")
        ensure_tiktok_auth()
        
        # Double check that we have valid tokens
        token_store = Path.home() / '.tiktok_token.json'
        if not token_store.exists():
            print("❌ TikTok token file not found after authentication!")
            return
            
        token_data = json.loads(token_store.read_text())
        if not all(k in token_data for k in ['access_token', 'refresh_token', 'expires_at']):
            print("❌ TikTok token file is missing required fields!")
            return
            
        print("✅ TikTok tokens found and validated")
        start_auto_refresher()
        
    except Exception as e:
        print(f"❌ TikTok authentication failed: {e}")
        print("\nTo fix this:")
        print("1. Make sure your .env file has:")
        print("   TIKTOK_CLIENT_KEY=your_client_key")
        print("   TIKTOK_LOGIN_URL=https://your-site.netlify.app/.netlify/functions/login")
        print("2. Delete ~/.tiktok_token.json if it exists")
        print("3. Run the script again and complete the authentication process")
        return

    # Get all video files
    video_files = sorted(videos_dir.glob("*.mp4"))
    
    if not video_files:
        print("❌ No video files found in videos directory!")
        return
        
    print(f"\n📁 Found {len(video_files)} video files to process")
    
    for video_path in video_files:
        # Extract the UUID from the video filename (everything before _part)
        uuid = video_path.name.split('_part')[0]
        
        # Find corresponding metadata file
        metadata_file = metadata_dir / f"{uuid}_metadata.json"
        
        if not metadata_file.exists():
            print(f"⚠️  No metadata found for {video_path.name}, skipping...")
            continue

        print(f"\n📤 Processing {video_path.name}...")
        
        # try:
        #     print("Uploading to YouTube Shorts...")
        #     youtube_response = upload_youtube_short(str(video_path), str(metadata_file))
        #     print(f"✅ YouTube upload complete! Video ID: {youtube_response['id']}")
        # except Exception as e:
        #     print(f"❌ YouTube upload failed: {e}")
        #     print("Make sure you have:")
        #     print(f"1. Valid client_secret.json file at: {client_secrets_file}")
        #     print("2. Enabled the YouTube Data API v3")
        #     print("3. Correct OAuth 2.0 credentials configured")

        try:
            print("\nUploading to TikTok...")
            # Verify token before upload
            token_data = json.loads((Path.home() / '.tiktok_token.json').read_text())
            print(f"Using access token: {token_data['access_token'][:20]}...")
            
            tiktok_response = upload_tiktok(str(video_path), str(metadata_file))
            print(f"✅ TikTok upload complete! Status: {tiktok_response}")
        except Exception as e:
            print(f"❌ TikTok upload failed: {e}")
            print("\nTo fix TikTok upload:")
            print("1. Delete ~/.tiktok_token.json")
            print("2. Run the script again to re-authenticate")
            print("3. Make sure you complete the TikTok authentication in the browser")
            print("4. Check that you copied and pasted the entire token data correctly")

if __name__ == "__main__":
    upload_all_videos()
