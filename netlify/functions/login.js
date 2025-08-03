// netlify/functions/login.js
exports.handler = async () => {
    const clientKey   = process.env.TIKTOK_CLIENT_KEY;
    const redirectUri = encodeURIComponent(process.env.TIKTOK_REDIRECT_URI);
    const state       = "secure-random-string"; // you can generate/store per session
  
    const authUrl = 
    `https://open.tiktokapis.com/v2/oauth/authorize/?` + 
    `client_key=${CLIENT_KEY}` +
    `&response_type=code` +
    `&scope=${scopes}` +
    `&redirect_uri=${redirectUri}` +
    `&state=${state}`;
    
    return {
      statusCode: 302,
      headers: { Location: authUrl },
    };
  };
  