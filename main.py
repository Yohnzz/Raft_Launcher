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
from pathlib import Path
from datetime import datetime
import winreg

# =========================================================
# CONFIGURATION & CONSTANTS
# =========================================================

APP_NAME = "Raft Multiplayer Launcher"
APP_VERSION = "V 0.2"
APP_AUTHOR = "Igna"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "raft_exe": "",
    "steam_user_id": "",
    "selected_world": "",
    "repo_path": "",
    "remote_url": "",
    "branch": "master",
    "auto_check_steam": True
}

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
    def get_all_saves_in_world(world_path):
        """Returns list of timestamp directories inside world sorted newest first."""
        if not os.path.exists(world_path):
            return []
        saves = []
        for item in os.listdir(world_path):
            p = os.path.join(world_path, item)
            if os.path.isdir(p) and not item.startswith(".") and item not in ["backups", "OldSaveSystem-Backup"]:
                mtime = os.path.getmtime(p)
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                is_latest = item.lower().endswith("-latest") or "latest" in item.lower()
                saves.append({
                    "name": item,
                    "is_latest": is_latest,
                    "mtime": mtime,
                    "mtime_str": mtime_str,
                    "path": p
                })
        # Sort latest first, then by modification time
        saves.sort(key=lambda x: (not x["is_latest"], -x["mtime"]))
        return saves

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

            return True, f"Save dari '{latest_name}' berhasil disalin ke folder repo."
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

    def stash(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.run(["stash", "save", "-u", f"Auto-stash {timestamp}"])

    def pull(self, branch="master"):
        st = self.status()
        if st["stdout"]:
            self.stash()

        res = self.run(["pull", "--rebase=false", "origin", branch])
        if not res["success"]:
            err_lower = res["stderr"].lower()
            if "unstaged" in err_lower or "stash" in err_lower or "rebase" in err_lower or "conflict" in err_lower:
                self.stash()
                res = self.run(["pull", "--rebase=false", "origin", branch])
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
            if "rejected" in err_lower or "non-fast-forward" in err_lower or "behind" in err_lower:
                # Auto-pull and merge diverged changes
                self.run(["pull", "--no-rebase", "-X", "theirs", "origin", branch])
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

        self.setup_menu()
        self.build_ui()
        self.load_data()

        # Check Steam status
        self.check_steam_status()

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

        # View
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Refresh World List", accelerator="F5", command=self.refresh_worlds)
        view_menu.add_command(label="Open World Folder", command=self.open_world_folder)
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
        help_menu.add_command(label=f"About {APP_NAME}", command=lambda: messagebox.showinfo("About", f"{APP_NAME} {APP_VERSION}\nAuthor: {APP_AUTHOR}\n\nDedicated multiplayer turn-based world synchronizer for Raft."))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    # =====================================================
    # UI CONSTRUCTION
    # =====================================================

    def build_ui(self):
        # 1. TOP TOOLBAR STRIP
        toolbar = tk.Frame(self.root, bg="#f5f5f5", bd=1, relief="raised", height=38)
        toolbar.pack(fill="x", side="top", padx=2, pady=2)

        # Connect / Play Button (Green Icon style)
        self.btn_connect = tk.Button(toolbar, text="▶ Connect", font=("Segoe UI", 9, "bold"), bg="#4caf50", fg="#ffffff", activebackground="#43a047", relief="groove", padx=8, pady=2, command=self.start_sync_and_play)
        self.btn_connect.pack(side="left", padx=(4, 2), pady=3)

        # Reload / Refresh
        btn_refresh = tk.Button(toolbar, text="🔄 Refresh", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.refresh_worlds)
        btn_refresh.pack(side="left", padx=2, pady=3)

        # Git Pull
        btn_pull = tk.Button(toolbar, text="⬇️ Pull", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.manual_pull)
        btn_pull.pack(side="left", padx=2, pady=3)

        # Git Push
        btn_push = tk.Button(toolbar, text="⬆️ Push", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.manual_push)
        btn_push.pack(side="left", padx=2, pady=3)

        # Open folder
        btn_open = tk.Button(toolbar, text="📂 Folder", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.open_world_folder)
        btn_open.pack(side="left", padx=2, pady=3)

        # Steam Action
        self.btn_steam = tk.Button(toolbar, text="🎮 Steam", font=("Segoe UI", 9), relief="groove", padx=6, pady=2, command=self.launch_steam_app)
        self.btn_steam.pack(side="left", padx=2, pady=3)

        # Separator
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        # Name / Steam Account Selector
        tk.Label(toolbar, text="Name:", font=("Segoe UI", 9, "bold"), bg="#f5f5f5").pack(side="left", padx=(2, 4))
        self.user_var = tk.StringVar()
        self.combo_user = ttk.Combobox(toolbar, textvariable=self.user_var, state="readonly", font=("Segoe UI", 9), width=28)
        self.combo_user.pack(side="left", padx=(0, 8), pady=4)
        self.combo_user.bind("<<ComboboxSelected>>", self.on_user_changed)

        # Top Right Raft Badge
        badge_frame = tk.Frame(toolbar, bg="#ff6600", padx=10, pady=2)
        badge_frame.pack(side="right", padx=6, pady=3)
        tk.Label(badge_frame, text=f"RAFT {APP_VERSION}", font=("Segoe UI", 9, "bold italic"), fg="#ffffff", bg="#ff6600").pack()

        # 2. MAIN CENTER AREA (SPLIT PANE: LEFT SERVER LIST, RIGHT DETAILS)
        main_paned = tk.PanedWindow(self.root, orient="horizontal", bg="#d9d9d9", sashrelief="ridge", sashwidth=4)
        main_paned.pack(fill="both", expand=True, padx=4, pady=2)

        # --- LEFT PANEL: WORLD BROWSER (SAMP SERVER LIST STYLE) ---
        left_frame = tk.Frame(main_paned, bg="#ffffff")
        main_paned.add(left_frame, minsize=480)

        # Treeview (World List)
        tree_scroll_y = tk.Scrollbar(left_frame, orient="vertical")
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x = tk.Scrollbar(left_frame, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        columns = ("world_name", "latest_save", "saves_count", "status", "folder_path")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="browse", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
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

        # --- RIGHT PANEL: DETAILS (SAMP PLAYER & RULES BOXES) ---
        right_frame = tk.Frame(main_paned, bg="#f0f0f0")
        main_paned.add(right_frame, minsize=260)

        # Top Right Box: Save Timestamps (Like Player List)
        lbl_player_header = tk.Label(right_frame, text="Save Timestamps / History", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", anchor="w", padx=6, pady=2)
        lbl_player_header.pack(fill="x")

        save_box_frame = tk.Frame(right_frame, bg="#ffffff")
        save_box_frame.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        save_scroll = tk.Scrollbar(save_box_frame, orient="vertical")
        save_scroll.pack(side="right", fill="y")

        self.save_tree = ttk.Treeview(save_box_frame, columns=("timestamp", "type"), show="headings", selectmode="browse", yscrollcommand=save_scroll.set)
        save_scroll.config(command=self.save_tree.yview)

        self.save_tree.heading("timestamp", text="Save Timestamp", anchor="w")
        self.save_tree.heading("type", text="Type", anchor="center")
        self.save_tree.column("timestamp", width=160, minwidth=120)
        self.save_tree.column("type", width=70, minwidth=60, anchor="center")
        self.save_tree.pack(fill="both", expand=True)

        # Bottom Right Box: Properties / Rule-Value (Like Rules Box)
        lbl_rule_header = tk.Label(right_frame, text="World & Git Properties", font=("Segoe UI", 9, "bold"), bg="#e0e0e0", anchor="w", padx=6, pady=2)
        lbl_rule_header.pack(fill="x")

        rule_box_frame = tk.Frame(right_frame, bg="#ffffff")
        rule_box_frame.pack(fill="both", expand=True, padx=2, pady=0)

        rule_scroll = tk.Scrollbar(rule_box_frame, orient="vertical")
        rule_scroll.pack(side="right", fill="y")

        self.rule_tree = ttk.Treeview(rule_box_frame, columns=("property", "value"), show="headings", selectmode="browse", yscrollcommand=rule_scroll.set)
        rule_scroll.config(command=self.rule_tree.yview)

        self.rule_tree.heading("property", text="Property", anchor="w")
        self.rule_tree.heading("value", text="Value", anchor="w")
        self.rule_tree.column("property", width=100, minwidth=80)
        self.rule_tree.column("value", width=160, minwidth=120)
        self.rule_tree.pack(fill="both", expand=True)

        # 3. BOTTOM DETAIL NOTEBOOK TABS & QUICK CONFIG (Favorites / Internet / Settings)
        bottom_tabs_frame = tk.Frame(self.root, bg="#f0f0f0")
        bottom_tabs_frame.pack(fill="x", padx=4, pady=(2, 0))

        self.notebook = ttk.Notebook(bottom_tabs_frame)
        self.notebook.pack(fill="x")

        # TAB 1: Server Info / Quick Status (SAMP Footer info box)
        tab_info = tk.Frame(self.notebook, bg="#f5f5f5", padx=8, pady=6)
        self.notebook.add(tab_info, text=" Server Info ")

        info_grid = tk.Frame(tab_info, bg="#f5f5f5")
        info_grid.pack(fill="x")

        self.lbl_info_world = tk.Label(info_grid, text="World: None", font=("Segoe UI", 9, "bold"), bg="#f5f5f5", anchor="w")
        self.lbl_info_world.grid(row=0, column=0, sticky="w", padx=(0, 20))

        self.lbl_info_latest = tk.Label(info_grid, text="Latest Save: None", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_latest.grid(row=0, column=1, sticky="w", padx=(0, 20))

        self.lbl_info_steam = tk.Label(info_grid, text="Steam: Checking...", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_steam.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=(4, 0))

        self.lbl_info_git = tk.Label(info_grid, text="Git: origin/master", font=("Segoe UI", 9), bg="#f5f5f5", anchor="w")
        self.lbl_info_git.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(4, 0))

        # TAB 2: Quick Settings / Paths
        tab_settings = tk.Frame(self.notebook, bg="#f5f5f5", padx=8, pady=6)
        self.notebook.add(tab_settings, text=" Configuration & Paths ")

        # Row 1: Raft.exe
        row1 = tk.Frame(tab_settings, bg="#f5f5f5")
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Raft.exe:", width=12, anchor="w", bg="#f5f5f5").pack(side="left")
        self.raft_exe_var = tk.StringVar()
        self.entry_exe = tk.Entry(row1, textvariable=self.raft_exe_var, bg="#fff")
        self.entry_exe.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row1, text="Browse", padx=6, command=self.browse_raft_exe).pack(side="left")

        # Row 2: Local Repo & Branch
        row2 = tk.Frame(tab_settings, bg="#f5f5f5")
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Repo Dir:", width=12, anchor="w", bg="#f5f5f5").pack(side="left")
        self.repo_path_var = tk.StringVar()
        self.entry_repo = tk.Entry(row2, textvariable=self.repo_path_var, bg="#fff")
        self.entry_repo.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row2, text="Browse", padx=6, command=self.browse_repo_dir).pack(side="left")

        tk.Label(row2, text="Branch:", bg="#f5f5f5").pack(side="left", padx=(8, 2))
        self.branch_var = tk.StringVar(value="master")
        self.entry_branch = tk.Entry(row2, textvariable=self.branch_var, width=10, bg="#fff")
        self.entry_branch.pack(side="left", padx=2)

        # Row 3: Remote URL & Save Config
        row3 = tk.Frame(tab_settings, bg="#f5f5f5")
        row3.pack(fill="x", pady=2)
        tk.Label(row3, text="Git URL:", width=12, anchor="w", bg="#f5f5f5").pack(side="left")
        self.remote_url_var = tk.StringVar()
        self.entry_url = tk.Entry(row3, textvariable=self.remote_url_var, bg="#fff")
        self.entry_url.pack(side="left", fill="x", expand=True, padx=4)
        tk.Button(row3, text="💾 Save Config", bg="#e0e0e0", padx=8, command=self.save_current_settings).pack(side="left", padx=2)

        # TAB 3: Activity Log (Terminal)
        tab_log = tk.Frame(self.notebook, bg="#f5f5f5", padx=6, pady=4)
        self.notebook.add(tab_log, text=" Activity Log ")

        log_scroll = tk.Scrollbar(tab_log, orient="vertical")
        log_scroll.pack(side="right", fill="y")
        self.log_text = tk.Text(tab_log, height=5, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff", yscrollcommand=log_scroll.set)
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

    def start_sync_and_play(self):
        if self.is_playing:
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

        repo_path = self.repo_path_var.get().strip()
        remote_url = self.remote_url_var.get().strip()
        branch = self.branch_var.get().strip() or "master"

        self.save_current_settings(silent=True)
        self.is_playing = True
        self.btn_connect.config(state="disabled", text="⏳ Running...", bg="#9e9e9e")

        self.run_async(self._sync_worker, raft_exe, user_folder, world_name, repo_path, remote_url, branch)

    def _sync_worker(self, raft_exe, user_folder, world_name, repo_path, remote_url, branch):
        git = GitEngine(repo_path)
        world_local_path = RaftWorldManager.get_world_path(user_folder, world_name)

        try:
            self.log(f"=== CONNECTING TO WORLD: {world_name} ===")

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