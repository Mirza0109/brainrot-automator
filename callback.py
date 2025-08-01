from flask import Flask, request
app = Flask(__name__)

@app.route('/oauth/callback')
def cb():
    code = request.args.get('code')
    print("Got TikTok auth code:", code)
    return "✅ Code received — check your console!"

if __name__=='__main__':
    app.run(port=8090)