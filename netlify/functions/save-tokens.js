const fs = require("fs");
const path = require("path");
const os = require("os");

exports.handler = async (event) => {
  // Only allow POST requests
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    const tokenData = JSON.parse(event.body);
    const tokenPath = path.join(os.homedir(), ".tiktok_token.json");

    // Save tokens to file
    fs.writeFileSync(tokenPath, JSON.stringify(tokenData, null, 2));

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ success: true }),
    };
  } catch (error) {
    console.error("Error saving tokens:", error);
    return {
      statusCode: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        success: false,
        error: error.message,
      }),
    };
  }
};
