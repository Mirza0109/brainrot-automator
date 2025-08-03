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

  // Create HTML page that displays tokens in a format Python can parse
  const html = `
    <!DOCTYPE html>
    <html>
    <body>
      <h2>Authentication Successful!</h2>
      <p>Your tokens are ready. The Python script will automatically save these.</p>
      <pre id="tokens" style="display:none">
        ${JSON.stringify(
          {
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            expires_at: expires_at,
          },
          null,
          2
        )}
      </pre>
      <script>
        // The Python script will look for this element
        document.title = 'TIKTOK_AUTH_SUCCESS';
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
