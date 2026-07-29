#!/usr/bin/env python3
"""Quick OAuth flow to refresh Google Sheets credentials."""
import json
import os

# Use the client secret from Downloads
CLIENT_SECRET_PATH = "/mnt/c/Users/lplim/Downloads/client_secret_204235255856-7v204fflrmocajqskhat9c85p58cstfv.apps.googleusercontent.com.json"
TOKENS_PATH = os.path.expanduser("~/.mcp-z/tokens.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

with open(CLIENT_SECRET_PATH) as f:
    cs = json.load(f)["installed"]

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_config(
    {"installed": cs},
    scopes=SCOPES,
)
creds = flow.run_local_server(port=0, open_browser=False)

# Save back into the MCP-Z tokens.json format
token_value = {
    "accessToken": creds.token,
    "refreshToken": creds.refresh_token,
    "expiresAt": int(creds.expiry.timestamp() * 1000) if creds.expiry else None,
    "scope": " ".join(SCOPES),
}

# Update existing tokens.json
if os.path.exists(TOKENS_PATH):
    with open(TOKENS_PATH) as f:
        tokens_data = json.load(f)
else:
    tokens_data = {"cache": []}

# Update or add the token entry
updated = False
for i, (key, val) in enumerate(tokens_data.get("cache", [])):
    if ":token" in key:
        inner = json.loads(val["value"])
        inner["value"] = token_value
        val["value"] = json.dumps(inner)
        updated = True
        break

if not updated:
    tokens_data.setdefault("cache", []).append([
        "keyv:lpl1696@gmail.com:mcp-sheets:token",
        {"value": json.dumps({"value": token_value})}
    ])

with open(TOKENS_PATH, 'w') as f:
    json.dump(tokens_data, f)

print(f"✅ OAuth tokens refreshed and saved to {TOKENS_PATH}")
print(f"   Access token: {creds.token[:20]}...")
print(f"   Refresh token: {creds.refresh_token[:20]}...")
