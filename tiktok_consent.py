from flask import Flask, request, redirect
import requests, os

app = Flask(__name__)

CLIENT_KEY    = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = "https://mirza0109.github.io/brainrot-automator/oauth/callback"

# 1) Send the user here to log in & authorize:
@app.route("/login/tiktok")
def login_tiktok():
    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": "video.upload",            # or "video.publish"
        "redirect_uri": REDIRECT_URI,
        "state": "secure-random-state"
    }
    url = "https://open.tiktokapis.com/v2/oauth/authorize/?" + \
          "&".join(f"{k}={v}" for k,v in params.items())
    return redirect(url)

# 2) Handle the callback and exchange code for a user token:
@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key":    CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code":          code,
            "grant_type":    "authorization_code",
            "redirect_uri":  REDIRECT_URI
        }
    ).json()
    # Save these for your upload calls:
    user_token = resp["access_token"]
    open_id    = resp["open_id"]
    # e.g. store in DB or export as env var:
    os.environ["TIKTOK_ACCESS_TOKEN"] = user_token

    return "✅ TikTok connected! You can now upload on behalf of this user."
