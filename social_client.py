"""
social_client.py
Socket.IO client untuk Raft Social Backend
Phase 3: Presence (ONLINE/PLAYING/OFFLINE) + Heartbeat

Module ini TIDAK menyentuh GUI secara langsung.
Launcher (main.py) memanggil method di sini, dan social_client
memanggil callback yang didaftarkan launcher untuk update UI.
"""

import threading
import time
import logging

try:
    import socketio
except ImportError:
    socketio = None
    print("[Social] python-socketio belum terinstall. Jalankan: pip install python-socketio[client]")

logger = logging.getLogger("social_client")


class SocialClient:
    """
    Klien Socket.IO untuk koneksi ke Raft Social Backend.

    Lifecycle:
        connect() → auth → heartbeat loop
        set_playing()   → status PLAYING
        set_online()    → status ONLINE
        disconnect()    → OFFLINE (otomatis oleh server)
    """

    def __init__(self, backend_url="http://localhost:3000"):
        self.backend_url = backend_url
        self.steam_id = None
        self.username = None
        self.connected = False
        self.authenticated = False
        self._sio = None
        self._heartbeat_thread = None
        self._stop_heartbeat = threading.Event()

        # Callbacks yang bisa didaftarkan oleh launcher (main.py)
        self._on_connect_cb = None
        self._on_disconnect_cb = None
        self._on_presence_update_cb = None
        self._on_auth_result_cb = None
        self._on_message_received_cb = None
        self._on_game_invite_cb = None
        self._on_game_invite_resolved_cb = None
        self._on_game_invite_expired_cb = None

    # ─── CALLBACKS REGISTRATION ──────────────────────────────────────────────

    def on_connect(self, callback):
        """Dipanggil saat berhasil connect ke backend"""
        self._on_connect_cb = callback

    def on_disconnect(self, callback):
        """Dipanggil saat disconnect dari backend"""
        self._on_disconnect_cb = callback

    def on_presence_update(self, callback):
        """Dipanggil saat ada user lain yang berubah status
        callback(data) dimana data = {steam_id, username, status}
        """
        self._on_presence_update_cb = callback

    def on_message_received(self, callback):
        """Dipanggil saat ada pesan chat baru masuk realtime
        callback(data) dimana data = {id, sender_steam_id, sender_username, receiver_steam_id, message, created_at}
        """
        self._on_message_received_cb = callback

    def on_game_invite(self, callback):
        """Dipanggil saat menerima ajakan main dari teman
        callback(data) dimana data = {invite_id, from_steam_id, from_username, world_name, expires_at}
        """
        self._on_game_invite_cb = callback

    def on_game_invite_resolved(self, callback):
        """Dipanggil saat teman merespons ajakan main (TERIMA / TOLAK)
        callback(data) dimana data = {invite_id, accepted, responder_steam_id, responder_username, world_name}
        """
        self._on_game_invite_resolved_cb = callback

    def on_game_invite_expired(self, callback):
        """Dipanggil saat undangan kedaluwarsa (timeout)
        callback(data) dimana data = {invite_id}
        """
        self._on_game_invite_expired_cb = callback

    def on_auth_result(self, callback):
        """Dipanggil setelah auth selesai
        callback(success: bool, user: dict|None)
        """
        self._on_auth_result_cb = callback

    # ─── CONNECTION ──────────────────────────────────────────────────────────

    def connect(self, steam_id, username, avatar_url=None):
        """
        Connect ke backend dan otomatis auth + mulai heartbeat.
        Berjalan di background thread — tidak memblokir GUI.
        """
        if socketio is None:
            logger.warning("python-socketio not installed, social features disabled")
            return

        if self.connected:
            logger.info("Already connected, skipping")
            return

        self.steam_id = str(steam_id)
        self.username = username
        self._avatar_url = avatar_url

        thread = threading.Thread(target=self._connect_worker, daemon=True)
        thread.start()

    def _connect_worker(self):
        """Worker thread: connect → auth → heartbeat"""
        try:
            self._sio = socketio.Client(
                logger=False,
                engineio_logger=False,
                reconnection=True,
                reconnection_attempts=0,  # unlimited
                reconnection_delay=5,
                reconnection_delay_max=30,
            )

            # ─── Socket Events ─────────────────────────────────────────────
            @self._sio.event
            def connect():
                self.connected = True
                logger.info(f"Connected to {self.backend_url}")
                if self._on_connect_cb:
                    self._on_connect_cb()
                # Auto auth setelah connect/reconnect
                self._do_auth()

            @self._sio.event
            def disconnect():
                self.connected = False
                self.authenticated = False
                logger.info("Disconnected from backend")
                if self._on_disconnect_cb:
                    self._on_disconnect_cb()

            @self._sio.event
            def connect_error(data):
                logger.warning(f"Connection error: {data}")

            @self._sio.on('presence_update')
            def on_presence(data):
                logger.info(f"Presence: {data.get('username')} -> {data.get('status')}")
                if self._on_presence_update_cb:
                    self._on_presence_update_cb(data)

            @self._sio.on('new_message')
            def on_new_msg(data):
                logger.info(f"New message from {data.get('sender_username')}")
                if self._on_message_received_cb:
                    self._on_message_received_cb(data)

            @self._sio.on('game_invite')
            def on_invite(data):
                logger.info(f"Game invite received from {data.get('from_username')}")
                if self._on_game_invite_cb:
                    self._on_game_invite_cb(data)

            @self._sio.on('game_invite_resolved')
            def on_invite_res(data):
                logger.info(f"Game invite resolved: {data.get('responder_username')} -> accepted={data.get('accepted')}")
                if self._on_game_invite_resolved_cb:
                    self._on_game_invite_resolved_cb(data)

            @self._sio.on('game_invite_expired')
            def on_invite_exp(data):
                logger.info(f"Game invite expired: {data.get('invite_id')}")
                if self._on_game_invite_expired_cb:
                    self._on_game_invite_expired_cb(data)

            # ─── Connect ───────────────────────────────────────────────────
            self._sio.connect(self.backend_url, transports=['websocket'])

            # Start heartbeat loop
            self._stop_heartbeat.clear()
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread.start()

            # Block thread sampai disconnect
            self._sio.wait()

        except Exception as e:
            logger.error(f"Social connect error: {e}")

    def _do_auth(self):
        """Kirim auth event ke backend"""
        if not self._sio or not self.connected:
            return

        auth_data = {
            "steam_id": self.steam_id,
            "username": self.username,
        }
        if self._avatar_url:
            auth_data["avatar_url"] = self._avatar_url

        def on_auth_response(response):
            if response.get("success"):
                self.authenticated = True
                logger.info(f"Auth OK: {self.username}")
                if self._on_auth_result_cb:
                    self._on_auth_result_cb(True, response.get("user"))
            else:
                self.authenticated = False
                logger.warning(f"Auth failed: {response.get('error')}")
                if self._on_auth_result_cb:
                    self._on_auth_result_cb(False, None)

        self._sio.emit("auth", auth_data, callback=on_auth_response)

    def _heartbeat_loop(self):
        """Kirim heartbeat setiap 20 detik selama masih connected"""
        while not self._stop_heartbeat.is_set():
            if self._sio and self.connected:
                try:
                    self._sio.emit("heartbeat")
                except Exception:
                    pass
            self._stop_heartbeat.wait(20)

    # ─── STATUS CONTROL ──────────────────────────────────────────────────────

    def set_playing(self):
        """Panggil saat Raft dijalankan → status berubah ke PLAYING"""
        self._update_status("PLAYING")

    def set_online(self):
        """Panggil saat Raft ditutup → status kembali ke ONLINE"""
        self._update_status("ONLINE")

    def _update_status(self, status):
        """Kirim status_update event ke backend"""
        if not self._sio or not self.authenticated:
            return

        def on_response(response):
            if response.get("success"):
                logger.info(f"Status updated: {status}")
            else:
                logger.warning(f"Status update failed: {response.get('error')}")

        try:
            self._sio.emit("status_update", {"status": status}, callback=on_response)
        except Exception as e:
            logger.error(f"Status update error: {e}")

    # ─── GET ONLINE USERS ────────────────────────────────────────────────────

    def get_online_users(self, callback):
        """
        Minta daftar user online dari server.
        callback(users: list) → [{steam_id, username, status}, ...]
        """
        if not self._sio or not self.authenticated:
            callback([])
            return

        def on_response(response):
            callback(response.get("users", []))

        try:
            self._sio.emit("get_online_users", callback=on_response)
        except Exception:
            callback([])

    # ─── GET ALL USERS (FRIENDS LIST) ────────────────────────────────────────

    def get_all_users(self, callback):
        """
        Minta seluruh daftar user (ONLINE, PLAYING, OFFLINE) dari server.
        callback(users: list) → [{steam_id, username, status, avatar_url, last_seen}, ...]
        """
        if not self._sio or not self.authenticated:
            callback([])
            return

        def on_response(response):
            callback(response.get("users", []))

        try:
            self._sio.emit("get_all_users", callback=on_response)
        except Exception as e:
            logger.error(f"get_all_users error: {e}")
            callback([])

    # ─── REALTIME CHAT (Phase 5) ─────────────────────────────────────────────

    def send_message(self, to_steam_id, message, callback=None):
        """
        Kirim pesan chat ke user lain secara realtime.
        callback(success: bool, data: dict|str)
        """
        if not self._sio or not self.authenticated:
            if callback:
                callback(False, "Belum terhubung ke backend")
            return

        def on_response(response):
            if callback:
                if response.get("success"):
                    callback(True, response.get("message"))
                else:
                    callback(False, response.get("error", "Gagal mengirim pesan"))

        try:
            self._sio.emit(
                "send_message",
                {"to_steam_id": str(to_steam_id), "message": message},
                callback=on_response
            )
        except Exception as e:
            logger.error(f"send_message error: {e}")
            if callback:
                callback(False, str(e))

    def get_chat_history(self, with_steam_id, callback, limit=50):
        """
        Ambil riwayat chat dengan user tertentu dari database.
        callback(messages: list)
        """
        if not self._sio or not self.authenticated:
            callback([])
            return

        def on_response(response):
            callback(response.get("messages", []))

        try:
            self._sio.emit(
                "get_chat_history",
                {"with_steam_id": str(with_steam_id), "limit": limit},
                callback=on_response
            )
        except Exception as e:
            logger.error(f"get_chat_history error: {e}")
            callback([])

    # ─── GAME INVITES (Phase 6) ──────────────────────────────────────────────

    def send_game_invite(self, to_steam_id, world_name, callback=None):
        """
        Kirim ajakan main Raft ke teman secara realtime.
        callback(response: dict) -> {success: bool, is_playing: bool, invite_id: str, error?: str}
        """
        if not self._sio or not self.authenticated:
            if callback:
                callback({"success": False, "error": "Belum terhubung ke backend"})
            return

        def on_response(response):
            if callback:
                callback(response)

        try:
            self._sio.emit(
                "game_invite",
                {"to_steam_id": str(to_steam_id), "world_name": str(world_name or 'Default World')},
                callback=on_response
            )
        except Exception as e:
            logger.error(f"send_game_invite error: {e}")
            if callback:
                callback({"success": False, "error": str(e)})

    def respond_game_invite(self, invite_id, accepted, callback=None):
        """
        Respons ajakan main dari teman (accepted: True/False).
        callback(response: dict)
        """
        if not self._sio or not self.authenticated:
            if callback:
                callback({"success": False, "error": "Belum terhubung ke backend"})
            return

        def on_response(response):
            if callback:
                callback(response)

        try:
            self._sio.emit(
                "game_invite_response",
                {"invite_id": str(invite_id), "accepted": bool(accepted)},
                callback=on_response
            )
        except Exception as e:
            logger.error(f"respond_game_invite error: {e}")
            if callback:
                callback({"success": False, "error": str(e)})

    # ─── DISCONNECT ──────────────────────────────────────────────────────────

    def disconnect(self):
        """Disconnect dari backend — panggil saat launcher ditutup"""
        self._stop_heartbeat.set()
        if self._sio and self.connected:
            try:
                self._sio.disconnect()
            except Exception:
                pass
        self.connected = False
        self.authenticated = False

    # ─── PROPERTIES ──────────────────────────────────────────────────────────

    @property
    def is_connected(self):
        return self.connected and self.authenticated
