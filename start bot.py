import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# ===== CONFIGURATION =====
CONFIG_FILE = "bot_path.txt"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/jasonsgunz/self-hosting-bot-discord/refs/heads/main/discord%20cmd.py"
DEFAULT_BOT_DIR = os.path.join(os.environ['APPDATA'], "DiscordBot")
DEFAULT_BOT_PATH = os.path.join(DEFAULT_BOT_DIR, "bot.py")
# =========================

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

def get_local_path():
    """Read the bot file path from config, or return default if missing/invalid."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            path = f.read().strip()
            if os.path.exists(path):
                return path
    # Fallback to default if config missing or path invalid
    return DEFAULT_BOT_PATH

def save_local_path(path):
    """Save the bot file path to config."""
    with open(CONFIG_FILE, "w") as f:
        f.write(path)

def fetch_github_code():
    """Download the raw code from GitHub. Returns (content, error)."""
    try:
        with urllib.request.urlopen(GITHUB_RAW_URL, timeout=10) as response:
            if response.status == 200:
                return response.read().decode("utf-8"), None
            else:
                return None, f"HTTP {response.status}"
    except Exception as e:
        return None, str(e)

def download_to_default():
    """Download code from GitHub and save to default location."""
    print("Fetching bot code from GitHub...")
    code, error = fetch_github_code()
    if error:
        print(f"Download failed: {error}")
        return None

    ensure_dir(DEFAULT_BOT_PATH)
    with open(DEFAULT_BOT_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Bot code saved to: {DEFAULT_BOT_PATH}")
    return DEFAULT_BOT_PATH

def check_for_updates(local_path):
    """Compare local file with GitHub version. Update if different."""
    print("Checking for updates...")
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            local_code = f.read()
    except Exception as e:
        print(f"Could not read local file: {e}")
        return False

    github_code, error = fetch_github_code()
    if error:
        print(f"GitHub fetch failed ({error}), using existing file.")
        return False

    if local_code == github_code:
        print("Bot is up to date.")
        return False
    else:
        # Overwrite with new code
        ensure_dir(local_path)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(github_code)
        print("Bot updated with latest version.")
        return True

def launch_bot(path):
    """Launch the bot in a new CMD window."""
    python_exe = sys.executable
    subprocess.Popen(f'start cmd /k ""{python_exe}" "{path}""', shell=True)

# ===== MAIN SCRIPT =====
if __name__ == "__main__":
    # 1. Determine the bot file path
    bot_path = get_local_path()

    # If the file doesn't exist at the resolved path, download it fresh
    if not os.path.exists(bot_path):
        print("Bot file not found. Downloading from GitHub...")
        new_path = download_to_default()
        if new_path is None:
            input("Press Enter to exit.")  # Pause so user sees error
            sys.exit(1)
        # Update config with the default path
        save_local_path(new_path)
        bot_path = new_path
    else:
        print(f"Found bot at: {bot_path}")

    # 2. Check for updates (always do this)
    check_for_updates(bot_path)

    # 3. Launch the bot
    launch_bot(bot_path)