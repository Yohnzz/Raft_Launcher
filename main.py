import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import json
import os
import sys
import shutil
import time
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
import winreg

# =========================================================
# CONFIGURATION & CONSTANTS
# =========================================================

APP_NAME = "Raft Multiplayer Launcher"
APP_VERSION = "V 0.3.6"
APP_TITLE = f"Raft Multiplayer Launcher ({APP_VERSION}) - (by Yohnzz)"
APP_AUTHOR = "Igna"
DEFAULT_UPDATE_REPO = "Yohnzz/Raft_Launcher"  # Default GitHub Repo for releases
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "raft_exe": "",
    "steam_user_id": "",
    "selected_world": "",
    "repo_path": "",
    "remote_url": "",
    "branch": "master",
    "update_repo": "Yohnzz/Raft_Launcher",
    "auto_check_steam": True,
    "theme": "light"
}

THEMES = {
    "light": {
        "root_bg":        "#f0f0f0",
        "toolbar_bg":     "#f5f5f5",
        "toolbar_fg":     "#222222",
        "btn_bg":         "#e0e0e0",
        "btn_fg":         "#222222",
        "panel_bg":       "#ffffff",
        "left_frame_bg":  "#ffffff",
        "right_frame_bg": "#f0f0f0",
        "header_bg":      "#e0e0e0",
        "header_fg":      "#222222",
        "tab_bg":         "#f5f5f5",
        "tab_fg":         "#222222",
        "entry_bg":       "#ffffff",
        "entry_fg":       "#000000",
        "statusbar_bg":   "#e8e8e8",
        "statusbar_fg":   "#333333",
        "log_bg":         "#1e1e1e",
        "log_fg":         "#ffffff",
        "label_bg":       "#f5f5f5",
        "label_fg":       "#222222",
        "name_label_bg":  "#f5f5f5",
        "sash_bg":        "#d9d9d9",
    },
    "dark": {
        "root_bg":        "#1e1e2e",
        "toolbar_bg":     "#2a2a3e",
        "toolbar_fg":     "#e0e0e0",
        "btn_bg":         "#3a3a52",
        "btn_fg":         "#e0e0e0",
        "panel_bg":       "#252535",
        "left_frame_bg":  "#252535",
        "right_frame_bg": "#1e1e2e",
        "header_bg":      "#2e2e42",
        "header_fg":      "#cccccc",
        "tab_bg":         "#2a2a3e",
        "tab_fg":         "#cccccc",
        "entry_bg":       "#333348",
        "entry_fg":       "#e0e0e0",
        "statusbar_bg":   "#2a2a3e",
        "statusbar_fg":   "#aaaaaa",
        "log_bg":         "#0d0d1a",
        "log_fg":         "#00ff99",
        "label_bg":       "#2a2a3e",
        "label_fg":       "#e0e0e0",
        "name_label_bg":  "#2a2a3e",
        "sash_bg":        "#1a1a2a",
    }
}

# =========================================================
# AUTO-UPDATE MANAGER (GITHUB RELEASES)
# =========================================================

