import os
import subprocess
import sys
import urllib.request
from pathlib import Path

CONFIG_FILE = "bot_path.txt"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/jasonsgunz/self-hosting-bot-discord/refs/heads/main/discord%20cmd.py"
DEFAULT_BOT_DIR = os.path.join(os.environ['APPDATA'], "DiscordBot")
DEFAULT_BOT_PATH = os.path.join(DEFAULT_BOT_DIR, "bot.py")
REQUIRED_PACKAGES = ["discord.py", "colorama"]

def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def get_local_path():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            path = f.read().strip()
            if os.path.exists(path):
                return path
    return DEFAULT_BOT_PATH

def save_local_path(path):
    with open(CONFIG_FILE, "w") as f:
        f.write(path)

def fetch_github_code():
    try:
        with urllib.request.urlopen(GITHUB_RAW_URL, timeout=10) as response:
            if response.status == 200:
                return response.read().decode("utf-8"), None
            else:
                return None, f"HTTP {response.status}"
    except Exception as e:
        return None, str(e)

def download_to_default():
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
        ensure_dir(local_path)
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(github_code)
        print("Bot updated with latest version.")
        return True

def install_packages():
    python_exe = sys.executable
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package.replace("-", "_"))
            print(f"✓ {package} already installed.")
        except ImportError:
            print(f"Installing {package}...")
            try:
                subprocess.run([python_exe, "-m", "pip", "install", package],
                               check=True, capture_output=True, text=True)
                print(f"✓ {package} installed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e.stderr}")
                return False
            except Exception as e:
                print(f"Unexpected error while installing {package}: {e}")
                return False
    return True

def launch_bot(path):
    python_exe = sys.executable
    subprocess.Popen(f'start cmd /k ""{python_exe}" "{path}""', shell=True)

if __name__ == "__main__":
    bot_path = get_local_path()

    if not os.path.exists(bot_path):
        print("Bot file not found. Checking required packages...")
        if not install_packages():
            print("Package installation failed. Please install the required packages manually:")
            print(f"  python -m pip install {' '.join(REQUIRED_PACKAGES)}")
            input("Press Enter to exit.")
            sys.exit(1)

        print("Downloading bot from GitHub...")
        new_path = download_to_default()
        if new_path is None:
            input("Press Enter to exit.")
            sys.exit(1)
        save_local_path(new_path)
        bot_path = new_path
    else:
        print(f"Found bot at: {bot_path}")

    check_for_updates(bot_path)
    launch_bot(bot_path)
