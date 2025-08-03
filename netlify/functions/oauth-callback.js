const fetch = require("node-fetch");

exports.handler = async (event) => {
  const { code, state } = event.queryStringParameters;
  const cookieHeader = event.headers.cookie || "";
  const expectedState = cookieHeader.match(/csrfState=([^;]+)/)?.[1];

  if (!expectedState || expectedState !== state) {
    return { statusCode: 400, body: "Invalid CSRF state" };
  }

  if (!code) {
    return { statusCode: 400, body: "Missing code" };
  }

  // Exchange code for token at the correct v2 endpoint:
  const tokenRes = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_key: process.env.TIKTOK_CLIENT_KEY,
      client_secret: process.env.TIKTOK_CLIENT_SECRET,
      code,
      grant_type: "authorization_code",
      redirect_uri: process.env.TIKTOK_REDIRECT_URI,
    }),
  });

  if (!tokenRes.ok) {
    const err = await tokenRes.text();
    return {
      statusCode: tokenRes.status,
      body: `Token exchange failed: ${err}`,
    };
  }

  const data = await tokenRes.json();
  console.log("Token response:", JSON.stringify(data, null, 2));

  // TikTok v2 API returns tokens directly in the response, not nested under data
  const expires_at = Math.floor(Date.now() / 1000) + data.expires_in;

  // Format token data
  const tokenData = JSON.stringify(
    {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: expires_at,
    },
    null,
    2
  );

  // Create HTML page that displays tokens for easy copying
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; }
        .token-box { 
          background: #f5f5f5; 
          padding: 1em; 
          border-radius: 4px;
          margin: 1em 0;
        }
        pre { white-space: pre-wrap; word-wrap: break-word; }
      </style>
    </head>
    <body>
      <h2>Authentication Successful! 🎉</h2>
      <p>Please copy the entire token data below and paste it back in the terminal:</p>
      <div class="token-box">
        <pre id="tokens">${tokenData}</pre>
      </div>
      <button onclick="copyTokens()">Copy Token Data</button>
      <p id="copyStatus"></p>

      <script>
        function copyTokens() {
          const tokens = document.getElementById('tokens').textContent;
          navigator.clipboard.writeText(tokens).then(() => {
            document.getElementById('copyStatus').textContent = '✅ Copied! Now paste this back in the terminal.';
          }).catch(err => {
            document.getElementById('copyStatus').textContent = '❌ Failed to copy. Please select and copy manually.';
          });
        }
      </script>
    </body>
    </html>
  `;

  return {
    statusCode: 200,
    headers: {
      "Content-Type": "text/html",
      "Set-Cookie":
        "csrfState=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax",
    },
    body: html,
  };
};