class UpdateManager:
    @staticmethod
    def get_clean_version(ver_str):
        """Extracts numerical parts like '0.2' from 'V 0.2' or 'v0.3.1' for comparison."""
        m = re.findall(r'\d+', str(ver_str))
        return [int(x) for x in m] if m else [0]

    @staticmethod
    def is_newer_version(remote_ver_str, current_ver_str):
        rem = UpdateManager.get_clean_version(remote_ver_str)
        cur = UpdateManager.get_clean_version(current_ver_str)
        # Compare element by element
        for r, c in zip(rem, cur):
            if r > c:
                return True
            if r < c:
                return False
        return len(rem) > len(cur)

    @staticmethod
    def check_for_updates(repo_slug):
        """Queries GitHub API for latest release. Returns (success, has_update, tag_name, download_url, release_notes)."""
        url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "RaftLauncher-Updater"})
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag_name = data.get("tag_name", "")
                    body = data.get("body", "")
                    assets = data.get("assets", [])

                    download_url = None
                    for a in assets:
                        if a.get("name", "").lower().endswith(".exe"):
                            download_url = a.get("browser_download_url")
                            break

                    has_update = UpdateManager.is_newer_version(tag_name, APP_VERSION)
                    return True, has_update, tag_name, download_url, body
        except urllib.error.HTTPError as e:
            return False, False, None, None, f"HTTP Error: {e.code}"
        except Exception as e:
            return False, False, None, None, str(e)

        return False, False, None, None, "Tidak ada rilis yang ditemukan."

    @staticmethod
    def perform_update(download_url, current_exe_path, on_progress=None):
        """Downloads new executable and launches updater script to replace and restart."""
        temp_exe = current_exe_path + ".new"
        try:
            req = urllib.request.Request(download_url, headers={"User-Agent": "RaftLauncher-Updater"})
            with urllib.request.urlopen(req, timeout=60) as response, open(temp_exe, "wb") as out_file:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                block_size = 65536

                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size > 0 and on_progress:
                        percent = (downloaded / total_size) * 100
                        on_progress(percent, downloaded, total_size)

            exe_dir = os.path.dirname(current_exe_path)
            updater_bat = os.path.join(exe_dir, "update_launcher.bat")
            script = f"""@echo off
cd /d "{exe_dir}"
timeout /t 3 /nobreak > nul
:retry
del "{current_exe_path}" > nul 2>&1
if exist "{current_exe_path}" (
    timeout /t 1 /nobreak > nul
    goto retry
)
move /y "{temp_exe}" "{current_exe_path}" > nul 2>&1
timeout /t 1 /nobreak > nul
start "" "{current_exe_path}"
del "%~f0" > nul 2>&1
exit
"""
            with open(updater_bat, "w", encoding="utf-8") as f:
                f.write(script)

            # Run updater script and exit current process
            subprocess.Popen([updater_bat], shell=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            os._exit(0)
        except Exception as e:
            if os.path.exists(temp_exe):
                try:
                    os.remove(temp_exe)
                except Exception:
                    pass
            raise e

# =========================================================
# CONFIG MANAGER
# =========================================================

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception:
            pass
    return config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# =========================================================
# STEAM MANAGER
# =========================================================

class SteamManager:
    @staticmethod
    def is_running():
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(
                ['tasklist', '/FI', 'IMAGENAME eq steam.exe'],
                startupinfo=startupinfo,
                text=True,
                errors="ignore"
            )
            return "steam.exe" in output.lower()
        except Exception:
            return False

    @staticmethod
    def get_steam_paths():
        steam_path = None
        steam_exe = None
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            steam_exe, _ = winreg.QueryValueEx(key, "SteamExe")
            winreg.CloseKey(key)
        except Exception:
            pass

        if not steam_exe:
            common = [
                r"C:\Program Files (x86)\Steam\steam.exe",
                r"C:\Program Files\Steam\steam.exe"
            ]
            for p in common:
                if os.path.exists(p):
                    steam_exe = p
                    steam_path = os.path.dirname(p)
                    break
        return steam_path, steam_exe

    @staticmethod
    def get_accounts():
        steam_path, _ = SteamManager.get_steam_paths()
        if not steam_path:
            return []

        loginusers_path = os.path.join(steam_path, "config", "loginusers.vdf")
        if not os.path.exists(loginusers_path):
            return []

        accounts = []
        try:
            with open(loginusers_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            current_steamid = None
            current_data = {}

            for line in lines:
                line_str = line.strip()
                id_match = re.match(r'^"(\d{17})"$', line_str)
                if id_match:
                    if current_steamid and current_data:
                        accounts.append(current_data)
                    current_steamid = id_match.group(1)
                    current_data = {
                        "steamid": current_steamid,
                        "account_name": current_steamid,
                        "persona_name": current_steamid,
                        "most_recent": False
                    }
                    continue

                if current_steamid:
                    if '"AccountName"' in line_str:
                        m = re.search(r'"AccountName"\s+"([^"]+)"', line_str)
                        if m:
                            current_data["account_name"] = m.group(1)
                    elif '"PersonaName"' in line_str:
                        m = re.search(r'"PersonaName"\s+"([^"]+)"', line_str)
                        if m:
                            current_data["persona_name"] = m.group(1)
                    elif '"MostRecent"' in line_str:
                        m = re.search(r'"MostRecent"\s+"([^"]+)"', line_str)
                        if m:
                            current_data["most_recent"] = (m.group(1) == "1")

            if current_steamid and current_data:
                accounts.append(current_data)

        except Exception as e:
            print(f"Error reading Steam accounts: {e}")

        return accounts

    @staticmethod
    def launch_steam(account_name=None):
        _, steam_exe = SteamManager.get_steam_paths()
        if not steam_exe or not os.path.exists(steam_exe):
            return False, "steam.exe tidak ditemukan."

        try:
            cmd = [steam_exe]
            if account_name:
                cmd.extend(["-login", account_name])
            subprocess.Popen(cmd)
            return True, "Steam berhasil dijalankan."
        except Exception as e:
            return False, str(e)


# =========================================================
# RAFT SAVE / WORLD MANAGER
# =========================================================

class RaftWorldManager:
    @staticmethod
    def get_base_save_dir():
        appdata = os.getenv("LOCALAPPDATA", "")
        if not appdata:
            appdata = os.path.expandvars(r"%USERPROFILE%\AppData\Local")
        locallow = os.path.join(os.path.dirname(appdata), "LocalLow")
        base = os.path.join(locallow, "Redbeet Interactive", "Raft", "User")
        return base

    @staticmethod
    def get_user_folders():
        base = RaftWorldManager.get_base_save_dir()
        if not os.path.exists(base):
            return []
        users = []
        for name in os.listdir(base):
            full = os.path.join(base, name)
            if os.path.isdir(full) and name.startswith("User_"):
                users.append(name)
        return users

    @staticmethod
    def get_worlds_for_user(user_folder_name):
        base = RaftWorldManager.get_base_save_dir()
        world_dir = os.path.join(base, user_folder_name, "World")
        if not os.path.exists(world_dir):
            return []
        worlds = []
        for w in os.listdir(world_dir):
            full_w = os.path.join(world_dir, w)
            if os.path.isdir(full_w) and w != "OldSaveSystem-Backup":
                worlds.append(w)
        return worlds

    @staticmethod
    def get_world_path(user_folder_name, world_name):
        base = RaftWorldManager.get_base_save_dir()
        return os.path.join(base, user_folder_name, "World", world_name)

    @staticmethod
    def get_dir_size(dir_path):
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total += os.path.getsize(fp)
        except Exception:
            pass
        return total

    @staticmethod
    def get_all_saves_in_world(world_path):
        """Returns list of timestamp directories inside world sorted newest first."""
        if not os.path.exists(world_path):
            return []
        saves = []
        world_name = os.path.basename(os.path.normpath(world_path))
        for item in os.listdir(world_path):
            p = os.path.join(world_path, item)
            # Skip non-directories, hidden folders (.git, etc.)
            if not os.path.isdir(p) or item.startswith("."):
                continue
            # Skip system folders, backup folders, or the base world-named config folder itself
            if item in ["backups", "OldSaveSystem-Backup"] or item.lower() == world_name.lower():
                continue
            # Skip folders containing sync metadata (sync_meta.json / sync.meta)
            if os.path.exists(os.path.join(p, "sync_meta.json")) or os.path.exists(os.path.join(p, "sync.meta")):
                continue

            mtime = os.path.getmtime(p)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            is_latest = item.lower().endswith("-latest") or "latest" in item.lower()
            size_bytes = RaftWorldManager.get_dir_size(p)
            size_kb = size_bytes / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
            saves.append({
                "name": item,
                "is_latest": is_latest,
                "mtime": mtime,
                "mtime_str": mtime_str,
                "size_bytes": size_bytes,
                "size_str": size_str,
                "path": p
            })
        # Sort latest first, then by modification time
        saves.sort(key=lambda x: (not x["is_latest"], -x["mtime"]))
        return saves

    @staticmethod
    def clean_old_saves(world_path, specific_save_names=None):
        """Deletes old autosave folders, preserving active '-Latest' and world config/meta folders."""
        if not os.path.exists(world_path):
            return 0, 0

        world_name = os.path.basename(os.path.normpath(world_path))
        saves = RaftWorldManager.get_all_saves_in_world(world_path)
        deleted_count = 0
        freed_bytes = 0

        for s in saves:
            if s["is_latest"]:
                continue  # Never delete active -Latest save
            if s["name"].lower() == world_name.lower():
                continue  # Protect world config folder
            if os.path.exists(os.path.join(s["path"], "sync_meta.json")) or os.path.exists(os.path.join(s["path"], "sync.meta")):
                continue

            if specific_save_names is not None and s["name"] not in specific_save_names:
                continue

            try:
                freed_bytes += s["size_bytes"]
                shutil.rmtree(s["path"])
                deleted_count += 1
            except Exception:
                pass

        return deleted_count, freed_bytes

    @staticmethod
    def get_latest_save_info(world_path):
        saves = RaftWorldManager.get_all_saves_in_world(world_path)
        if not saves:
            for f in os.listdir(world_path) if os.path.exists(world_path) else []:
                if f.endswith(".rgd"):
                    return world_path, "Root", os.path.join(world_path, f)
            return None, None, None

        latest_candidate = saves[0]["path"]
        folder_name = saves[0]["name"]
        rgd_file = None
        for f in os.listdir(latest_candidate):
            if f.endswith(".rgd"):
                rgd_file = os.path.join(latest_candidate, f)
                break
        return latest_candidate, folder_name, rgd_file

    @staticmethod
    def create_backup(world_path, backup_root_dir):
        if not os.path.exists(world_path):
            return False, "World folder tidak ditemukan."

        os.makedirs(backup_root_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        world_name = os.path.basename(os.path.normpath(world_path))
        dest_backup = os.path.join(backup_root_dir, f"{world_name}_{timestamp}")

        try:
            def ignore_patterns(path, names):
                return [n for n in names if n in [".git", "backups", world_name]]
            shutil.copytree(world_path, dest_backup, ignore=ignore_patterns)
            return True, dest_backup
        except Exception as e:
            return False, str(e)

    @staticmethod
    def sync_to_repo(world_path, repo_path, world_name):
        latest_dir, latest_name, rgd_path = RaftWorldManager.get_latest_save_info(world_path)
        if not latest_dir or not os.path.exists(latest_dir):
            return False, "Tidak ditemukan save '-Latest' atau .rgd di world lokal."

        dest_repo_world = os.path.join(repo_path, world_name)
        os.makedirs(dest_repo_world, exist_ok=True)

        try:
            # 1. Bersihkan file lama di folder repo world agar hanya save Latest murni yang masuk ke GitHub
            for item in os.listdir(dest_repo_world):
                p = os.path.join(dest_repo_world, item)
                if os.path.isfile(p):
                    os.remove(p)
                elif os.path.isdir(p) and item != ".git":
                    shutil.rmtree(p)

            # 2. Salin HANYA file save dari folder '-Latest' aktif
            for item in os.listdir(latest_dir):
                s = os.path.join(latest_dir, item)
                d = os.path.join(dest_repo_world, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)

            meta = {
                "world_name": world_name,
                "latest_folder_name": latest_name,
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(os.path.join(dest_repo_world, "sync_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return True, f"Save dari '{latest_name}' (Latest Only) berhasil disalin ke folder repo."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def sync_from_repo(repo_path, world_path, world_name):
        repo_world_dir = os.path.join(repo_path, world_name)
        if not os.path.exists(repo_world_dir):
            return False, f"Folder world '{world_name}' belum ada di repository."

        os.makedirs(world_path, exist_ok=True)

        for item in os.listdir(world_path):
            full_item = os.path.join(world_path, item)
            if os.path.isdir(full_item) and item.endswith("-Latest"):
                clean_name = item[:-7]
                new_path = os.path.join(world_path, clean_name)
                try:
                    if not os.path.exists(new_path):
                        os.rename(full_item, new_path)
                except Exception:
                    pass

        now_ts = datetime.now().strftime("%Y.%m.%d-%H.%M-Latest")
        target_latest_dir = os.path.join(world_path, now_ts)
        os.makedirs(target_latest_dir, exist_ok=True)

        try:
            copied_count = 0
            for item in os.listdir(repo_world_dir):
                if item == "sync_meta.json":
                    continue
                s = os.path.join(repo_world_dir, item)
                d = os.path.join(target_latest_dir, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
                    copied_count += 1

            if copied_count == 0:
                return False, "Tidak ada file save (.rgd) di folder repository."

            return True, f"World terbaru berhasil dipasang ke folder '{now_ts}'!"
        except Exception as e:
            return False, str(e)


# =========================================================
# GIT ENGINE
# =========================================================

class GitEngine:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir

    def run(self, args):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo
            )
            return {
                "success": result.returncode == 0,
                "code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except FileNotFoundError:
            return {"success": False, "code": -1, "stdout": "", "stderr": "Git tidak ditemukan di Windows PATH."}
        except Exception as e:
            return {"success": False, "code": -1, "stdout": "", "stderr": str(e)}

    def is_valid_repo(self):
        if not os.path.exists(self.repo_dir):
            return False
        res = self.run(["rev-parse", "--is-inside-work-tree"])
        return res["success"] and res["stdout"] == "true"

    def clone_or_init(self, remote_url, branch="master"):
        if not os.path.exists(self.repo_dir):
            os.makedirs(self.repo_dir, exist_ok=True)

        if not self.is_valid_repo():
            if remote_url:
                parent = os.path.dirname(self.repo_dir)
                folder_name = os.path.basename(self.repo_dir)
                try:
                    res = subprocess.run(
                        ["git", "clone", "-b", branch, remote_url, folder_name],
                        cwd=parent,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace"
                    )
                    if res.returncode == 0:
                        return True, "Repository berhasil di-clone."
                except Exception:
                    pass

            res = self.run(["init"])
            if not res["success"]:
                return False, res["stderr"]
            if remote_url:
                self.run(["remote", "add", "origin", remote_url])
            return True, "Git repository berhasil diinisialisasi."
        return True, "Repository valid."

    def resolve_conflicts_theirs(self):
        """Resolves merge conflicts automatically by accepting remote changes."""
        self.run(["checkout", "--theirs", "."])
        self.run(["add", "."])
        return self.run(["commit", "-m", "Auto-resolved save conflict with remote"])

    def pull(self, branch="master"):
        st = self.status()
        if st["stdout"]:
            self.stash()

        res = self.run(["pull", "--rebase=false", "--allow-unrelated-histories", "origin", branch])
        if not res["success"]:
            err_lower = res["stderr"].lower()
            if "conflict" in err_lower or "automatic merge failed" in err_lower:
                self.resolve_conflicts_theirs()
                return {"success": True, "code": 0, "stdout": "✓ Konflik terselesaikan otomatis.", "stderr": ""}

            if "unstaged" in err_lower or "stash" in err_lower or "rebase" in err_lower or "unrelated" in err_lower:
                self.stash()
                res = self.run(["pull", "--rebase=false", "--allow-unrelated-histories", "-X", "theirs", "origin", branch])
                if not res["success"] and ("conflict" in res["stderr"].lower() or "merge failed" in res["stderr"].lower()):
                    self.resolve_conflicts_theirs()
                    return {"success": True, "code": 0, "stdout": "✓ Konflik terselesaikan otomatis.", "stderr": ""}
        return res

    def status(self):
        return self.run(["status", "--short"])

    def add_all(self):
        return self.run(["add", "."])

    def commit(self, message):
        return self.run(["commit", "-m", message])

    def push(self, branch="master"):
        res = self.run(["push", "origin", branch])
        if not res["success"]:
            err_lower = res["stderr"].lower()
            if "rejected" in err_lower or "non-fast-forward" in err_lower or "behind" in err_lower or "unrelated" in err_lower:
                # Auto-pull and merge diverged changes
                self.run(["pull", "--no-rebase", "--allow-unrelated-histories", "-X", "theirs", "origin", branch])
                if "conflict" in err_lower or "merge failed" in err_lower:
                    self.resolve_conflicts_theirs()
                # Retry push
                res = self.run(["push", "origin", branch])
                # If still rejected, force push so latest save progress is safely updated
                if not res["success"] and ("rejected" in res["stderr"].lower() or "non-fast-forward" in res["stderr"].lower()):
                    res = self.run(["push", "--force", "origin", branch])
        return res


# =========================================================
# AUTHENTIC SA-MP 0.3.7 STYLE CLIENT GUI
# =========================================================

class SampRaftClient:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION} - Author: {APP_AUTHOR}")
        self.root.geometry("960x680")
        self.root.minsize(880, 580)
        self.root.configure(bg="#f0f0f0")

        self.config = load_config()
        self.is_playing = False
        self.steam_running = False
        self.current_theme = self.config.get("theme", "light")
        self._themed_widgets = []  # List of (widget, attr, theme_key) tuples

        # Load App Icon if available (.ico)
        for icon_name in ["app_icon.ico", "icon.ico", "raft.ico"]:
            icon_found = False
            paths_to_check = []
            if hasattr(sys, '_MEIPASS'):
                paths_to_check.append(os.path.join(sys._MEIPASS, icon_name))
            if getattr(sys, 'frozen', False):
                paths_to_check.append(os.path.join(os.path.dirname(sys.executable), icon_name))
            paths_to_check.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), icon_name))

            for ip in paths_to_check:
                if os.path.exists(ip):
                    try:
                        self.root.iconbitmap(ip)
                        icon_found = True
                        break
                    except Exception:
                        pass
            if icon_found:
                break

        self.setup_menu()
        self.build_ui()
        self.load_data()

        # Apply saved theme
        self.apply_theme(self.current_theme, save=False)

        # Check Steam status
        self.check_steam_status()

        # Global Keyboard Shortcuts
        self.root.bind("<F5>", lambda e: self.refresh_worlds())
        self.root.bind("<F9>", lambda e: self.start_sync_and_play())
        self.root.bind("<Control-l>", lambda e: self.clear_log())
        self.root.bind("<Control-L>", lambda e: self.clear_log())
        self.root.bind("<Control-u>", lambda e: self.check_updates_gui(manual=True))
        self.root.bind("<Control-U>", lambda e: self.check_updates_gui(manual=True))

        # Check for updates in background after launch
        self.root.after(3500, lambda: self.check_updates_gui(manual=False))

    # =====================================================
    # TOP CLASSIC MENU BAR
    # =====================================================

    def setup_menu(self):
        menubar = tk.Menu(self.root)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Connect (Sync & Play)", accelerator="F9", command=self.start_sync_and_play)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Clear Activity Log", accelerator="Ctrl+L", command=self.clear_log)
        edit_menu.add_command(label="Copy All Logs to Clipboard", command=self.copy_log)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh World List", accelerator="F5", command=self.refresh_worlds)
        view_menu.add_command(label="Open World Folder", command=self.open_world_folder)
        view_menu.add_separator()
        view_menu.add_command(label="Clean Storage (Hapus Save Lama)", command=self.open_clean_storage_dialog)
        view_menu.add_separator()

        # Theme submenu
        theme_menu = tk.Menu(view_menu, tearoff=0)
        self.theme_var = tk.StringVar(value=self.config.get("theme", "light"))
        theme_menu.add_radiobutton(label="☀️  Light",  variable=self.theme_var, value="light",  command=lambda: self.apply_theme("light"))
        theme_menu.add_radiobutton(label="🌙  Dark",   variable=self.theme_var, value="dark",   command=lambda: self.apply_theme("dark"))
        theme_menu.add_radiobutton(label="💻  System", variable=self.theme_var, value="system", command=lambda: self.apply_theme("system"))
        view_menu.add_cascade(label="🎨 Theme", menu=theme_menu)

        menubar.add_cascade(label="View", menu=view_menu)

        # Git
        git_menu = tk.Menu(menubar, tearoff=0)
        git_menu.add_command(label="Git Pull (Download latest)", command=self.manual_pull)
        git_menu.add_command(label="Git Push (Upload save)", command=self.manual_push)
        git_menu.add_command(label="Init / Clone Repo", command=self.init_or_clone_repo)
        git_menu.add_command(label="Test Git Status", command=self.test_git)
        menubar.add_cascade(label="Git Sync", menu=git_menu)

        # Steam
        steam_menu = tk.Menu(menubar, tearoff=0)
        steam_menu.add_command(label="Launch Steam", command=self.launch_steam_app)
        menubar.add_cascade(label="Steam", menu=steam_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="🔍 Check for Updates", accelerator="Ctrl+U", command=lambda: self.check_updates_gui(manual=True))
        help_menu.add_separator()
        help_menu.add_command(label=f"About {APP_NAME}", command=lambda: messagebox.showinfo("About", f"{APP_NAME} {APP_VERSION}\nAuthor: {APP_AUTHOR}\n\nDedicated multiplayer turn-based world synchronizer for Raft.\n\nKey Shortcuts:\n• F5: Refresh World List\n• F9: Connect (Sync & Play)\n• Ctrl+L: Clear Log\n• Ctrl+U: Check for Updates"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    # =====================================================
    # THEME MANAGEMENT
    # =====================================================

    def get_system_theme(self):
        """Detects Windows system theme (dark/light) via registry."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val == 1 else "dark"
        except Exception:
            return "light"

    def apply_theme(self, theme_name, save=True):
        """Applies Light, Dark, or System theme to the entire UI."""
        if theme_name == "system":
            resolved = self.get_system_theme()
        else:
            resolved = theme_name

        t = THEMES.get(resolved, THEMES["light"])
        self.current_theme = theme_name

        # --- ttk Style (Treeview, Notebook) ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=t["panel_bg"],
                        foreground=t["label_fg"],
                        fieldbackground=t["panel_bg"],
                        rowheight=22)
        style.configure("Treeview.Heading",
                        background=t["header_bg"],
                        foreground=t["header_fg"],
                        relief="flat")
        style.map("Treeview",
                  background=[("selected", "#1565c0" if resolved == "dark" else "#0078d4")],
                  foreground=[("selected", "#ffffff")])
        style.configure("TNotebook",
                        background=t["root_bg"],
                        tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab",
                        background=t["btn_bg"],
                        foreground=t["btn_fg"],
                        padding=[8, 4])
        style.map("TNotebook.Tab",
                  background=[("selected", t["tab_bg"])],
                  foreground=[("selected", t["tab_fg"])])

        # --- Root & main containers ---
        self.root.configure(bg=t["root_bg"])
        self.toolbar.configure(bg=t["toolbar_bg"])
        self.main_paned.configure(bg=t["sash_bg"])
        self.left_frame.configure(bg=t["left_frame_bg"])
        self.right_frame.configure(bg=t["right_frame_bg"])
        self.bottom_tabs_frame.configure(bg=t["root_bg"])

        # --- Toolbar buttons ---
        for btn in self._toolbar_btns:
            btn.configure(bg=t["btn_bg"], fg=t["btn_fg"], activebackground=t["header_bg"])
        self.btn_steam.configure(bg=t["btn_bg"], fg=t["btn_fg"], activebackground=t["header_bg"])
        self.lbl_name.configure(bg=t["toolbar_bg"], fg=t["toolbar_fg"])

        # --- Right panel headers and sub-frames ---
        self.lbl_player_header.configure(bg=t["header_bg"], fg=t["header_fg"])
        self.lbl_rule_header.configure(bg=t["header_bg"], fg=t["header_fg"])
        self.save_box_frame.configure(bg=t["panel_bg"])
        self.rule_box_frame.configure(bg=t["panel_bg"])

        # --- Tab frames ---
        self.tab_info.configure(bg=t["tab_bg"])
        self.tab_settings.configure(bg=t["tab_bg"])
        self.tab_log.configure(bg=t["tab_bg"])
        self.info_grid.configure(bg=t["tab_bg"])

        # --- Info labels ---
        for lbl in [self.lbl_info_world, self.lbl_info_latest, self.lbl_info_steam, self.lbl_info_git]:
            lbl.configure(bg=t["tab_bg"], fg=t["label_fg"])

        # --- Settings tab frames and labels ---
        for frame in [self.row1, self.row2, self.row3]:
            frame.configure(bg=t["tab_bg"])
        for lbl in [self.lbl_exe, self.lbl_repo, self.lbl_branch, self.lbl_url]:
            lbl.configure(bg=t["tab_bg"], fg=t["label_fg"])

        # --- Entries ---
        for entry in [self.entry_exe, self.entry_repo, self.entry_branch, self.entry_url]:
            entry.configure(bg=t["entry_bg"], fg=t["entry_fg"],
                            insertbackground=t["entry_fg"],
                            disabledbackground=t["entry_bg"])

        # --- Log text box and toolbar ---
        if hasattr(self, "log_toolbar"):
            self.log_toolbar.configure(bg=t["tab_bg"])
            self.btn_clear_log.configure(bg=t["btn_bg"], fg=t["btn_fg"])
            self.btn_copy_log.configure(bg=t["btn_bg"], fg=t["btn_fg"])
            self.lbl_log_hint.configure(bg=t["tab_bg"], fg=t["label_fg"])
        self.log_text.configure(bg=t["log_bg"], fg=t["log_fg"])

        # --- Status bar ---
        self.statusbar.configure(bg=t["statusbar_bg"], fg=t["statusbar_fg"])

        # --- Update menu radio check ---
        if hasattr(self, "theme_var"):
            self.theme_var.set(theme_name)

        # Save to config
        if save:
            self.config["theme"] = theme_name
            save_config(self.config)

    # =====================================================
    # UI CONSTRUCTION
    # =====================================================

    def build_ui(self):
        # 1. TOP TOOLBAR STRIP
        self.toolbar = tk.Frame(self.root, bg="#f5f5f5", bd=1, relief="raised", height=38)
        self.toolbar.pack(fill="x", side="top", padx=2, pady=2)

        # Connect / Play Button (Green Icon style)
        self.btn_connect = tk.Button(self.toolbar, text="▶ Connect", font=("Segoe UI", 9, "bold"), bg="#4caf50", fg="#ffffff", activebackground="#43a047", relief="groove", padx=8, pady=2, command=self.start_sync_and_play)
        self.btn_connect.pack(side="left", padx=(4, 2), pady=3)

        # Reload / Refresh
        btn_refresh = tk.Button(self.toolbar, text="🔄 Refresh", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.refresh_worlds)
        btn_refresh.pack(side="left", padx=2, pady=3)

        # Git Pull
        btn_pull = tk.Button(self.toolbar, text="⬇️ Pull", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.manual_pull)
        btn_pull.pack(side="left", padx=2, pady=3)

        # Git Push
        btn_push = tk.Button(self.toolbar, text="⬆️ Push", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.manual_push)
        btn_push.pack(side="left", padx=2, pady=3)

        # Open folder
        btn_open = tk.Button(self.toolbar, text="📂 Folder", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.open_world_folder)
        btn_open.pack(side="left", padx=2, pady=3)

        # Clean Storage Button
        btn_clean = tk.Button(self.toolbar, text="🧹 Clean Storage", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.open_clean_storage_dialog)
        btn_clean.pack(side="left", padx=2, pady=3)

        # Steam Action
        self.btn_steam = tk.Button(self.toolbar, text="🎮 Steam", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.launch_steam_app)
        self.btn_steam.pack(side="left", padx=2, pady=3)

        # Keep refs for theming
        self._toolbar_btns = [btn_refresh, btn_pull, btn_push, btn_open, btn_clean]

        # Separator
        ttk.Separator(self.toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        # Name / Steam Account Selector
        self.lbl_name = tk.Label(self.toolbar, text="Name:", font=("Segoe UI", 9, "bold"), bg="#f5f5f5")
        self.lbl_name.pack(side="left", padx=(2, 4))
        self.user_var = tk.StringVar()
        self.combo_user = ttk.Combobox(self.toolbar, textvariable=self.user_var, state="readonly", font=("Segoe UI", 9), width=28)
        self.combo_user.pack(side="left", padx=(0, 8), pady=4)
        self.combo_user.bind("<<ComboboxSelected>>", self.on_user_changed)

        # Top Right Raft Badge
        badge_frame = tk.Frame(self.toolbar, bg="#ff6600", padx=10, pady=2)
        badge_frame.pack(side="right", padx=6, pady=3)
        tk.Label(badge_frame, text=f"RAFT {APP_VERSION}", font=("Segoe UI", 9, "bold italic"), fg="#ffffff", bg="#ff6600").pack()

        # 2. MAIN CENTER AREA (SPLIT PANE: LEFT SERVER LIST, RIGHT DETAILS)
        self.main_paned = tk.PanedWindow(self.root, orient="horizontal", bg="#d9d9d9", sashrelief="ridge", sashwidth=4)
        self.main_paned.pack(fill="both", expand=True, padx=4, pady=2)

        # --- LEFT PANEL: WORLD BROWSER ---
        self.left_frame = tk.Frame(self.main_paned, bg="#ffffff")
        self.main_paned.add(self.left_frame, minsize=480)

        # Treeview (World List)
        tree_scroll_y = tk.Scrollbar(self.left_frame, orient="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x = tk.Scrollbar(self.left_frame, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        columns = ("world_name", "latest_save", "saves_count", "status", "folder_path")
        self.tree = ttk.Treeview(self.left_frame, columns=columns, show="headings", selectmode="browse", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        # Setup Columns
        self.tree.heading("world_name", text="HostName / World Name", anchor="w")
        self.tree.heading("latest_save", text="Latest Save Active", anchor="w")
        self.tree.heading("saves_count", text="Saves", anchor="center")
        self.tree.heading("status", text="Cloud Status", anchor="center")
        self.tree.heading("folder_path", text="Directory Path", anchor="w")

        self.tree.column("world_name", width=180, minwidth=140)
        self.tree.column("latest_save", width=190, minwidth=150)
        self.tree.column("saves_count", width=60, minwidth=50, anchor="center")
        self.tree.column("status", width=90, minwidth=80, anchor="center")
        self.tree.column("folder_path", width=220, minwidth=150)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.start_sync_and_play())

        # --- RIGHT PANEL: DETAILS ---
        self.right_frame = tk.Frame(self.main_paned, bg="#f0f0f0")
        self.main_paned.add(self.right_frame, minsize=260)

        # Top Right Box: Save Timestamps
        self.lbl_player_header = tk.Label(self.right_frame, text="Save Timestamps / History", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", anchor="w", padx=6, pady=2)
        self.lbl_player_header.pack(fill="x")

        self.save_box_frame = tk.Frame(self.right_frame, bg="#ffffff")
        self.save_box_frame.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        save_scroll = tk.Scrollbar(self.save_box_frame, orient="vertical")
        save_scroll.pack(side="right", fill="y")

        self.save_tree = ttk.Treeview(self.save_box_frame, columns=("timestamp", "type"), show="headings", selectmode="browse", yscrollcommand=save_scroll.set)
        save_scroll.config(command=self.save_tree.yview)

        self.save_tree.heading("timestamp", text="Save Timestamp", anchor="w")
        self.save_tree.heading("type", text="Type", anchor="center")
        self.save_tree.column("timestamp", width=160, minwidth=120)
        self.save_tree.column("type", width=70, minwidth=60, anchor="center")
        self.save_tree.pack(fill="both", expand=True)

        # Bottom Right Box: Properties
        self.lbl_rule_header = tk.Label(self.right_frame, text="World & Git Properties", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", anchor="w", padx=6, pady=2)
        self.lbl_rule_header.pack(fill="x")

        self.rule_box_frame = tk.Frame(self.right_frame, bg="#ffffff")
        self.rule_box_frame.pack(fill="both", expand=True, padx=2, pady=0)

        rule_scroll = tk.Scrollbar(self.rule_box_frame, orient="vertical")
        rule_scroll.pack(side="right", fill="y")

        self.rule_tree = ttk.Treeview(self.rule_box_frame, columns=("property", "value"), show="headings", selectmode="browse", yscrollcommand=rule_scroll.set)
        rule_scroll.config(command=self.rule_tree.yview)

        self.rule_tree.heading("property", text="Property", anchor="w")
        self.rule_tree.heading("value", text="Value", anchor="w")
        self.rule_tree.column("property", width=100, minwidth=80)
        self.rule_tree.column("value", width=160, minwidth=120)
        self.rule_tree.pack(fill="both", expand=True)

        # 3. BOTTOM DETAIL NOTEBOOK TABS
        self.bottom_tabs_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.bottom_tabs_frame.pack(fill="x", padx=4, pady=(2, 0))

        self.notebook = ttk.Notebook(self.bottom_tabs_frame)
        self.notebook.pack(fill="x")

        # TAB 1: Server Info / Quick Status
        self.tab_info = tk.Frame(self.notebook, bg="#f5f5f5", padx=8, pady=6)
        self.notebook.add(self.tab_info, text=" Server Info ")

        self.info_grid = tk.Frame(self.tab_info, bg="#f5f5f5")
        self.info_grid.pack(fill="x")

        self.lbl_info_world = tk.Label(self.info_grid, text="World: None", font=("Segoe UI", 9, "bold"), bg="#f5f5f5", anchor="w")
        self.lbl_info_world.grid(row=0, column=0, sticky="w", padx=(0, 20))

        self.lbl_info_latest = tk.Label(self.info_grid, text="Latest Save: None", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_latest.grid(row=0, column=1, sticky="w", padx=(0, 20))

        self.lbl_info_steam = tk.Label(self.info_grid, text="Steam: Checking...", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_steam.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=(4, 0))

        self.lbl_info_git = tk.Label(self.info_grid, text="Git: origin/master", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_git.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(4, 0))

        # TAB 2: Quick Settings / Paths
        self.tab_settings = tk.Frame(self.notebook, bg="#f5f5f5", padx=8, pady=6)
        self.notebook.add(self.tab_settings, text=" Configuration & Paths ")

        # Row 1: Raft.exe
        self.row1 = tk.Frame(self.tab_settings, bg="#f5f5f5")
        self.row1.pack(fill="x", pady=2)
        self.lbl_exe = tk.Label(self.row1, text="Raft.exe:", width=12, anchor="w", bg="#f5f5f5")
        self.lbl_exe.pack(side="left")
        self.raft_exe_var = tk.StringVar()
        self.entry_exe = tk.Entry(self.row1, textvariable=self.raft_exe_var, bg="#fff")
        self.entry_exe.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(self.row1, text="Browse", padx=6, command=self.browse_raft_exe).pack(side="left")

        # Row 2: Local Repo & Branch
        self.row2 = tk.Frame(self.tab_settings, bg="#f5f5f5")
        self.row2.pack(fill="x", pady=2)
        self.lbl_repo = tk.Label(self.row2, text="Repo Dir:", width=12, anchor="w", bg="#f5f5f5")
        self.lbl_repo.pack(side="left")
        self.repo_path_var = tk.StringVar()
        self.entry_repo = tk.Entry(self.row2, textvariable=self.repo_path_var, bg="#fff")
        self.entry_repo.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(self.row2, text="Browse", padx=6, command=self.browse_repo_dir).pack(side="left")

        self.lbl_branch = tk.Label(self.row2, text="Branch:", bg="#f5f5f5")
        self.lbl_branch.pack(side="left", padx=(8, 2))
        self.branch_var = tk.StringVar(value="master")
        self.entry_branch = tk.Entry(self.row2, textvariable=self.branch_var, width=10, bg="#fff")
        self.entry_branch.pack(side="left", padx=2)

        # Row 3: Remote URL & Save Config
        self.row3 = tk.Frame(self.tab_settings, bg="#f5f5f5")
        self.row3.pack(fill="x", pady=2)
        self.lbl_url = tk.Label(self.row3, text="Git URL:", width=12, anchor="w", bg="#f5f5f5")
        self.lbl_url.pack(side="left")
        self.remote_url_var = tk.StringVar()
        self.entry_url = tk.Entry(self.row3, textvariable=self.remote_url_var, bg="#fff")
        self.entry_url.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(self.row3, text="💾 Save Config", bg="#e0e0e0", padx=8, command=self.save_current_settings).pack(side="left", padx=2)

        # TAB 3: Activity Log (Terminal)
        self.tab_log = tk.Frame(self.notebook, bg="#f5f5f5", padx=6, pady=4)
        self.notebook.add(self.tab_log, text=" Activity Log ")

        self.log_toolbar = tk.Frame(self.tab_log, bg="#f5f5f5")
        self.log_toolbar.pack(fill="x", side="top", pady=(0, 4))

        self.btn_clear_log = tk.Button(self.log_toolbar, text="🗑️ Clear Log", font=("Segoe UI", 8), bg="#e0e0e0", relief="groove", padx=6, pady=1, command=self.clear_log)
        self.btn_clear_log.pack(side="left", padx=(0, 4))

        self.btn_copy_log = tk.Button(self.log_toolbar, text="📋 Copy Log", font=("Segoe UI", 8), bg="#e0e0e0", relief="groove", padx=6, pady=1, command=self.copy_log)
        self.btn_copy_log.pack(side="left", padx=(0, 4))

        self.lbl_log_hint = tk.Label(self.log_toolbar, text="Shortcuts: [F5] Refresh  |  [Ctrl+L] Clear Log  |  [Ctrl+U] Update Check", font=("Segoe UI", 8), fg="#777777", bg="#f5f5f5")
        self.lbl_log_hint.pack(side="right")

        log_scroll = tk.Scrollbar(self.tab_log, orient="vertical")
        log_scroll.pack(side="right", fill="y")
        self.log_text = tk.Text(self.tab_log, height=5, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff", yscrollcommand=log_scroll.set)
        self.log_text.pack(fill="both", expand=True)
        log_scroll.config(command=self.log_text.yview)

        # 4. BOTTOM STATUS BAR
        self.statusbar = tk.Label(self.root, text="Ready. Select a world and click Connect.", font=("Segoe UI", 8), bd=1, relief="sunken", anchor="w", padx=6, pady=2, bg="#e8e8e8")
        self.statusbar.pack(fill="x", side="bottom")

    # =====================================================
    # DATA LOADING & TREEVIEW POPULATION
    # =====================================================

    def load_data(self):
        self.raft_exe_var.set(self.config.get("raft_exe", ""))
        self.repo_path_var.set(self.config.get("repo_path", ""))
        self.remote_url_var.set(self.config.get("remote_url", ""))
        self.branch_var.set(self.config.get("branch", "master"))

        # Populate users
        users = RaftWorldManager.get_user_folders()
        steam_accounts = SteamManager.get_accounts()

        user_options = []
        for u in users:
            steamid_part = u.replace("User_", "")
            display_name = u
            for acc in steam_accounts:
                if acc.get("steamid") == steamid_part:
                    display_name = f"{acc.get('persona_name', u)} ({u})"
                    break
            user_options.append(display_name)

        self.combo_user["values"] = user_options if user_options else ["(Tidak ada folder user)"]

        saved_user = self.config.get("steam_user_id", "")
        selected_idx = 0
        if saved_user:
            for idx, opt in enumerate(user_options):
                if saved_user in opt:
                    selected_idx = idx
                    break
        if user_options:
            self.combo_user.current(selected_idx)

        self.refresh_worlds()

    def get_selected_player_name(self):
        val = self.user_var.get()
        if not val or val.startswith("("):
            return "Player"
        # Extract persona name if formatted as "Persona (User_...)"
        m = re.match(r'^(.*?)\s*\(User_\d+\)$', val)
        if m:
            return m.group(1).strip()
        return val.strip()

    def get_selected_user_folder(self):
        val = self.user_var.get()
        if not val or val.startswith("("):
            return None
        m = re.search(r'(User_\d+)', val)
        if m:
            return m.group(1)
        return val

    def on_user_changed(self, event):
        self.refresh_worlds()
        self.save_current_settings(silent=True)

    def refresh_worlds(self):
        """Scans worlds and populates the main Treeview table."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        user_folder = self.get_selected_user_folder()
        if not user_folder:
            self.statusbar.config(text="Status: User folder not found.")
            return

        worlds = RaftWorldManager.get_worlds_for_user(user_folder)
        saved_world = self.config.get("selected_world", "")
        item_to_select = None

        for w in worlds:
            world_path = RaftWorldManager.get_world_path(user_folder, w)
            saves = RaftWorldManager.get_all_saves_in_world(world_path)
            latest_name = "-"
            for s in saves:
                if s["is_latest"]:
                    latest_name = s["name"]
                    break
            if latest_name == "-" and saves:
                latest_name = saves[0]["name"]

            count_str = f"{len(saves)}"
            status_str = "🟢 Ready" if latest_name != "-" else "⚠️ Empty"

            row_id = self.tree.insert("", "end", values=(w, latest_name, count_str, status_str, world_path))

            if w == saved_world:
                item_to_select = row_id

        children = self.tree.get_children()
        if children:
            if not item_to_select:
                item_to_select = children[0]
            self.tree.selection_set(item_to_select)
            self.tree.focus(item_to_select)
            self.on_tree_select(None)
            player = self.get_selected_player_name()
            self.statusbar.config(text=f"Status: {len(children)} World(s) detected. Player: {player} | Steam: {'Online' if self.steam_running else 'Offline'} | Author: {APP_AUTHOR} ({APP_VERSION})")
        else:
            self.statusbar.config(text=f"Status: No worlds found in selected user profile. | Author: {APP_AUTHOR} ({APP_VERSION})")
            self.clear_details()

    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        vals = self.tree.item(selected[0])["values"]
        if not vals:
            return

        world_name = vals[0]
        latest_name = vals[1]
        world_path = vals[4]

        self.config["selected_world"] = world_name
        self.lbl_info_world.config(text=f"World: {world_name}")
        self.lbl_info_latest.config(text=f"Latest Save: {latest_name}")

        # Update right top table: Save Timestamps
        for item in self.save_tree.get_children():
            self.save_tree.delete(item)

        saves = RaftWorldManager.get_all_saves_in_world(world_path)
        for s in saves:
            type_label = "Latest" if s["is_latest"] else "AutoSave"
            self.save_tree.insert("", "end", values=(s["name"], type_label))

        # Update right bottom table: Properties (Rule-Value)
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)

        user_f = self.get_selected_user_folder() or "-"
        player_name = self.get_selected_player_name()
        branch = self.branch_var.get().strip() or "master"
        _, _, rgd = RaftWorldManager.get_latest_save_info(world_path)
        rgd_name = os.path.basename(rgd) if rgd else "-"

        props = [
            ("author", APP_AUTHOR),
            ("version", APP_VERSION),
            ("steam_name", player_name),
            ("world_name", world_name),
            ("steam_user", user_f),
            ("steam_status", "Online" if self.steam_running else "Offline"),
            ("git_branch", branch),
            ("save_file", rgd_name),
            ("total_saves", str(len(saves))),
            ("sync_mode", "Latest Only")
        ]
        for p, v in props:
            self.rule_tree.insert("", "end", values=(p, v))

    def clear_details(self):
        for item in self.save_tree.get_children():
            self.save_tree.delete(item)
        for item in self.rule_tree.get_children():
            self.rule_tree.delete(item)
        self.lbl_info_world.config(text="World: None")
        self.lbl_info_latest.config(text="Latest Save: None")

    # =====================================================
    # LOGGING
    # =====================================================

    def log(self, message):
        def write():
            self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see("end")
            self.statusbar.config(text=f"Status: {message}")
        self.root.after(0, write)

    def clear_log(self):
        """Clears all text in the Activity Log tab."""
        self.log_text.delete("1.0", "end")
        self.log("Activity Log telah dibersihkan.")

    def copy_log(self):
        """Copies all text in the Activity Log to clipboard."""
        content = self.log_text.get("1.0", "end-1c").strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.statusbar.config(text="Status: ✓ Activity Log berhasil disalin ke clipboard.")
        else:
            self.statusbar.config(text="Status: Log masih kosong.")

    def run_async(self, func, *args):
        threading.Thread(target=func, args=args, daemon=True).start()

    # =====================================================
    # STEAM MANAGEMENT
    # =====================================================

    def check_steam_status(self):
        self.steam_running = SteamManager.is_running()
        status_text = "🟢 Steam: Online" if self.steam_running else "🔴 Steam: Offline"
        self.lbl_info_steam.config(text=status_text)
        self.btn_steam.config(text="🎮 Steam (Online)" if self.steam_running else "🎮 Steam (Offline)")
        self.root.after(3000, self.check_steam_status)

    def launch_steam_app(self):
        self.log("Membuka Steam...")
        ok, msg = SteamManager.launch_steam()
        if ok:
            self.log(f"✓ {msg}")
        else:
            self.log(f"✗ {msg}")

    # =====================================================
    # SETTINGS & FILE ACTIONS
    # =====================================================

    def locate_raft_exe(self):
        """Displays SA-MP style error alert when Raft.exe is not found and opens file locator."""
        current_path = self.raft_exe_var.get().strip()
        if current_path and os.path.exists(current_path):
            return current_path

        # 1. Show SA-MP style error dialog
        messagebox.showerror(
            "Error",
            f"Raft executable not found.\n({current_path if current_path else 'Not specified'})\n\nPlease locate it now."
        )

        # 2. Open file locator dialog
        chosen = filedialog.askopenfilename(
            title="Please locate your Raft installation (Raft.exe)...",
            filetypes=[
                ("Raft Executable", "Raft.exe"),
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )

        if chosen and os.path.exists(chosen):
            self.raft_exe_var.set(chosen)
            self.save_current_settings(silent=True)
            self.log(f"✓ Raft executable located: {chosen}")
            return chosen

        self.log("⚠️ Pemilihan lokasi Raft.exe dibatalkan.")
        return None

    def browse_raft_exe(self):
        p = filedialog.askopenfilename(
            title="Please locate your Raft installation (Raft.exe)...",
            filetypes=[("Raft Executable", "Raft.exe"), ("Executable", "*.exe"), ("All files", "*.*")]
        )
        if p:
            self.raft_exe_var.set(p)
            self.save_current_settings(silent=True)

    def browse_repo_dir(self):
        p = filedialog.askdirectory(title="Pilih Folder Local Git Repository")
        if p:
            self.repo_path_var.set(p)
            self.save_current_settings(silent=True)

    def open_world_folder(self):
        user_folder = self.get_selected_user_folder()
        world_name = self.config.get("selected_world", "")
        if not user_folder or not world_name:
            messagebox.showwarning("Warning", "Pilih world terlebih dahulu dari tabel.")
            return
        path = RaftWorldManager.get_world_path(user_folder, world_name)
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("World", f"Folder tidak ditemukan: {path}")

    def open_clean_storage_dialog(self):
        """Dedicated Clean Storage Manager modal UI for purging obsolete autosaves."""
        user_folder = self.get_selected_user_folder()
        world_name = self.config.get("selected_world", "")
        if not user_folder or not world_name:
            messagebox.showwarning("Pilih World", "Silakan pilih salah satu world terlebih dahulu dari tabel.")
            return

        world_path = RaftWorldManager.get_world_path(user_folder, world_name)
        if not os.path.exists(world_path):
            messagebox.showwarning("World Tidak Ditemukan", f"Folder world tidak ditemukan:\n{world_path}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Clean Storage Manager - {world_name}")
        dialog.geometry("640x480")
        dialog.minsize(580, 400)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 320
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 240
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Top Header Info Box
        header_frame = tk.Frame(dialog, bg="#f5f5f5", padx=10, pady=8, bd=1, relief="ridge")
        header_frame.pack(fill="x", padx=8, pady=(8, 4))

        lbl_title = tk.Label(
            header_frame,
            text=f"🧹 Pembersih Save Game: {world_name}",
            font=("Segoe UI", 11, "bold"),
            bg="#f5f5f5",
            anchor="w"
        )
        lbl_title.pack(fill="x")

        lbl_subtitle = tk.Label(
            header_frame,
            text="Hapus folder autosave lama yang tidak digunakan untuk menghemat ruang disk. Save '-Latest' aktif akan selalu diproteksi.",
            font=("Segoe UI", 8),
            fg="#555",
            bg="#f5f5f5",
            anchor="w",
            wraplength=580
        )
        lbl_subtitle.pack(fill="x", pady=(2, 0))

        # Status counts
        lbl_stats = tk.Label(
            header_frame,
            text="Memuat data...",
            font=("Segoe UI", 9, "bold"),
            fg="#1565c0",
            bg="#f5f5f5",
            anchor="w"
        )
        lbl_stats.pack(fill="x", pady=(4, 0))

        # Center Treeview Frame
        tree_frame = tk.Frame(dialog)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        tree_scroll_y = tk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x = tk.Scrollbar(tree_frame, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        cols = ("name", "status", "size", "mtime")
        save_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        tree_scroll_y.config(command=save_tree.yview)
        tree_scroll_x.config(command=save_tree.xview)

        save_tree.heading("name", text="Folder Save (Timestamp)", anchor="w")
        save_tree.heading("status", text="Status", anchor="center")
        save_tree.heading("size", text="Ukuran", anchor="center")
        save_tree.heading("mtime", text="Waktu Dibuat", anchor="w")

        save_tree.column("name", width=220, minwidth=180)
        save_tree.column("status", width=140, minwidth=120, anchor="center")
        save_tree.column("size", width=90, minwidth=70, anchor="center")
        save_tree.column("mtime", width=140, minwidth=120)

        # Style tags
        save_tree.tag_configure("latest", background="#e8f5e9", foreground="#1b5e20")
        save_tree.tag_configure("old", background="#ffffff", foreground="#333333")

        save_tree.pack(fill="both", expand=True)

        def reload_saves():
            for it in save_tree.get_children():
                save_tree.delete(it)

            saves = RaftWorldManager.get_all_saves_in_world(world_path)
            old_count = 0
            old_size_bytes = 0

            for s in saves:
                if s["is_latest"]:
                    status_text = "🟢 Active (Latest)"
                    tag = "latest"
                else:
                    status_text = "📁 Old AutoSave"
                    tag = "old"
                    old_count += 1
                    old_size_bytes += s["size_bytes"]

                save_tree.insert("", "end", values=(s["name"], status_text, s["size_str"], s["mtime_str"]), tags=(tag,))

            old_kb = old_size_bytes / 1024
            old_size_str = f"{old_kb:.1f} KB" if old_kb < 1024 else f"{old_kb/1024:.2f} MB"
            lbl_stats.config(
                text=f"Total: {len(saves)} Save | Save Lama: {old_count} folder ({old_size_str} dapat dibersihkan)"
            )
            btn_clean_all.config(text=f"🧹 Bersihkan Semua ({old_count} Save Lama)")
            if old_count == 0:
                btn_clean_all.config(state="disabled")
            else:
                btn_clean_all.config(state="normal")

        def delete_selected():
            selected_items = save_tree.selection()
            if not selected_items:
                messagebox.showwarning("Pilih Save", "Silakan klik/pilih save yang ingin dihapus dari daftar.", parent=dialog)
                return

            to_delete = []
            has_latest = False
            for item in selected_items:
                vals = save_tree.item(item)["values"]
                name = str(vals[0])
                status = str(vals[1])
                if "Latest" in status:
                    has_latest = True
                else:
                    to_delete.append(name)

            if has_latest and not to_delete:
                messagebox.showwarning(
                    "Proteksi Save Aktif",
                    "Save bertanda '🟢 Active (Latest)' tidak dapat dihapus karena merupakan save aktif yang sedang digunakan.",
                    parent=dialog
                )
                return

            if not to_delete:
                return

            confirm = messagebox.askyesno(
                "Konfirmasi Hapus",
                f"Apakah Anda yakin ingin menghapus {len(to_delete)} folder save lama yang dipilih?\n\n"
                f"Daftar: {', '.join(to_delete[:5])}{'...' if len(to_delete) > 5 else ''}",
                parent=dialog
            )
            if confirm:
                count, bytes_freed = RaftWorldManager.clean_old_saves(world_path, specific_save_names=to_delete)
                freed_kb = bytes_freed / 1024
                freed_str = f"{freed_kb:.1f} KB" if freed_kb < 1024 else f"{freed_kb/1024:.2f} MB"
                self.log(f"🧹 Clean Storage: Menghapus {count} save lama dari '{world_name}' ({freed_str} dibebaskan).")
                reload_saves()
                self.refresh_worlds()
                messagebox.showinfo("Selesai", f"Berhasil menghapus {count} folder save ({freed_str} ruang dibebaskan).", parent=dialog)

        def clean_all_old():
            saves = RaftWorldManager.get_all_saves_in_world(world_path)
            old_saves = [s for s in saves if not s["is_latest"]]
            if not old_saves:
                messagebox.showinfo("Bersih", "Tidak ada folder save lama yang perlu dibersihkan.", parent=dialog)
                return

            confirm = messagebox.askyesno(
                "Konfirmasi Bersihkan Semua",
                f"Apakah Anda yakin ingin menghapus SEMUA {len(old_saves)} folder save lama pada world '{world_name}'?\n\n"
                f"✓ Save aktif '-Latest' akan tetap aman dan tidak akan terhapus.",
                parent=dialog
            )
            if confirm:
                count, bytes_freed = RaftWorldManager.clean_old_saves(world_path)
                freed_kb = bytes_freed / 1024
                freed_str = f"{freed_kb:.1f} KB" if freed_kb < 1024 else f"{freed_kb/1024:.2f} MB"
                self.log(f"🧹 Clean Storage: Menghapus semua {count} save lama dari '{world_name}' ({freed_str} dibebaskan).")
                reload_saves()
                self.refresh_worlds()
                messagebox.showinfo("Selesai", f"✓ Semua save lama berhasil dibersihkan!\n{count} folder dihapus ({freed_str} ruang dibebaskan).", parent=dialog)

        # Bottom Buttons Bar
        btn_bar = tk.Frame(dialog, bg="#f5f5f5", padx=8, pady=8, bd=1, relief="ridge")
        btn_bar.pack(fill="x", padx=8, pady=(4, 8))

        btn_del_selected = tk.Button(
            btn_bar,
            text="🗑️ Hapus yang Dipilih",
            font=("Segoe UI", 9),
            bg="#fce4ec",
            fg="#c2185b",
            activebackground="#f8bbd0",
            relief="groove",
            padx=8,
            pady=3,
            command=delete_selected
        )
        btn_del_selected.pack(side="left", padx=2)

        btn_clean_all = tk.Button(
            btn_bar,
            text="🧹 Bersihkan Semua Save Lama",
            font=("Segoe UI", 9, "bold"),
            bg="#ffebee",
            fg="#d32f2f",
            activebackground="#ffcdd2",
            relief="groove",
            padx=10,
            pady=3,
            command=clean_all_old
        )
        btn_clean_all.pack(side="left", padx=6)

        btn_close = tk.Button(
            btn_bar,
            text="Tutup",
            font=("Segoe UI", 9),
            relief="groove",
            padx=12,
            pady=3,
            command=dialog.destroy
        )
        btn_close.pack(side="right", padx=2)

        btn_reload = tk.Button(
            btn_bar,
            text="🔄 Refresh",
            font=("Segoe UI", 9),
            relief="groove",
            padx=8,
            pady=3,
            command=reload_saves
        )
        btn_reload.pack(side="right", padx=4)

        reload_saves()

    def check_updates_gui(self, manual=False):
        """Checks for updates from GitHub Releases and displays update dialog."""
        repo_slug = self.config.get("update_repo", DEFAULT_UPDATE_REPO).strip() or DEFAULT_UPDATE_REPO

        def worker():
            if manual:
                self.log("🔍 Memeriksa pembaruan di GitHub Releases...")

            ok, has_update, tag_name, download_url, notes = UpdateManager.check_for_updates(repo_slug)
            if not ok:
                if manual:
                    self.log(f"⚠️ Gagal memeriksa update: {notes}")
                    messagebox.showwarning("Cek Update", f"Gagal terhubung ke GitHub Releases:\n{notes}")
                return

            if has_update:
                self.log(f"🎉 Update baru ditemukan: {tag_name} (Versi saat ini: {APP_VERSION})")
                self.root.after(0, lambda: self._show_update_available_dialog(tag_name, download_url, notes))
            else:
                if manual:
                    self.log(f"✓ Anda sudah menggunakan versi terbaru ({APP_VERSION}).")
                    messagebox.showinfo("Cek Update", f"Anda sudah menggunakan versi terbaru ({APP_VERSION})!\nTidak ada pembaruan.")

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_available_dialog(self, tag_name, download_url, notes):
        """Displays update available dialog and executes download & replace."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Pembaruan Tersedia! - Raft Launcher")
        dialog.geometry("520x430")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 260
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 215
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        tk.Label(
            dialog,
            text=f"🚀 Versi Baru Tersedia: {tag_name}",
            font=("Segoe UI", 12, "bold"),
            fg="#1565c0"
        ).pack(pady=(15, 4))

        tk.Label(
            dialog,
            text=f"Versi Anda saat ini: {APP_VERSION}  ➔  Versi Baru: {tag_name}",
            font=("Segoe UI", 9),
            fg="#555"
        ).pack(pady=(0, 6))

        if not download_url:
            tk.Label(dialog, text="⚠️ File .exe tidak ditemukan di aset rilis GitHub.", fg="#d32f2f").pack(pady=4)
            tk.Button(dialog, text="Tutup", command=dialog.destroy).pack(pady=8)
            return

        # Progress elements (pack early so they sit above buttons)
        progress_var = tk.DoubleVar()
        progress_frame = tk.Frame(dialog)
        progress_frame.pack(fill="x", padx=20, pady=(0, 2))
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
        lbl_status = tk.Label(progress_frame, text="", font=("Segoe UI", 8), fg="#666")

        # Buttons — pack BEFORE notes so they always visible at bottom
        btn_box = tk.Frame(dialog, pady=8)
        btn_box.pack(fill="x", padx=16, side="bottom")

        btn_update = tk.Button(
            btn_box,
            text="📥 Download & Pasang Update Package",
            font=("Segoe UI", 10, "bold"),
            bg="#2e7d32",
            fg="#ffffff",
            activebackground="#1b5e20",
            relief="groove",
            padx=14,
            pady=6,
            command=lambda: start_download()
        )
        btn_update.pack(side="left", padx=4)

        btn_later = tk.Button(
            btn_box,
            text="Nanti Saja",
            font=("Segoe UI", 9),
            relief="groove",
            padx=10,
            pady=4,
            command=dialog.destroy
        )
        btn_later.pack(side="right", padx=4)

        # Notes Frame — fills remaining space between header and buttons
        notes_frame = tk.Frame(dialog, bg="#f9f9f9", bd=1, relief="sunken")
        notes_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        txt_notes = tk.Text(notes_frame, font=("Segoe UI", 9), bg="#f9f9f9", wrap="word", relief="flat")
        txt_notes.pack(fill="both", expand=True, padx=6, pady=6)
        txt_notes.insert("1.0", f"Catatan Rilis:\n{notes if notes else '(Tidak ada catatan rilis)'}")
        txt_notes.config(state="disabled")

        def start_download():
            btn_update.config(state="disabled")
            btn_later.config(state="disabled")
            progress_bar.pack(fill="x", pady=(4, 0))
            lbl_status.pack(pady=(2, 0))

            current_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath("RaftLauncher.exe")

            def on_prog(percent, downloaded, total):
                progress_var.set(percent)
                mb_done = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                lbl_status.config(text=f"Mengunduh... {percent:.1f}% ({mb_done:.1f} MB / {mb_tot:.1f} MB)")

            def download_worker():
                try:
                    self.log(f"Mengunduh pembaruan {tag_name}...")
                    UpdateManager.perform_update(download_url, current_exe, on_progress=on_prog)
                except Exception as e:
                    self.log(f"✗ Gagal mengunduh update: {e}")
                    self.root.after(0, lambda: messagebox.showerror("Gagal Update", f"Terjadi kesalahan saat mengunduh update:\n{e}", parent=dialog))
                    self.root.after(0, dialog.destroy)

            threading.Thread(target=download_worker, daemon=True).start()

    def validate_config_fields(self, show_alert=True):
        """Checks if all required config fields are filled, and shows detailed alerts if empty."""
        missing = []
        num = 1

        raft_exe = self.raft_exe_var.get().strip()
        if not raft_exe:
            missing.append(
                f"{num}. Belum mengisi Raft.exe\n"
                f"   Silahkan mencari lokasi file Raft sesuai dengan pathnya (contoh: D:/.../Raft.exe)."
            )
            num += 1

        repo_dir = self.repo_path_var.get().strip()
        if not repo_dir:
            missing.append(
                f"{num}. Belum mengisi Repo Dir\n"
                f"   Silahkan mencari/memilih folder tempat untuk worldnya (contoh: D:/.../RAFT_WORLD)."
            )
            num += 1

        git_url = self.remote_url_var.get().strip()
        if not git_url:
            missing.append(
                f"{num}. Belum mengisi Git URL\n"
                f"   Silahkan mencari link URL Git repo untuk penyimpanan file world (contoh: https://github.com/Yohnzz/RAFT_WORLD.git)."
            )
            num += 1

        branch = self.branch_var.get().strip()
        if not branch:
            missing.append(
                f"{num}. Belum mengisi Branch\n"
                f"   Silahkan mengisi branch sesuai dengan apa yang ada (contoh: master)."
            )
            num += 1

        if missing:
            if show_alert:
                self.notebook.select(1)  # switch to 'Configuration & Paths' tab
                details = "\n\n".join(missing)
                msg = (
                    f"Ada {len(missing)} field konfigurasi yang belum diisi:\n\n"
                    f"{details}\n\n"
                    f"Silahkan lengkapi kolom di tab 'Configuration & Paths' lalu klik '💾 Save Config'."
                )
                messagebox.showwarning("Konfigurasi Belum Lengkap", msg)
            return False
        return True

    def save_current_settings(self, silent=False):
        self.config["raft_exe"] = self.raft_exe_var.get().strip()
        self.config["steam_user_id"] = self.get_selected_user_folder() or ""
        self.config["repo_path"] = self.repo_path_var.get().strip()
        self.config["remote_url"] = self.remote_url_var.get().strip()
        self.config["branch"] = self.branch_var.get().strip() or "master"
        save_config(self.config)

        if not silent:
            is_complete = self.validate_config_fields(show_alert=True)
            if is_complete:
                self.log("✓ Settings berhasil disimpan.")
                messagebox.showinfo("Sukses", "Semua konfigurasi berhasil disimpan dan siap digunakan!")
            else:
                self.log("⚠️ Settings tersimpan, namun masih ada field yang belum lengkap.")

    # =====================================================
    # GIT ACTIONS
    # =====================================================

    def test_git(self):
        def worker():
            repo_path = self.repo_path_var.get().strip()
            if not repo_path:
                self.log("✗ Tentukan path repository di tab Settings.")
                return
            git = GitEngine(repo_path)
            res = git.run(["--version"])
            if res["success"]:
                self.log(f"✓ {res['stdout']}")
                if git.is_valid_repo():
                    self.log("✓ Git repository valid.")
                else:
                    self.log("⚠️ Folder ini belum di-init sebagai git repo.")
            else:
                self.log("✗ Git tidak terdeteksi.")
        self.run_async(worker)

    def init_or_clone_repo(self):
        def worker():
            repo_path = self.repo_path_var.get().strip()
            remote_url = self.remote_url_var.get().strip()
            branch = self.branch_var.get().strip() or "master"
            if not repo_path:
                self.log("✗ Tentukan path folder repository.")
                return
            self.log(f"Setup Git repository di '{repo_path}' (branch: {branch})...")
            git = GitEngine(repo_path)
            ok, msg = git.clone_or_init(remote_url, branch=branch)
            self.log(f"{'✓' if ok else '✗'} {msg}")
        self.run_async(worker)

    def manual_pull(self):
        repo_path = self.repo_path_var.get().strip()
        branch = self.branch_var.get().strip() or "master"
        git = GitEngine(repo_path)
        if not git.is_valid_repo():
            self.log("✗ Repo belum valid. Buka Settings untuk setup.")
            return
        self.log(f"Menjalankan git pull origin/{branch} (Auto-Stash)...")
        res = git.pull(branch=branch)
        if res["success"]:
            self.log("✓ Git pull berhasil.")
            self.refresh_worlds()
        else:
            self.log(f"✗ Git pull gagal: {res['stderr']}")

    def manual_push(self):
        repo_path = self.repo_path_var.get().strip()
        branch = self.branch_var.get().strip() or "master"
        git = GitEngine(repo_path)
        if not git.is_valid_repo():
            self.log("✗ Repo belum valid.")
            return
        self.log(f"Menjalankan git push ke origin/{branch}...")
        git.add_all()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        player = self.get_selected_player_name()
        git.commit(f"[{player}] Manual Sync - {now_str}")
        res = git.push(branch=branch)
        if res["success"]:
            self.log("✓ Git push berhasil ke GitHub.")
        else:
            self.log(f"✗ Git push gagal: {res['stderr']}")

    # =====================================================
    # CONNECT (SYNC & PLAY RAFT)
    # =====================================================

    def prompt_game_mode(self, world_name):
        """Displays dialog allowing user to choose between Main Solo (Auto-Sync) or Multiplayer (Manual Sync)."""
        selected_mode = {"mode": None}

        dialog = tk.Toplevel(self.root)
        dialog.title("Pilih Mode Bermain - Raft Launcher")
        dialog.geometry("460x270")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog relative to parent window
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 230
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 135
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

        tk.Label(
            dialog,
            text=f"Pilih Mode Bermain: '{world_name}'",
            font=("Segoe UI", 11, "bold"),
            fg="#1e1e1e"
        ).pack(pady=(16, 6))

        tk.Label(
            dialog,
            text="Tentukan mode permainan sebelum menjalankan Raft:",
            font=("Segoe UI", 9),
            fg="#555555"
        ).pack(pady=(0, 14))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=25)

        # 1. Main Solo
        def choose_solo():
            selected_mode["mode"] = "solo"
            dialog.destroy()

        btn_solo = tk.Button(
            btn_frame,
            text="🎮  Main Solo (Auto-Sync Pull & Push)",
            font=("Segoe UI", 10, "bold"),
            bg="#2e7d32",
            fg="#ffffff",
            activebackground="#1b5e20",
            activeforeground="#ffffff",
            relief="groove",
            pady=8,
            command=choose_solo
        )
        btn_solo.pack(fill="x", pady=4)

        # 2. Main Multiplayer
        def choose_multi():
            selected_mode["mode"] = "multiplayer"
            dialog.destroy()

        btn_multi = tk.Button(
            btn_frame,
            text="👥  Main Multiplayer (Join Teman / Sync Manual)",
            font=("Segoe UI", 10, "bold"),
            bg="#0288d1",
            fg="#ffffff",
            activebackground="#0277bd",
            activeforeground="#ffffff",
            relief="groove",
            pady=8,
            command=choose_multi
        )
        btn_multi.pack(fill="x", pady=4)

        # 3. Batal
        tk.Button(
            dialog,
            text="Batal",
            font=("Segoe UI", 9),
            relief="groove",
            padx=12,
            pady=2,
            command=dialog.destroy
        ).pack(pady=(12, 10))

        self.root.wait_window(dialog)
        return selected_mode["mode"]

    def start_sync_and_play(self):
        if self.is_playing:
            return

        # 1. Check Steam status before proceeding
        if not SteamManager.is_running():
            ans = messagebox.askyesno(
                "Steam Belum Berjalan",
                "Aplikasi Steam belum terdeteksi aktif di komputer Anda!\n\n"
                "Game Raft membutuhkan aplikasi Steam yang sudah berjalan dan login agar save game dan koneksi in-game dapat berfungsi.\n\n"
                "Apakah Anda ingin membuka aplikasi Steam sekarang?"
            )
            if ans:
                self.launch_steam_app()
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Pilih World", "Silakan klik/pilih salah satu World pada tabel terlebih dahulu.")
            return

        # Validate all required configuration fields first
        if not self.validate_config_fields(show_alert=True):
            return

        world_name = self.tree.item(selected[0])["values"][0]
        user_folder = self.get_selected_user_folder()

        # Check & Locate Raft.exe (SA-MP style popup)
        raft_exe = self.locate_raft_exe()
        if not raft_exe:
            return

        # Prompt user to choose game mode (Solo vs Multiplayer)
        mode = self.prompt_game_mode(world_name)
        if not mode:
            return

        repo_path = self.repo_path_var.get().strip()
        remote_url = self.remote_url_var.get().strip()
        branch = self.branch_var.get().strip() or "master"

        self.save_current_settings(silent=True)
        self.is_playing = True
        mode_label = "Solo" if mode == "solo" else "Multi"
        self.btn_connect.config(state="disabled", text=f"⏳ Running ({mode_label})...", bg="#9e9e9e")

        self.run_async(self._sync_worker, raft_exe, user_folder, world_name, repo_path, remote_url, branch, mode)

    def _sync_worker(self, raft_exe, user_folder, world_name, repo_path, remote_url, branch, mode="solo"):
        git = GitEngine(repo_path)
        world_local_path = RaftWorldManager.get_world_path(user_folder, world_name)

        try:
            self.log(f"=== CONNECTING TO WORLD: {world_name} [MODE: {mode.upper()}] ===")

            if mode == "solo":
                # 1. Setup repo if needed
                if not git.is_valid_repo():
                    self.log("Menginisialisasi repo...")
                    ok, msg = git.clone_or_init(remote_url, branch=branch)
                    if not ok:
                        self.log(f"✗ Setup repo gagal: {msg}")
                        return

                # 2. Pull latest from remote
                self.log(f"Git pull origin/{branch} (Auto-Stash)...")
                pull_res = git.pull(branch=branch)
                if pull_res["success"]:
                    self.log("✓ Progress terbaru ditarik dari GitHub.")
                else:
                    self.log(f"⚠️ Catatan pull: {pull_res['stderr'] or pull_res['stdout']}")

                # 3. Install latest save into Raft
                ok, sync_msg = RaftWorldManager.sync_from_repo(repo_path, world_local_path, world_name)
                if ok:
                    self.log(f"✓ {sync_msg}")
                else:
                    self.log(f"ℹ️ {sync_msg}")

                self.root.after(0, self.refresh_worlds)
            else:
                self.log("👥 Mode Multiplayer: Melewati auto-pull (bisa pull manual di toolbar).")

            # 4. Launch Game
            self.log("Menjalankan Raft.exe...")
            try:
                proc = subprocess.Popen([raft_exe], cwd=os.path.dirname(raft_exe))
                self.log("✓ Raft aktif. Menunggu sesi selesai...")
                proc.wait()
                self.log("🛑 Raft telah ditutup.")
            except Exception as e:
                self.log(f"✗ Gagal membuka Raft: {e}")
                return

            if mode == "solo":
                # 5. Copy new Latest to repo
                self.log("Mendeteksi save '-Latest' baru untuk diupload...")
                ok, sync_repo_msg = RaftWorldManager.sync_to_repo(world_local_path, repo_path, world_name)
                if not ok:
                    self.log(f"✗ {sync_repo_msg}")
                    return
                self.log(f"✓ {sync_repo_msg}")

                # 6. Commit & Push
                self.log("Mengunggah save game ke GitHub...")
                git.add_all()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                player = self.get_selected_player_name()
                git.commit(f"[{player}] Update world '{world_name}' - {now_str}")
                push_res = git.push(branch=branch)
                if push_res["success"]:
                    self.log("🎉 SYNC SUKSES! Save terbaru sudah berada di GitHub.")
                else:
                    self.log(f"⚠️ Push error: {push_res['stderr']}")
            else:
                self.log("👥 Mode Multiplayer selesai. Gunakan tombol '⬆️ Push' manual jika ingin mengunggah save game.")

        finally:
            self.is_playing = False
            self.root.after(0, lambda: self.btn_connect.config(state="normal", text="▶ Connect", bg="#4caf50"))
            self.root.after(0, self.refresh_worlds)


# =========================================================
# APPLICATION ENTRYPOINT
# =========================================================

def main():
    root = tk.Tk()
    app = SampRaftClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()