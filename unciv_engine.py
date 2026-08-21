"""
Unciv Engine: Python SDK and Process Manager for the Unciv Java Headless Bridge.
Uses direct TCP loopback IPC on pre-allocated ports with file-based log redirection
to completely eliminate OS pipe buffer deadlocks across all terminal types.
"""

import json
import subprocess
import os
import sys
import threading
import time
import socket
from typing import Dict, Any, Optional, List, Tuple

class UncivEngineError(Exception):
    """Exception raised for Unciv engine errors."""
    pass

class UncivEngine:
    """
    Manages the lifecycle and TCP socket communication with the headless Unciv Java Bridge.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd())
        self.jar_path = os.path.join(self.base_dir, "Unciv.jar")
        self.bridge_source = os.path.join(self.base_dir, "bridge", "UncivBridge.java")
        self.log_path = os.path.join(self.base_dir, "bridge_server.log")
        self.process: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self.port: Optional[int] = None
        self._lock = threading.RLock()
        self._ensure_running()

    def _find_free_port(self) -> int:
        """Finds an available local port on 127.0.0.1."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _ensure_running(self):
        """Starts the bridge daemon process and establishes socket connection."""
        with self._lock:
            if self.sock is not None and self.process is not None and self.process.poll() is None:
                return

            self.close()

            if not os.path.exists(self.jar_path):
                raise UncivEngineError(f"Unciv.jar not found at {self.jar_path}")
            if not os.path.exists(self.bridge_source):
                raise UncivEngineError(f"UncivBridge source not found at {self.bridge_source}")

            # Pre-allocate free port
            self.port = self._find_free_port()

            cmd = [
                "java",
                "-Xms128m",
                "-Xmx1024m",
                "-XX:+UseG1GC",
                "-cp", "Unciv.jar",
                "bridge/UncivBridge.java",
                str(self.port)
            ]

            try:
                # Redirect process stdio to a dedicated log file on disk.
                # This ensures the JVM NEVER blocks on OS pipe buffers regardless of terminal type.
                log_file = open(self.log_path, "w", encoding="utf-8")
                self.process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=log_file,
                    cwd=self.base_dir
                )

                # Connect with socket retry loop (Java initializes rulesets then listens)
                t_start = time.time()
                connected = False
                while time.time() - t_start < 15.0:
                    if self.process.poll() is not None:
                        err_log = ""
                        try:
                            with open(self.log_path, "r", encoding="utf-8") as f:
                                err_log = f.read()[-1000:]
                        except Exception:
                            pass
                        raise UncivEngineError(f"Java daemon exited with code {self.process.returncode}. Log: {err_log}")

                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.settimeout(5.0)
                    try:
                        s.connect(("127.0.0.1", self.port))
                        self.sock = s
                        connected = True
                        break
                    except (ConnectionRefusedError, socket.timeout, OSError):
                        try:
                            s.close()
                        except Exception:
                            pass
                        time.sleep(0.1)

                if not connected or self.sock is None:
                    self.close()
                    raise UncivEngineError(f"Timed out connecting to Unciv bridge socket on port {self.port}")

            except Exception as e:
                self.close()
                raise UncivEngineError(f"Failed to start Unciv bridge daemon: {e}")

    def send_command(self, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """
        Sends a JSON-RPC request to the Java daemon over TCP socket and returns parsed response.
        """
        with self._lock:
            self._ensure_running()
            if self.sock is None:
                raise UncivEngineError("Bridge socket is not connected")

            req_data = (json.dumps(payload) + "\n").encode("utf-8")
            try:
                self.sock.settimeout(timeout)
                self.sock.sendall(req_data)

                # Read raw bytes until newline delimiter
                buf = bytearray()
                while True:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        raise UncivEngineError("Bridge socket disconnected unexpectedly")
                    buf.extend(chunk)
                    if b"\n" in chunk:
                        break

                line = buf.decode("utf-8").strip()
                data = json.loads(line)
                if isinstance(data, dict) and data.get("status") == "error":
                    raise UncivEngineError(data.get("error", "Unknown engine error"))
                return data

            except Exception as e:
                # If socket timed out or was interrupted (e.g. system sleep/resume)
                # check if Java daemon process is still healthy and try to reconnect
                if self.process and self.process.poll() is None:
                    try:
                        if self.sock:
                            try:
                                self.sock.close()
                            except Exception:
                                pass
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        s.settimeout(5.0)
                        s.connect(("127.0.0.1", self.port))
                        self.sock = s
                        # Retry ping
                        ping_res = (json.dumps({"command": "ping"}) + "\n").encode("utf-8")
                        self.sock.sendall(ping_res)
                        p_buf = bytearray()
                        while True:
                            p_chunk = self.sock.recv(4096)
                            if not p_chunk or b"\n" in p_chunk:
                                break
                        # Connection recovered
                        state_res = (json.dumps({"command": "get_state"}) + "\n").encode("utf-8")
                        self.sock.sendall(state_res)
                        s_buf = bytearray()
                        while True:
                            s_chunk = self.sock.recv(4096)
                            if not s_chunk:
                                break
                            s_buf.extend(s_chunk)
                            if b"\n" in s_chunk:
                                break
                        recovered_data = json.loads(s_buf.decode("utf-8").strip())
                        return {"status": "ok", "message": "Turn advanced (reconnected after suspend)", "state": recovered_data}
                    except Exception:
                        pass

                self.close()
                raise UncivEngineError(f"Bridge socket communication error: {e}")

    def ping(self) -> bool:
        """Pings the bridge process."""
        res = self.send_command({"command": "ping"})
        return res.get("message") == "pong"

    def new_game(self, nation: str = "", difficulty: str = "Prince",
                 ruleset: str = "Civ V - Vanilla", map_size: str = "Tiny") -> Dict[str, Any]:
        """
        Starts a new game with specified parameters.
        """
        return self.send_command({
            "command": "new_game",
            "nation": nation,
            "difficulty": difficulty,
            "ruleset": ruleset,
            "map_size": map_size
        })

    def get_state(self) -> Dict[str, Any]:
        """
        Fetches the complete game state from the perspective of the human/active player.
        """
        res = self.send_command({"command": "get_state"})
        return res.get("game", {})

    def get_map(self, center_x: int = 0, center_y: int = 0, radius: int = 6) -> Dict[str, Any]:
        """
        Fetches the map view centered at [center_x, center_y] with given radius.
        """
        res = self.send_command({
            "command": "get_map",
            "center_x": center_x,
            "center_y": center_y,
            "radius": radius
        })
        return res.get("map", {})

    def unit_action(self, unit_id: int, action: str, target_x: int = 0, target_y: int = 0,
                    param: str = "") -> Dict[str, Any]:
        """
        Executes an action for a specific unit.
        Actions: 'move', 'attack', 'found_city', 'improve', 'fortify', 'sleep', 'wake', 'promote', 'disband'
        """
        return self.send_command({
            "command": "unit_action",
            "unit_id": unit_id,
            "action": action,
            "target_x": target_x,
            "target_y": target_y,
            "param": param
        })

    def city_action(self, city_name: str, action: str, param: str = "",
                    target_x: int = 0, target_y: int = 0) -> Dict[str, Any]:
        """
        Executes an action for a city.
        Actions: 'set_production', 'add_to_queue', 'purchase', 'set_focus'
        """
        return self.send_command({
            "command": "city_action",
            "city_name": city_name,
            "action": action,
            "param": param,
            "target_x": target_x,
            "target_y": target_y
        })

    def choose_tech(self, tech_name: str) -> Dict[str, Any]:
        """
        Sets the active research technology.
        """
        return self.send_command({
            "command": "choose_tech",
            "tech_name": tech_name
        })

    def adopt_policy(self, policy_name: str) -> Dict[str, Any]:
        """
        Adopts a social policy.
        """
        return self.send_command({
            "command": "adopt_policy",
            "policy_name": policy_name
        })

    def diplomacy_action(self, target_civ: str, action: str, param: str = "") -> Dict[str, Any]:
        """
        Executes diplomacy action: 'declare_war', 'make_peace'
        """
        return self.send_command({
            "command": "diplomacy_action",
            "target_civ": target_civ,
            "action": action,
            "param": param
        })

    def end_turn(self, timeout: float = 180.0) -> Dict[str, Any]:
        """
        Finishes current player's turn, executes AI turns, and returns turn notifications.
        """
        return self.send_command({"command": "end_turn"}, timeout=timeout)

    def save_game(self) -> str:
        """
        Serializes current game state and returns the save string.
        """
        res = self.send_command({"command": "save_game"})
        return res.get("save_data", "")

    def load_game(self, save_data: str) -> Dict[str, Any]:
        """
        Loads a game from a save string.
        """
        return self.send_command({
            "command": "load_game",
            "save_data": save_data
        })

    def close(self):
        """Terminates socket and bridge process."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        if self.process:
            try:
                self.process.kill()
                self.process.wait(timeout=1.0)
            except Exception:
                pass
            self.process = None

    def __del__(self):
        self.close()
