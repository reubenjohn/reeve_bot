import time
import subprocess
import requests
import json
import os
from pathlib import Path

# Load environment variables from .env file if it exists
def load_env():
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOSE_SESSION_NAME = os.getenv("GOOSE_SESSION_NAME", "reeve_default")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required. Create a .env file with BOT_TOKEN=your_token")

# Function to get updates from Telegram
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 100, "offset": offset}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Error polling Telegram: {e}")
        return None

def main():
    print(f"🤖 Listening for messages for Goose session: '{GOOSE_SESSION_NAME}'...")
    last_update_id = None

    while True:
        updates = get_updates(last_update_id)
        
        if not updates or "result" not in updates:
            continue

        for update in updates["result"]:
            last_update_id = update["update_id"] + 1
            
            # Check if it's a text message
            if "message" not in update or "text" not in update["message"]:
                continue
            user_text = update["message"]["text"]
            user_name = update["message"]["from"].get("first_name", "User")
            goose_prompt = f"\n📩 Telegram message from {user_name} to Reeve bot: {user_text}"
            
            print(goose_prompt)
            print("🚀 Triggering Goose...\n---")

            # --- THE HOOK: RUN GOOSE CLI ---
            # We use 'goose run' instead of 'session' so it executes and exits
            # -n: uses a named session to keep memory/context
            # -r: resumes that session
            # -t: passes your text as the instruction
            cmd = [
                "goose", "run",
                "-n", GOOSE_SESSION_NAME,
                "--resume",
                "--text", goose_prompt
            ]
            
            # Run the command and wait for it to finish
            subprocess.run(cmd)
            print("---\n✅ Goose task complete. Listening for more...")

        time.sleep(1) # Sleep to prevent CPU spiking

if __name__ == "__main__":
    main()
