# 📘 TÀI LIỆU HƯỚNG DẪN HỆ THỐNG SAFETY KIDS (HARNESSCORE v3.0)

Hệ thống quản lý, giám sát và kiểm soát máy tính từ xa đa kênh dành cho tài khoản Standard/Local User trên Windows.

---

## 🏗️ I. KIẾN TRÚC & 3 KÊNH ĐIỀU KHIỂN

```
                    +--------------------------------+
                    |        NGƯỜI QUẢN TRỊ          |
                    +--------------------------------+
                       /            |             \
                      /             |              \
           (1) Telegram     (2) Web cPanel     (3) Local API
              (Global)          (LAN/Web)        (Direct LAN)
                    \               |              /
                     v              v             v
       +-------------------------------------------------------+
       |                   MÁY TÍNH ĐÍCH (CLIENT)                |
       |                                                       |
       |  [Task 1: SYSTEM] Safety_Kids_Master (hc_master.py)   |
       |    ├── Lắng nghe Telegram Bot                         |
       |    ├── Gõ cửa kéo lệnh & gửi Heartbeat (mỗi 9s)       |
       |    ├── Mở cổng HTTP Server (Port [api_port])                |
       |    ├── Xử lý Cấp độ, Block/Whitelist, Khóa Mạng       |
       |    └── IPC Server giao tiếp với Eyes (Port [ipc_port])      |
       |                                                       |
       |  [Task 2: SYSTEM] Windows_System_Helper               |
       |    └── Watchdog cảm tử: Tự động hồi sinh Master       |
       |                                                       |
       |  [Task 3: USER]   Safety_Kids_Eyes (hc_eyes.py)       |
       |    └── Chụp màn hình, quét URL trình duyệt Chrome/Edge|
       +-------------------------------------------------------+
```

---

## 🎚️ II. BẢN ĐỒ PHÂN BIỆT 3 CẤP ĐỘ (LEVELS) & LỊCH TRÌNH (SCHEDULE)

*(Lưu ý: Hệ thống đã nâng cấp lên cơ chế kiểm soát Nhị phân (Play/Study) thay vì Blacklist nửa vời, loại bỏ hoàn toàn Cấp 1)*.

### 1. Ý nghĩa 3 Cấp Độ Chặn:
* **Cấp 0 (Thả Cửa - Free Mode):** Tắt hoàn toàn mọi rào chắn. Cho phép chơi game, lướt web tự do, tài khoản hoạt động bình thường. (Mặc định).
* **Cấp 2 (Học Tập - Whitelist / Restricted):** Chế độ tập trung 100%. Khóa sạch toàn bộ Web (chỉ mở các trang học tập trong `whitelist.json` như VioEdu, OLM, VnEdu...), đồng thời chặn hoàn toàn mọi Game.
* **Cấp 3 (Khẩn Cấp - Lockdown):** Tước quyền đăng nhập Windows (`net user /active:no`). Trẻ không thể đăng nhập vào máy tính được nữa cho tới khi phụ huynh mở khóa.

### 2. Mối liên hệ giữa Cấp Độ và Lịch Trình (Schedule):
Lịch trình tự động (`schedule.json`) là công tắc tự động luân chuyển giữa chế độ Giải Trí và chế độ Học Tập:
* Khi **Bật Lịch (`/sch_on`)**: 
  * **Ngoài giờ học:** Hệ thống tự động chuyển về **Cấp 0 (Thả cửa)**.
  * **Đến giờ học (VD: 17:30 - 19:30):** Hệ thống tự động kích hoạt **Cấp 2 (Học tập nghiêm ngặt)**.
* Khi **Tắt Lịch (`/sch_off` hoặc sau khi Khôi phục lỗi)**: 
  * Hệ thống **ngừng luân chuyển tự động**, đứng yên ở Cấp độ do phụ huynh chỉ định bằng tay trên Web hoặc Telegram.

---

## 📡 III. CHI TIẾT 3 KÊNH ĐIỀU KHIỂN

### 1. KÊNH 1: TELEGRAM BOT (ĐIỀU KHIỂN TOÀN CẦU)
Điều khiển mọi lúc, mọi nơi thông qua chat với Telegram Bot.

#### 📋 Bảng tra cứu toàn bộ menu lệnh:

#### A. Điều khiển Cấp độ & Trạng thái:
* `/l0` hoặc `/level0` : Chuyển sang Cấp 0 (Thả cửa hoàn toàn).
* `/l2` hoặc `/level2` : Chuyển sang Cấp 2 (Chỉ cho học tập).
* `/l3` hoặc `/level3` : Chuyển sang Cấp 3 (Khóa máy khẩn cấp).

