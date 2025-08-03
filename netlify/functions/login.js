// netlify/functions/login.js
exports.handler = async () => {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const redirectUri = encodeURIComponent(process.env.TIKTOK_REDIRECT_URI);
  const state = Math.random().toString(36).substring(2);
  const scopes = ["user.info.basic", "video.upload", "video.publish"].join(",");
  const encodedScopes = encodeURIComponent(scopes);

  const authUrl =
    `https://www.tiktok.com/v2/auth/authorize/?` +
    `client_key=${clientKey}` +
    `&response_type=code` +
    `&scope=${encodedScopes}` +
    `&redirect_uri=${redirectUri}` +
    `&state=${state}`;

  return {
    statusCode: 302,
    headers: {
      Location: authUrl,
      "Set-Cookie": `csrfState=${state}; Max-Age=60000; Path=/; HttpOnly; Secure; SameSite=Lax`,
    },
  };
};
