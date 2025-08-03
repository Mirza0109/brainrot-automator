// netlify/functions/oauth-callback.js
const fetch = require("node-fetch");

exports.handler = async (event) => {
  const params = new URLSearchParams(event.queryStringParameters);
  const code   = params.get("code");
  const state  = params.get("state");
  const csrfState = event.cookies.get("csrfState");

  if (csrfState !== state) {
    return { statusCode: 400, body: "Invalid CSRF state" };
  }

  if (!code) {
    return { statusCode: 400, body: "Missing code" };
  }

  // Exchange code for token
  const tokenRes = await fetch("https://www.tiktok.com/v2/auth/token/", {
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
  const data = await tokenRes.json();

  // TODO: persist data.access_token & data.open_id (e.g. in Fauna, Dynamo, etc.)

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ success: true, data }),
  };
};