#### B. Giám sát & Báo cáo:
* `/sshot` : Chụp màn hình máy đích và gửi ảnh về Telegram.
* `/list` : Liệt kê danh sách các cửa sổ ứng dụng đang hiển thị.
* `/report` : Báo cáo tổng hợp thời gian sử dụng App/Web trong ngày.
* `/report YYYY-MM-DD` : Báo cáo hoạt động của một ngày cụ thể (VD: `/report 2026-08-24`).
* `/check` : Kiểm tra tình trạng kết nối, cấp độ hiện tại, trạng thái mạng, lịch chặn.

#### C. Điều khiển Mạng & Màn hình tức thời:
* `/lock` : Khóa màn hình ngay lập tức (LockWorkStation).
* `/off [số_giờ]` : Ngắt Internet nhưng **vẫn giữ mạng LAN nội bộ** (VD: `/off 0.5` = cắt 30 phút). 
* `/on` : Mở lại Internet ngay lập tức.
* `/sdown [số_giây]` : Tắt máy tính đích đếm ngược (VD: `/sdown 10`).

#### D. Quản lý Lịch trình chặn tự động:
* `/sch` : Xem danh sách lịch trình tự động trong tuần.
* `/sch_on` : Bật chế độ luân chuyển lịch.
* `/sch_off` : Tắt chế độ luân chuyển lịch.
* `/sch_add [ID] [Thứ] [Bắt đầu] [Kết thúc]` : Thêm lịch chặn (VD: `/sch_add 1 12345 22:00 24:00` -> Chặn T2-T6 từ 22h-24h).
* `/sch_del [ID]` : Xóa lịch chặn theo ID.
* `/allow [phút]` : Mở khóa tạm thời cho trẻ dùng trong `X` phút (VD: `/allow 30`).

#### E. Quản trị Hệ thống & Khắc phục sự cố:
* `/cmd [lệnh]` : Thực thi lệnh Command Prompt / PowerShell ngầm và trả về kết quả.
* `/set_child [username] [tên_gọi]` : Khai báo tài khoản Windows của trẻ (VD: `/set_child kid_username Tên_Của_Bé`).
* `/get_logs` : Tải file nhật ký hệ thống (`net_log.txt`).
* `/wipe_logs` : Xóa sạch nhật ký hệ thống.
* `/debug_on` / `/debug_off` : Bật / Tắt chế độ ghi log chi tiết.
* `/repair` : Khởi động lại các tiến trình ngầm nếu bị treo.
* `/stop_bot` : Tắt tiến trình Master để kích hoạt Watchdog phục hồi.

---

### 2. KÊNH 2: WEB DASHBOARD CPANEL (GIAO DIỆN NỘI BỘ/INTERNET)
Chạy trên nền PHP (môi trường Laragon/XAMPP hoặc Hosting).
* **Đường dẫn truy cập:** `http://[IP_MÁY_CHỦ_PHP]/.../Safety_Kids/Controller_Suite/web_cPanel/`
* **Giao diện 2 cột thông minh:**
  * **Cột trái (Bảng Điều Khiển):** 
    * Hiển thị Lớp phủ (Overlay) thông minh: Nếu máy đích tắt hoặc rớt mạng LAN, lớp phủ **🔴 MÁY TRẺ ĐANG OFFLINE** sẽ che toàn bộ khu vực thao tác. Khi máy trẻ online trở lại, lớp phủ tự tan biến.
    * 3 nút chuyển Cấp độ (0, 2, 3) tự động bắt nhịp tim của máy đích.
    * Bảng tác vụ nhanh: Khóa màn hình, Cắt mạng 30p, Mở mạng, Bật/Tắt Debug, Tải/Xóa Log.
  * **Cột phải (Remote Terminal):** Cửa sổ PowerShell trực quan, gõ lệnh nhấn `Enter` để chạy và xem kết quả trả về trực tiếp.

---

### 3. KÊNH 3: LOCAL LAN DIRECT API (CỔNG KHẨN CẤP [api_port])
Hoạt động độc lập trong mạng nội bộ WiFi/LAN, **không cần Internet**, không phụ thuộc Telegram hay máy chủ PHP.

* **Cổng dịch vụ:** `[api_port]`
* **Xác thực:** Tham số `key=[api_key]` (Mặc định: `YOUR_API_KEY_HERE`)
* **Cách sử dụng:** Gõ trực tiếp link vào trình duyệt (Chrome, Safari trên điện thoại, máy tính) kết nối cùng WiFi:

