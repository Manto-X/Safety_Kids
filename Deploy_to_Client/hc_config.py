"""
HarnessCore v3.0 - Configuration, Constants & Shared Utilities.

Centralizes all config, text strings, and helper functions
used by both Master and Eyes processes.
"""
import os
import sys
import json
import time
import threading
import subprocess
import ctypes

__all__ = [
    # Paths
    "BASE_DIR", "CONFIG_DIR", "DATA_DIR", "CONFIG_FILE", "CHILD_FILE", "SCHEDULE_FILE",
    "TIMER_FILE", "LOG_FILE", "ACTIVITY_FILE", "RESTRICTED_FILE",

    # Config
    "CFG", "API_TOKEN", "ALLOWED_ID", "API_KEY", "API_PORT", "IPC_PORT",
    # Timing constants
    "POLLING_INTERVAL", "POLLING_TIMEOUT", "RECONNECT_DELAY",
    "DEDUP_MAX_SIZE", "STARTUP_RETRY_DELAY", "STARTUP_MAX_RETRIES",
    "SCHEDULE_CHECK_SEC", "WATCHDOG_SEC", "ACTIVITY_SCAN_SEC",
    # Firewall
    "FW_RULE_OUT", "FW_RULE_IN", "NOWINDOW",
    # App constants
    "CHILD_NOT_SET", "HIDDEN_PROCS", "CURRENT_PID", "PROC_TYPE",
    # Text strings
    "MSG",
    # Functions
    "log_event", "wipe_logs", "is_another_master_running", "is_another_eyes_running", "is_duplicate",
    "save_child_info", "get_child_info",
    "save_net_timer", "get_timer_info", "clear_net_timer",
    "load_schedule", "save_schedule",
    "block_internet", "unblock_internet", "is_internet_blocked",
]

# =============================================================================
#  SECTION 1: FILE PATHS & CONFIG
# =============================================================================

import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

CONFIG_DIR = os.path.join(BASE_DIR, 'config')
CONFIG_SAMPLE_DIR = os.path.join(BASE_DIR, 'config_sample')
DATA_DIR = os.path.join(BASE_DIR, 'data')

if not os.path.exists(CONFIG_DIR):
    if os.path.exists(CONFIG_SAMPLE_DIR):
        shutil.copytree(CONFIG_SAMPLE_DIR, CONFIG_DIR)
    else:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        # Migration from v2 (root) to v3 (config/ folder)
        for f in ['config.json', 'child_info.json', 'schedule.json', 'whitelist.json']:
            old_path = os.path.join(BASE_DIR, f)
            if os.path.exists(old_path):
                shutil.move(old_path, os.path.join(CONFIG_DIR, f))

os.makedirs(DATA_DIR, exist_ok=True)
# Migration for data files
for f in ['net_log.txt', 'activity_log.jsonl', 'restricted.json', 'net_timer.json', 'state.json', 'cmd.json', 'result.txt']:
    old_path = os.path.join(BASE_DIR, f)
    if os.path.exists(old_path):
        shutil.move(old_path, os.path.join(DATA_DIR, f))

CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
"""Path to main config (token, API key, ports)."""

CHILD_FILE    = os.path.join(CONFIG_DIR, 'child_info.json')
"""Path to child account info (username, nickname)."""

SCHEDULE_FILE = os.path.join(CONFIG_DIR, 'schedule.json')
"""Path to weekly schedule (blocking time blocks)."""

TIMER_FILE    = os.path.join(DATA_DIR, 'net_timer.json')
"""Path to manual /off timer state."""

LOG_FILE      = os.path.join(DATA_DIR, 'net_log.txt')
"""Path to centralized system log."""

ACTIVITY_FILE = os.path.join(DATA_DIR, 'activity_log.jsonl')
"""Path to activity log (JSON Lines: 1 JSON object per line)."""

RESTRICTED_FILE = os.path.join(DATA_DIR, 'restricted.json')
"""Path to Restricted Mode state file."""



