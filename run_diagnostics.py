"""
Comprehensive Unciv AI Startup Diagnostic and Granular Ping Tracing Script
"""

import os
import sys
import time
import json
import socket
import subprocess

def log(msg: str):
    print(msg, flush=True)

def main():
    log("=" * 65)
    log("  UNCIV AI GRANULAR STARTUP & PING TRACER")
    log("=" * 65)

    log("\n[1] Python Environment:")
    log(f"    Executable: {sys.executable}")
    log(f"    Version: {sys.version.split()[0]}")
    log(f"    Working Directory: {os.getcwd()}")

    log("\n[2] Checking Files:")
    jar_path = os.path.abspath("Unciv.jar")
    bridge_path = os.path.abspath("bridge/UncivBridge.java")
    log_path = os.path.abspath("bridge_server.log")
    log(f"    Unciv.jar: {'FOUND' if os.path.exists(jar_path) else 'MISSING'} ({os.path.getsize(jar_path)} bytes)")
    log(f"    UncivBridge.java: {'FOUND' if os.path.exists(bridge_path) else 'MISSING'} ({os.path.getsize(bridge_path)} bytes)")

    log("\n[3] Testing Java JRE:")
    t0 = time.time()
    try:
        j_ver = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT, text=True)
        first_line = j_ver.strip().split('\n')[0]
        log(f"    Java detected in {time.time()-t0:.2f}s: {first_line}")
    except Exception as e:
        log(f"    Java check failed: {e}")
        return

    log("\n[4] Initializing UncivEngine (Daemon Spawn & Port Connect):")
    from unciv_engine import UncivEngine, UncivEngineError
    t0 = time.time()
    try:
        engine = UncivEngine()
        log(f"    Engine initialized in {time.time()-t0:.2f}s")
        log(f"    - Subprocess PID: {engine.process.pid if engine.process else 'None'}")
        log(f"    - Target Local Port: {engine.port}")
    except Exception as e:
        log(f"    Engine daemon startup FAILED: {e}")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                log(f"    Server Log Output:\n{f.read()}")
        return

    log("\n[5] Granular Ping Trace:")
    # 5.1 Process Check
    poll_code = engine.process.poll()
    log(f"    [5.1] Java process status: {'ALIVE' if poll_code is None else f'TERMINATED ({poll_code})'}")
    if poll_code is not None:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                log(f"    Server Log:\n{f.read()}")
        engine.close()
        return

    # 5.2 Socket state check
    log(f"    [5.2] Socket state: Connected to {engine.sock.getpeername() if engine.sock else 'None'}")

    # 5.3 Sending command bytes
    payload = {"command": "ping"}
    req_bytes = (json.dumps(payload) + "\n").encode("utf-8")
    log(f"    [5.3] Transmitting {len(req_bytes)} bytes: {req_bytes.decode().strip()}")
    t_send = time.time()
    try:
        engine.sock.settimeout(5.0)
        engine.sock.sendall(req_bytes)
        log(f"    [5.4] Transmission completed in {(time.time()-t_send)*1000:.2f}ms")
    except Exception as e:
        log(f"    [5.4] Transmission FAILED: {e}")
        engine.close()
        return

    # 5.5 Waiting for socket reply
    log(f"    [5.5] Awaiting response bytes from 127.0.0.1:{engine.port} (timeout=5.0s)...")
    t_recv = time.time()
    buf = bytearray()
    try:
        while True:
            chunk = engine.sock.recv(4096)
            if not chunk:
                raise UncivEngineError("Socket closed by remote bridge")
            buf.extend(chunk)
            if b"\n" in chunk:
                break
        elapsed_recv = (time.time() - t_recv) * 1000
        raw_reply = buf.decode("utf-8").strip()
        log(f"    [5.6] Received {len(buf)} bytes in {elapsed_recv:.2f}ms: '{raw_reply}'")
        data = json.loads(raw_reply)
        log(f"    [5.7] Parsed JSON response: status='{data.get('status')}', message='{data.get('message')}'")
        log(f"    --> Ping Test SUCCEEDED! Total time: {(time.time()-t_send)*1000:.2f}ms")
    except Exception as e:
        log(f"    [5.6] Receive FAILED: {e}")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                log(f"    Server Log:\n{f.read()}")
        engine.close()
        return

    log("\n[6] Granular Map Generation Trace (Rome, Prince, Tiny):")
    # 6.1 Payload preparation
    map_payload = {
        "command": "new_game",
        "nation": "Rome",
        "difficulty": "Prince",
        "ruleset": "Civ V - Vanilla",
        "map_size": "Tiny"
    }
    map_bytes = (json.dumps(map_payload) + "\n").encode("utf-8")
    log(f"    [6.1] Prepared new_game payload ({len(map_bytes)} bytes)")

    # 6.2 Transmission
    log(f"    [6.2] Sending new_game command to Java daemon...")
    t_send_map = time.time()
    try:
        engine.sock.settimeout(30.0)
        engine.sock.sendall(map_bytes)
        log(f"    [6.3] Command sent in {(time.time()-t_send_map)*1000:.2f}ms")
    except Exception as e:
        log(f"    [6.3] Command send FAILED: {e}")
        engine.close()
        return

    # 6.4 Awaiting procedural map generation and ruleset execution
    log(f"    [6.4] Awaiting Java map generation (procedural terrain, rivers, civ placements)...")
    t_map_recv = time.time()
    map_buf = bytearray()
    try:
        while True:
            chunk = engine.sock.recv(4096)
            if not chunk:
                raise UncivEngineError("Socket disconnected during map generation")
            map_buf.extend(chunk)
            if b"\n" in chunk:
                break
        map_elapsed = time.time() - t_map_recv
        map_reply = map_buf.decode("utf-8").strip()
        log(f"    [6.5] Received {len(map_buf)} bytes in {map_elapsed:.2f}s: '{map_reply}'")
        map_data = json.loads(map_reply)
        log(f"    [6.6] Parsed match data: status='{map_data.get('status')}', active_civ='{map_data.get('active_civ')}', turn={map_data.get('turn')}")
        log(f"    --> Map Generation SUCCEEDED! Total time: {time.time()-t_send_map:.2f}s")
    except Exception as e:
        log(f"    [6.5] Map Generation FAILED: {e}")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                log(f"    Server Log:\n{f.read()}")
        engine.close()
        return

    log("\n[7] Querying Initial State:")
    t0 = time.time()
    try:
        state = engine.get_state()
        log(f"    State retrieved in {time.time()-t0:.3f}s:")
        log(f"    - Civilization: {state.get('active_civ')}")
        log(f"    - Units: {len(state.get('units', []))} units ({[u.get('name') for u in state.get('units', [])]})")
        log(f"    - Cities: {len(state.get('cities', []))}")
    except Exception as e:
        log(f"    State retrieval FAILED: {e}")

    log("\n[8] Advancing Turn 0 -> Turn 1...")
    t0 = time.time()
    try:
        units = state.get("units", [])
        settler = next((u for u in units if u.get("name") == "Settler"), None)
        if settler:
            engine.unit_action(settler["id"], "found_city")
            log("    - Settler founded capital city (Rome)")
        end_res = engine.end_turn()
        log(f"    Turn advanced in {time.time()-t0:.2f}s!")
        log(f"    Notifications: {end_res.get('notifications', [])}")
    except Exception as e:
        log(f"    Turn advance FAILED: {e}")

    engine.close()
    log("\n" + "=" * 65)
    log("  ALL DIAGNOSTIC CHECKS COMPLETED SUCCESSFULLY!")
    log("=" * 65)

if __name__ == "__main__":
    main()