#### 🔗 Các URL mẫu:
1. **Khóa màn hình tức thì:** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=lock`
2. **Chuyển sang Cấp 0 (Thả cửa):** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=set_level&level=0`
3. **Chuyển sang Cấp 2 (Chỉ học tập):** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=set_level&level=2`
4. **Chuyển sang Cấp 3 (Lockdown):** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=set_level&level=3`
5. **Cắt mạng 30 phút:** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=off&hours=0.5`
6. **Mở lại mạng:** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=on`
7. **Kiểm tra trạng thái:** `http://[IP_Máy_trẻ]:[api_port]/api/command?key=YOUR_API_KEY_HERE&cmd=check`

---

## ⚙️ IV. HƯỚNG DẪN CÀI ĐẶT & TRIỂN KHAI TRÊN MÁY ĐÍCH (CLIENT)

1. **Chuẩn bị thư mục:** Copy toàn bộ nội dung trong `Deploy_to_Client` dán vào `C:\ProgramData\Safety_Kid`.
2. **Đăng ký Scheduled Tasks:** Mở PowerShell (Run as Administrator), chạy:
   ```powershell
   Set-Location "C:\ProgramData\Safety_Kid"
   powershell -ExecutionPolicy Bypass -File .\install_service.ps1
   ```
3. **Khởi động lại máy đích để kích hoạt toàn bộ.**

---

## 🛡️ V. CƠ CHẾ TỰ VỆ & BẢO MẬT NÂNG CAO

1. **Anti-Kill (Chống tắt tiến trình):** `win_sys_helper.py` giám sát liên tục `hc_master.py`. Nếu Master bị tắt, Helper sẽ bắn cảnh báo Telegram và khởi chạy lại Master trong vòng 30 - 75s.
2. **Anti-Admin Elevation (Chống hack nâng quyền):** Định kỳ kiểm tra nhóm `Administrators`. Nếu tài khoản trẻ tự nâng lên quyền Admin, hệ thống tự động giáng cấp về Standard User.
3. **Anti-Tamper Backdoor:** Kiểm tra tính toàn vẹn của các file hệ thống trợ năng (`utilman.exe`, `sethc.exe`). Nếu phát hiện bị tráo đổi, tự động kích hoạt `sfc /scanfile` để khôi phục.
4. **Stealth Telemetry:** Trích xuất lịch sử duyệt web trực tiếp từ file database SQLite của Chrome/Edge, không phụ thuộc vào việc trẻ xóa lịch sử hay lướt ẩn danh.

---

## 🚑 VI. KỊCH BẢN CỨU CÁNH TỪ XA QUA TELEGRAM (REMOTE HOT-PATCHING)

Khi máy đích gặp lỗi cấu hình hoặc mất đồng bộ mà người quản trị **không thể tiếp cận máy trực tiếp**:
1. **Chỉnh sửa file cấu hình từ xa (bằng Python một dòng):**
   ```text
   /cmd python -c "import json; p=r'C:\ProgramData\Safety_Kid\config.json'; f=open(p,'r',encoding='utf-8'); d=json.load(f); f.close(); d['cpanel_url']='http://192.168.1.xxx/03_Lab/proc/Safety_Kids/Controller_Suite/web_cPanel'; f=open(p,'w',encoding='utf-8'); json.dump(d,f,indent=2); f.close(); print('CONFIG_OK')"
   ```
2. **Kích hoạt Watchdog tái sinh hệ thống:**
   ```text
   /stop_bot
   ```
   *Tiến trình Master tự dừng, Watchdog `win_sys_helper.py` sẽ phát hiện và khởi động lại Master với cấu hình mới sau 30-75 giây.*

---

## 🤖 VII. ĐIỀU KHIỂN & CẬP NHẬT OTA TỰ ĐỘNG BỞI AI AGENT (ANTIGRAVITY)

Khi hệ thống đã thông suốt cả 3 kênh:
1. **AI Chụp màn hình & Đọc dữ liệu trực tiếp:** AI có thể gửi lệnh `sshot` qua Web API, trích xuất Base64 trả về và render ảnh chụp màn hình máy tính của trẻ ngay trong phiên làm việc.
2. **Nâng cấp mã nguồn Over-The-Air (OTA) không chạm:**
   * AI tự biên soạn code mới trên máy chủ Laragon.
   * AI bắn lệnh ngầm qua Web API yêu cầu máy đích tự kéo code mới về đè lên thư mục `C:\ProgramData\Safety_Kid\`.
   * AI gửi lệnh `wmic process where "name='pythonw.exe' and commandline like '%hc_master.py%'" call terminate` để tái khởi động Master ngầm mà không cần can thiệp thủ công từ người dùng. Mọi thao tác hoàn toàn trong suốt.


