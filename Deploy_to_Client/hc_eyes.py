"""HarnessCore v3.0 - Eyes Process (runs in User session)."""
import os, sys, json, time, socket, subprocess, ctypes, threading, sqlite3, shutil
from PIL import ImageGrab
from hc_config import *



class TCPConn:
    """Newline-delimited JSON over TCP."""
    def __init__(self, sock):
        self.sock = sock
        self.buf = ""

    def send(self, data):
        msg = json.dumps(data, ensure_ascii=False) + "\n"
        self.sock.sendall(msg.encode('utf-8'))

    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        while "\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk.decode('utf-8', errors='ignore')
        line, self.buf = self.buf.split("\n", 1)
        return json.loads(line)


def do_screenshot():
    """Capture screen, return filepath or error string."""
    try:
        temp_dir = os.path.join(BASE_DIR, "Temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        fname = os.path.join(temp_dir, f"ss_{int(time.time())}.png")
        img = ImageGrab.grab()
        if img is None:
            return None, "Cannot capture screen"
        img.save(fname)
        return fname, None
    except Exception as e:
        return None, str(e)


def do_list_windows():
    """Get list of visible windows as JSON string."""
    ps = (
        'Get-Process | Where-Object { $_.MainWindowTitle } '
        '| Select-Object Name, @{Name=\'Title\'; Expression={$_.MainWindowTitle}} '
        '| ConvertTo-Json'
    )
    try:
        out = subprocess.run(
            ['powershell', '-Command', ps],
            capture_output=True, creationflags=NOWINDOW, timeout=10
        ).stdout.decode('utf-8', errors='ignore').strip()
        return out, None
    except Exception as e:
        return None, str(e)


def activity_logger_loop():
    """Periodically scan windows and log to activity_log.jsonl."""
    last_snap = ""
    while True:
        try:
            raw, err = do_list_windows()
            if raw and not err:
                data = json.loads(raw) if raw else []
                if isinstance(data, dict):
                    data = [data]

                entries = []
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                for item in data:
                    name = item.get('Name', '').lower()
                    if name in HIDDEN_PROCS:
                        continue
                    title = (item.get('Title', '') or '')[:120]
                    entries.append({"time": ts, "app": name, "title": title})

                snap_key = "|".join(f"{e['app']}:{e['title']}" for e in entries)
                if snap_key != last_snap and entries:
                    with open(ACTIVITY_FILE, 'a', encoding='utf-8') as f:
                        for e in entries:
                            f.write(json.dumps(e, ensure_ascii=False) + "\n")
                    last_snap = snap_key

            # Cleanup old entries (keep 7 days) - run once per hour
            if int(time.time()) % 3600 < ACTIVITY_SCAN_SEC:
                cleanup_activity_log()
        except Exception as e:
            log_event(f"Activity logger error: {e}", "ERROR")
        time.sleep(ACTIVITY_SCAN_SEC)


def cleanup_activity_log():
    """Remove entries older than 7 days."""
    if not os.path.exists(ACTIVITY_FILE):
        return
    try:
        cutoff = time.strftime('%Y-%m-%d', time.localtime(time.time() - 7 * 86400))
        lines = []
        with open(ACTIVITY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("time", "")[:10] >= cutoff:
                        lines.append(line)
                except Exception:
                    pass
        with open(ACTIVITY_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n" if lines else "")
    except Exception:
        pass


def check_browser_history(history_path, last_time, app_name):
    if not os.path.exists(history_path):
        return last_time, []
    
    temp_dir = os.path.join(BASE_DIR, "Temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_history = os.path.join(temp_dir, f"hist_temp_{app_name}")
    
    try:
        shutil.copy2(history_path, temp_history)
        conn = sqlite3.connect(temp_history)
        cursor = conn.cursor()
        
        if last_time == 0:
            cursor.execute("SELECT MAX(visit_time) FROM visits")
            row = cursor.fetchone()
            max_val = row[0] if row and row[0] else 0
            conn.close()
            try: os.remove(temp_history)
            except: pass
            return max_val, []
            
        cursor.execute(
            "SELECT urls.url, urls.title, visits.visit_time, visits.visit_duration "
            "FROM visits JOIN urls ON visits.url = urls.id "
            "WHERE visits.visit_time > ? ORDER BY visits.visit_time ASC LIMIT 100",
            (last_time,)
        )
        
        rows = cursor.fetchall()
        new_entries = []
        new_last_time = last_time
        
        for url_val, title, visit_time, duration in rows:
            new_last_time = max(new_last_time, visit_time)
            dur_sec = round(duration / 1000000.0, 1)
            try:
                utime = (visit_time / 1000000.0) - 11644473600
                ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(utime))
            except:
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                
            if url_val:
                new_entries.append({
                    "time": ts,
                    "app": app_name,
                    "title": f"[URL] {title} ({url_val}) [{dur_sec}s]"
                })
        
        conn.close()
        try: os.remove(temp_history)
        except: pass
        return new_last_time, new_entries
    except Exception as e:
        try: conn.close()
        except: pass
        try: os.remove(temp_history)
        except: pass
        return last_time, []

def browser_history_logger_loop():
    """Background thread to monitor Chrome and Edge history."""
    chrome_last = 0
    edge_last = 0
    
    user_profile = os.environ.get("USERPROFILE", "")
    chrome_hist = os.path.join(user_profile, r"AppData\Local\Google\Chrome\User Data\Default\History")
    edge_hist = os.path.join(user_profile, r"AppData\Local\Microsoft\Edge\User Data\Default\History")
    
    # Initialize timestamps
    chrome_last, _ = check_browser_history(chrome_hist, 0, "chrome")
    edge_last, _ = check_browser_history(edge_hist, 0, "edge")
    
    while True:
        try:
            time.sleep(60)
            chrome_last, chrome_entries = check_browser_history(chrome_hist, chrome_last, "chrome")
            edge_last, edge_entries = check_browser_history(edge_hist, edge_last, "edge")
            
            all_entries = chrome_entries + edge_entries
            if all_entries:
                with open(ACTIVITY_FILE, 'a', encoding='utf-8') as f:
                    for e in all_entries:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except Exception as e:
            pass

def eyes_main_loop():
    """Main loop: connect to Master via TCP, serve commands, log activity."""
    # Check Session ID: Eyes must not run in Session 0 (SYSTEM session)
    kernel32 = ctypes.windll.kernel32
    session_id = ctypes.c_ulong()
    if kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(session_id)):
        if session_id.value == 0:
            log_event("Eyes process cannot run in Session 0. Exiting.", "WARNING")
            sys.exit(0)

    # Prevent duplicate Eyes processes using Windows Mutex
    if is_another_eyes_running():
        log_event("BLOCKED: Another Eyes process is already running. Exiting.", "WARNING")
        sys.exit(0)

    log_event("Eyes process starting.")
    threading.Thread(target=activity_logger_loop, daemon=True).start()
    threading.Thread(target=browser_history_logger_loop, daemon=True).start()

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", IPC_PORT))
            conn = TCPConn(sock)
            log_event("Eyes connected to Master via TCP.")

            while True:
                try:
                    req = conn.recv(timeout=10)
                except socket.timeout:
                    continue
                except ConnectionError:
                    log_event("Eyes lost connection to Master.", "WARNING")
                    break

                cmd = req.get("command", "")
                res = {"id": req.get("id"), "status": "done", "data": {}}

                if cmd == "ping":
                    res["data"]["pong"] = True

                elif cmd == "sshot":
                    fpath, err = do_screenshot()
                    if err:
                        res["data"]["error"] = err
                    else:
                        res["data"]["file"] = fpath

                elif cmd == "list":
                    out, err = do_list_windows()
                    if err:
                        res["data"]["error"] = err
                    else:
                        res["data"]["output"] = out

                elif cmd == "lock":
                    try:
                        ctypes.windll.user32.LockWorkStation()
                    except Exception as e:
                        res["data"]["error"] = str(e)

                conn.send(res)
                log_event(f"Eyes processed: {cmd}")

        except Exception as e:
            log_event(f"Eyes TCP error: {e}", "ERROR")
            time.sleep(5)


if __name__ == "__main__":
    eyes_main_loop()
