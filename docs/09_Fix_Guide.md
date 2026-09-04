# Hướng dẫn Khắc phục & Tránh lỗi Hệ thống (Fix Guide)

## 1. Lỗi Font chữ tiếng Việt (Mojibake)
- **Triệu chứng:** Các ký tự tiếng Việt có dấu bị biến thành `Ä Ã£`, `âš`, `há» c` trên Telegram hoặc file log.
- **Nguyên nhân cốt lõi:** Hệ điều hành Windows mặc định sử dụng bảng mã ANSI (cp1252/cp1258) cho các tác vụ đọc/ghi file nếu không được chỉ định rõ ràng. Khi Python hoặc PowerShell can thiệp vào file chứa tiếng Việt (UTF-8) mà không ép kiểu, dữ liệu sẽ bị mã hóa sai lệch thành Mojibake.
- **Kỹ thuật phòng tránh & Khắc phục (Coding Standard):**
  1. **Tuyệt đối không** dùng lệnh PowerShell/CMD thuần (như `echo`, `Select-String`, `-replace`) để sửa trực tiếp file code chứa chuỗi tiếng Việt.
  2. **Luôn luôn** dùng Python script để thao tác file, và BẮT BUỘC phải truyền tham số `encoding="utf-8"`:
     ```python
     with open("file.py", "r", encoding="utf-8") as f:
         content = f.read()
     # ... thao tác ...
     with open("file.py", "w", encoding="utf-8") as f:
         f.write(content)
     ```
  3. Nếu cần in tiếng Việt ra console (stdout) để debug, phải ép kiểu terminal:
     ```python
     import sys
     sys.stdout.reconfigure(encoding='utf-8')
     ```
  4. Tránh dùng Regex (Regular Expression) phức tạp để thay thế string tiếng Việt nếu không thiết lập cờ UNICODE. Ưu tiên ghi đè file hoặc dùng index byte/string cứng.
