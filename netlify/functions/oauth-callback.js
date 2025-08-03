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
      client_key:    process.env.TIKTOK_CLIENT_KEY,
      client_secret: process.env.TIKTOK_CLIENT_SECRET,
      code,
      grant_type:    "authorization_code",
      redirect_uri:  process.env.TIKTOK_REDIRECT_URI, 
    }),
  });

  if (!tokenRes.ok) {
    const err = await tokenRes.text();
    return { statusCode: tokenRes.status, body: `Token exchange failed: ${err}` };
  }

  const data = await tokenRes.json();

  return {
    statusCode: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie":    "csrfState=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax",
    },
    body: JSON.stringify({ success: true, data }),
  };
};
