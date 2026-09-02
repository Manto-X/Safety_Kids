# 🛡️ Safety Kids (HarnessCore v3.0)

Một hệ thống tự động hóa mạnh mẽ giúp phụ huynh giám sát, quản lý thời gian và kiểm soát nội dung trên máy tính Windows của trẻ nhỏ. Hệ thống được thiết kế với cơ chế "Tự vệ" (Anti-Kill) vững chắc và khả năng điều khiển đa kênh mượt mà.

## ✨ Tính năng Nổi bật

* 🎚️ **Kiểm soát Nhị phân (Binary Levels):** Đơn giản hóa việc quản lý với 3 trạng thái: 
  * **Cấp 0 (Thả cửa)**: Tự do học tập & giải trí.
  * **Cấp 2 (Học tập)**: Khóa toàn bộ Game, chỉ cho phép truy cập các website học tập (Whitelist).
  * **Cấp 3 (Khẩn cấp)**: Tước quyền truy cập máy tính ngay lập tức.
* 🕒 **Lịch trình Tự động (Smart Scheduler):** Tự động chuyển đổi giữa giờ Chơi và giờ Học theo các block thời gian đã cài đặt trước.
* 🌐 **Điều khiển Đa Kênh:**
  * **Telegram Bot:** Quản lý toàn cầu từ xa (Khóa máy, cắt/mở mạng, lấy ảnh chụp màn hình, kiểm tra trạng thái).
  * **Web cPanel:** Giao diện điều khiển trực quan qua mạng LAN, tích hợp Remote Terminal.
  * **Local API:** Điều khiển tức thời qua cổng API nội bộ (không cần Internet).
* 🛡️ **Cơ chế Tự vệ (Self-Defense):**
  * **Watchdog Cảm tử:** Liên tục giám sát và hồi sinh bộ điều khiển trung tâm nếu bị tắt ép buộc.
  * **Chống Nâng Quyền (Anti-Admin):** Tự động giáng cấp nếu trẻ cố tình cấp quyền Administrator cho tài khoản của mình.
* 🕵️ **Giám sát Ngầm (Stealth Telemetry):** Trích xuất lịch sử duyệt web trực tiếp từ SQLite của trình duyệt (vượt qua chế độ ẩn danh/xóa lịch sử) và chụp ảnh màn hình từ xa.

## 🚀 Cài đặt Nhanh (Getting Started)

1. **Chuẩn bị cấu hình:**
   * Đổi tên config.example.json thành config.json và điền Token Telegram Bot, API Key của bạn.
   * Đổi tên child_info.example.json thành child_info.json và điền username Windows của trẻ.
2. **Triển khai lên máy đích (Máy của trẻ):**
   * Copy toàn bộ nội dung thư mục Deploy_to_Client vào C:\ProgramData\Safety_Kid.
   * Mở PowerShell (Quyền Admin) và chạy: powershell -ExecutionPolicy Bypass -File .\install_service.ps1
3. **Quản trị Web cPanel (Tùy chọn):**
   * Đưa thư mục Controller_Suite\web_cPanel lên một máy chủ web (VD: Laragon/XAMPP) trong cùng mạng LAN.

## 📖 Tài liệu Hướng dẫn

Vui lòng đọc kỹ file [USER_GUIDE.md](docs/USER_GUIDE.md) để hiểu rõ:
* Cấu trúc hệ thống và luồng giao tiếp.
* Bảng tra cứu toàn bộ menu lệnh Telegram.
* Kịch bản xử lý sự cố và cứu cánh từ xa.

## ⚠️ Lưu ý Pháp lý & Đạo đức
Dự án này được thiết kế ĐỘC QUYỀN cho mục đích hỗ trợ phụ huynh quản lý máy tính cá nhân của con cái trong gia đình. Vui lòng không sử dụng mã nguồn này vào bất kỳ mục đích nào xâm phạm quyền riêng tư hợp pháp của người khác.




## 📝 Changelog
* **v3.0.1 (Sep 2026)**: Vá lỗi vòng lặp Watchdog (Anti-Kill Loop), tối ưu logic hạ quyền Admin (chỉ nhắm vào tài khoản con), sửa lỗi kẹt Policy Chrome/Edge khi thoát Restricted Mode.
