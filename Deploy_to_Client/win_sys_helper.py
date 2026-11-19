"""HarnessCore v3.0 - Windows System Helper Process (SYSTEM session).

Monitors hc_master.py. If master is killed, creates a recovery flag file,
sends a Telegram alert, and restarts master.
"""
import os
import sys
# Allow importing hc_config when helper is placed in system32 or other folders
sys.path.insert(0, r"C:\ProgramData\Safety_Kid")

import time
import ctypes
import subprocess
import urllib.request
import urllib.parse
from hc_config import *

FLAG_FILE = os.path.join(BASE_DIR, "Temp", "win_sys_state.tmp")

def check_mutex_running(name):
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, True, name)
    err = kernel32.GetLastError()
    if handle:
        kernel32.CloseHandle(handle)
    return err == 183

def send_telegram_alert(msg):
    import ssl
    url = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": ALLOWED_ID,
        "text": msg,
        "parse_mode": "html"
    }).encode('utf-8')
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10, context=context) as resp:
            pass
        log_event("Helper: Telegram alert sent.")
    except Exception as e:
        log_event(f"Helper: Failed to send Telegram alert: {e}", "ERROR")

def create_recovery_flag():
    try:
        temp_dir = os.path.dirname(FLAG_FILE)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        with open(FLAG_FILE, 'w') as f:
            f.write(str(time.time()))
        log_event("Helper: Recovery flag file created.")
    except Exception as e:
        log_event(f"Helper: Failed to create flag file: {e}", "ERROR")

def helper_main_loop():
    # Keep helper Mutex alive to identify this running process
    kernel32 = ctypes.windll.kernel32
    helper_handle = kernel32.CreateMutexW(None, True, "Global\\Windows_System_Helper_Mutex")
    if kernel32.GetLastError() == 183:
        log_event("Helper: Another instance holds Mutex. Exiting.", "WARNING")
        sys.exit(0)

    log_event("Helper: Watchdog started (Mutex acquired).")
    
    # Wait 45 seconds to let Master initialize and stagger checks
    time.sleep(45)

    while True:
        try:
            # Check if Master process is alive
            if not check_mutex_running("Global\\HarnessCore_Master_Mutex"):
                log_event("Helper: Master is OFFLINE. Triggering recovery...", "WARNING")
                
                # Create recovery flag
                create_recovery_flag()

                # Send Alert
                ts = time.strftime('%H:%M:%S %d/%m/%Y')
                msg = f"<b>⚠️ CẢNH BÁO:</b> Tiến trình Master đã dừng hoạt động lúc <code>{ts}</code>! Đang tiến hành khôi phục..."
                send_telegram_alert(msg)

                # Restart Master
                subprocess.run('schtasks /run /tn "Safety_Kids_Master"', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                log_event("Helper: Command to restart Master sent.")

                # Wait 45 seconds to allow Master to fully initialize
                time.sleep(45)
        except Exception as e:
            log_event(f"Helper Loop Error: {e}", "ERROR")
        
        # Scan every 30 seconds to minimize CPU usage
        time.sleep(30)

if __name__ == "__main__":
    helper_main_loop()
