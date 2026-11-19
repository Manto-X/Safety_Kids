import urllib.request
import json
import sys

def send_local_command(ip, port, level):
    url = f"http://{ip}:{port}/api/command"
    data = json.dumps({"command": "set_level", "args": {"level": level}}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'X-API-Key': 'YOUR_API_KEY_HERE'})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode())
            print("Thành công:", res)
    except Exception as e:
        print("Lỗi kết nối:", e)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Sử dụng: python lan_controller.py <IP_MAY_DICH> <PORT> <LEVEL>")
        print("Ví dụ: python lan_controller.py 192.168.1.100 7890 2")
        sys.exit(1)
        
    ip = sys.argv[1]
    port = sys.argv[2]
    level = int(sys.argv[3])
    
    print(f"Gửi lệnh chuyển sang Cấp {level} tới {ip}:{port}...")
    send_local_command(ip, port, level)