def _load_config():
    """Read config.json and return dict."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = _load_config()

API_TOKEN  = CFG["telegram_token"]
"""Telegram Bot API token from @BotFather."""

ALLOWED_ID = CFG["allowed_id"]
"""Telegram user ID authorized to send commands."""

API_KEY    = CFG["api_key"]
"""Pre-shared key for HTTP API authentication."""

API_PORT   = CFG.get("api_port", 7890)
"""HTTP API server port (LAN control)."""

IPC_PORT   = CFG.get("ipc_port", 7891)
"""TCP socket port for Master-Eyes IPC (localhost only)."""

DEBUG_MODE = CFG.get("debug_mode", False)
"""If True, verbose logs are written. If False, only INFO/ERROR/WARNING."""

# =============================================================================
#  SECTION 2: CONSTANTS
# =============================================================================

POLLING_INTERVAL    = 30

POLLING_TIMEOUT     = 30
"""Telegram long-polling timeout in seconds."""

RECONNECT_DELAY     = 10
"""Seconds to wait before reconnecting after polling crash."""

DEDUP_MAX_SIZE      = 200
"""Max message IDs kept in dedup set before cleanup."""

STARTUP_RETRY_DELAY = 10
"""Seconds between startup notification retries."""

STARTUP_MAX_RETRIES = 20
"""Max attempts to send startup notification."""

SCHEDULE_CHECK_SEC  = 60
"""Schedule engine check interval in seconds."""

WATCHDOG_SEC        = 30
"""Watchdog check interval for Eyes process."""

ACTIVITY_SCAN_SEC   = 30
"""Activity logger scan interval in seconds."""

FW_RULE_OUT = "HarnessCore_Block"
"""Windows Firewall rule name for outbound blocking."""

FW_RULE_IN  = "HarnessCore_Block_In"
"""Windows Firewall rule name for inbound blocking."""

NOWINDOW = subprocess.CREATE_NO_WINDOW
"""Flag to hide console window when spawning subprocesses."""

CHILD_NOT_SET = "unKnown"
"""Default placeholder when child account is not configured."""

HIDDEN_PROCS = [
    "python", "pythonw", "cmd", "powershell", "svchost", "conhost",
    "taskhost", "wininit", "services", "lsass", "csrss", "smss",
    "winlogon", "dwm", "fontdrvhost", "sihost", "taskhostw",
]
"""Process names hidden from /list and activity log."""

CURRENT_PID = os.getpid()
"""PID of this process (for log tagging)."""

PROC_TYPE = "EYES" if "--eyes" in sys.argv else "MASTER"
"""Process role identifier (for log tagging)."""

# Startup notification settings
STARTUP_MAX_RETRIES    = 20
STARTUP_RETRY_DELAY    = 15

# =============================================================================
#  SECTION 3: TEXT STRINGS (Telegram messages, NO emoji)
# =============================================================================

MSG = {
    "MENU": (
        "<b>DANH MỤC - HC v3.0</b>\n\n"
        "-- Phần giám sát --\n"
        "1. /sshot - Chụp màn hình\n"
        "2. /list - Ứng dụng đang mở\n"
        "3. /report - Báo cáo hoạt động\n\n"
        "-- Phần Kiểm soát --\n"
        "1. /off [gio] - Chặn internet (hẹn giờ)\n"
        "2. /on - Mở internet ngay\n"
        "3. /lock - Khóa màn hình\n"
        "4. /block - Cấm đăng nhập\n"
        "5. /unblock - Mở đăng nhập\n\n"
        "-- Phần Lịch chặn --\n"
        "1. /sch - Xem lịch tuần\n"
        "2. /sch_on - Bật lịch | /sch_off - Tắt lịch\n"
    ),
    "STARTUP": "🤖 <b>{child} vừa bật máy tính!</b>\n\n⏰ Lúc: {time}",
    "SCH_BLOCKED": "🚫 <b>Lịch chặn #{bid}</b> đang có hiệu lực (từ {start} đến {end}).\nĐã tự động chuyển sang Cấp độ 2 (Học tập).",
    "SCH_UNBLOCKED": "✅ Đã hết giờ chặn theo lịch.\nĐã khôi phục Cấp độ 0 (Tự do).",
    "SCH_OFF": "Đã <b>TẮT</b> lịch chặn tự động.",
    "ALLOW_OK": "Đã mở khóa Internet tạm thời trong <b>{mins} phút</b>.",
    "LOCKED": "🔒 Đã khóa màn hình thành công.",
    "CMD_ERR": "❌ Lỗi thực thi lệnh: {e}"
}




# =============================================================================
#  SECTION 4: LOGGING
# =============================================================================

def log_event(msg, level="INFO"):
    """Write timestamped log entry to LOG_FILE."""
    import time
    if level == "DEBUG" and not DEBUG_MODE:
        return
    try:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] [{PROC_TYPE}:{CURRENT_PID}] [{level}] {msg}\n")
    except Exception:
        pass

def wipe_logs():
    """Clear the contents of the log file."""
    import time
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Log wiped by user.\n")
        return True
    except:
        return False

# =============================================================================
#  SECTION 5: SYSTEM PROTECTION (Mutex, Dedup)
# =============================================================================

def is_another_master_running():
    """Use Windows Global Mutex to prevent duplicate Master across sessions."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, "Global\\HarnessCore_Master_Mutex")
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return True
    return handle == 0

