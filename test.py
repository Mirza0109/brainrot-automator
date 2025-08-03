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

    # Get all video files first
    video_files = sorted(videos_dir.glob("*.mp4"))
    if not video_files:
        print("❌ No video files found in videos directory!")
        return
        
    print(f"\n📁 Found {len(video_files)} video files to process")

    # Ensure TikTok authentication is ready
    try:
        print("\n🔑 Setting up TikTok authentication...")
        ensure_tiktok_auth()
        start_auto_refresher()
    except Exception as e:
        print(f"\n❌ TikTok authentication failed: {e}")
        print("\nTo fix this:")
        print("1. Check your .env file has:")
        print("   TIKTOK_CLIENT_KEY=your_client_key")
        print("   TIKTOK_LOGIN_URL=https://your-site.netlify.app/.netlify/functions/login")
        print("2. Delete ~/.tiktok_token.json if it exists")
        print("3. Make sure your Netlify functions are properly deployed")
        print("4. Run the script again and follow the authentication steps carefully")
        return

    # Process each video
    for video_path in video_files:
        # Extract the UUID from the video filename (everything before _part)
        uuid = video_path.name.split('_part')[0]
        
        # Find corresponding metadata file
        metadata_file = metadata_dir / f"{uuid}_metadata.json"
        
        if not metadata_file.exists():
            print(f"\n⚠️  No metadata found for {video_path.name}, skipping...")
            continue

        print(f"\n📤 Processing {video_path.name}...")

        try:
            print("\nUploading to TikTok...")
            # Verify token before upload
            token_store = Path.home() / '.tiktok_token.json'
            if not token_store.exists():
                raise Exception("Token file not found! Please authenticate again.")
                
            token_data = json.loads(token_store.read_text())
            print(f"Using access token: {token_data['access_token'][:20]}...")
            
            tiktok_response = upload_tiktok(str(video_path), str(metadata_file))
            print(f"✅ TikTok upload complete! Status: {tiktok_response}")
        except Exception as e:
            print(f"\n❌ TikTok upload failed: {e}")
            print("\nTo fix this:")
            print("1. Delete ~/.tiktok_token.json")
            print("2. Run the script again to re-authenticate")
            print("3. Make sure to:")
            print("   - Complete the TikTok authentication in the browser")
            print("   - Copy the ENTIRE token data (including { and })")
            print("   - Paste it correctly in the terminal")
            print("   - Press Ctrl+D (Mac/Linux) or Ctrl+Z (Windows) followed by Enter")
            return  # Stop processing if TikTok auth fails

if __name__ == "__main__":
    upload_all_videos()