def is_another_eyes_running():
    """Use Windows Global Mutex to prevent duplicate Eyes process."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, "Global\\HarnessCore_Eyes_Mutex")
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return True
    return handle == 0

import threading
_processed_ids = set()
_dedup_lock = threading.Lock()

def is_duplicate(mid):
    """Check if Telegram message_id was already processed (anti-replay)."""
    global _processed_ids
    with _dedup_lock:
        if mid in _processed_ids:
            return True
        _processed_ids.add(mid)
        if len(_processed_ids) > DEDUP_MAX_SIZE:
            oldest = sorted(_processed_ids)[:DEDUP_MAX_SIZE // 2]
            _processed_ids.difference_update(oldest)
        return False

# =============================================================================
#  SECTION 6: DATA PERSISTENCE
# =============================================================================

def save_child_info(account, nickname=None):
    """Save child account mapping to CHILD_FILE."""
    import json
    if not nickname:
        nickname = account.capitalize()
    with open(CHILD_FILE, "w", encoding="utf-8") as f:
        json.dump({"nickname": nickname, "account": account}, f, ensure_ascii=False)

def get_child_info():
    """Return (account, nickname) tuple from CHILD_FILE."""
    import os, json
    if os.path.exists(CHILD_FILE):
        try:
            with open(CHILD_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("account", CHILD_NOT_SET), d.get("nickname", CHILD_NOT_SET)
        except Exception:
            pass
    return CHILD_NOT_SET, CHILD_NOT_SET

def save_net_timer(hours, chat_id):
    """Persist manual /off timer to TIMER_FILE."""
    import time, json
    with open(TIMER_FILE, "w") as f:
        json.dump({"end_time": time.time() + hours * 3600, "chat_id": chat_id}, f)

def get_timer_info():
    """Return (remaining_seconds, chat_id) from TIMER_FILE."""
    import os, json, time
    if os.path.exists(TIMER_FILE):
        try:
            with open(TIMER_FILE, "r") as f:
                d = json.load(f)
                return d.get("end_time", 0) - time.time(), d.get("chat_id", ALLOWED_ID)
        except Exception:
            pass
    return 0, ALLOWED_ID

def clear_net_timer():
    """Delete TIMER_FILE if exists."""
    import os
    if os.path.exists(TIMER_FILE):
        try:
            os.remove(TIMER_FILE)
        except Exception:
            pass

def load_schedule():
    """Read SCHEDULE_FILE. Returns dict with 'enabled' and 'blocks' list."""
    import os, json
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"enabled": False, "blocks": []}

def save_schedule(data):
    """Write schedule dict to SCHEDULE_FILE."""
    import json
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =============================================================================
#  SECTION 7: FIREWALL CONTROL
# =============================================================================

def block_internet():
    """Add Windows Firewall rules to block internet (keep LAN alive)."""
    import subprocess
    log_event("Firewall: blocking internet...")
    subprocess.run(
        f'powershell -Command "New-NetFirewallRule -DisplayName {FW_RULE_OUT}'
        f' -Direction Outbound -Action Block -RemoteAddress Internet'
        f' -ErrorAction SilentlyContinue"',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000)
    subprocess.run(
        f'powershell -Command "New-NetFirewallRule -DisplayName {FW_RULE_IN}'
        f' -Direction Inbound -Action Block -RemoteAddress Internet'
        f' -ErrorAction SilentlyContinue"',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000)
    log_event("Firewall: internet blocked.")

def unblock_internet():
    """Remove HarnessCore firewall rules to restore internet."""
    import subprocess
    log_event("Firewall: unblocking internet...")
    subprocess.run(
        f'powershell -Command "Remove-NetFirewallRule -DisplayName {FW_RULE_OUT}'
        f' -ErrorAction SilentlyContinue"',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000)
    subprocess.run(
        f'powershell -Command "Remove-NetFirewallRule -DisplayName {FW_RULE_IN}'
        f' -ErrorAction SilentlyContinue"',
        shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000)
    log_event("Firewall: internet unblocked.")

def is_internet_blocked():
    """Check if HarnessCore firewall blocking rule is currently active."""
    import subprocess
    try:
        out = subprocess.run(
            f'powershell -Command "Get-NetFirewallRule -DisplayName {FW_RULE_OUT}'
            f' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Enabled"',
            shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        ).stdout.decode().strip()
        return out == "True"
    except Exception:
        return False
