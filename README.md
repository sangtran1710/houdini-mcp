# HoudiniMCP - Houdini Model Context Protocol Integration

HoudiniMCP kết nối Houdini với Claude AI thông qua Model Context Protocol (MCP), cho phép Claude điều khiển trực tiếp và tương tác với Houdini. Tích hợp này giúp bạn thực hiện các lệnh bằng văn bản để tạo mô phỏng, dựng cảnh và thao tác với Houdini.

### Tham gia cộng đồng

Đóng góp ý kiến, lấy cảm hứng và phát triển dựa trên MCP: [Discord](https://discord.gg/xcJxvuW6)

## Tính năng

- **Giao tiếp hai chiều**: Kết nối Claude AI với Houdini thông qua socket server
- **Thao tác đối tượng**: Tạo, chỉnh sửa và xóa các đối tượng 3D trong Houdini
- **Điều khiển mô phỏng**: Tạo và điều chỉnh các mô phỏng nước và lửa
- **Kiểm tra cảnh**: Lấy thông tin chi tiết về cảnh hiện tại trong Houdini
- **Thực thi mã**: Chạy mã Python tùy ý trong Houdini từ Claude

## Thành phần

Hệ thống bao gồm hai thành phần chính:

1. **Houdini Plugin (`houdini_plugin.py`)**: Plugin tạo socket server trong Houdini để nhận và thực thi lệnh
2. **MCP Server (`src/houdini_mcp/server.py`)**: Server Python triển khai Model Context Protocol và kết nối với Houdini plugin

## Cài đặt

### Yêu cầu

- Houdini 19.5 hoặc mới hơn
- Python 3.10 hoặc mới hơn
- uv package manager: 

**Nếu bạn đang dùng Mac, cài đặt uv bằng lệnh**
```bash
brew install uv
```
**Trên Windows**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex" 
```
sau đó
```bash
set Path=C:\Users\<username>\.local\bin;%Path%
```

**⚠️ Không tiếp tục nếu chưa cài đặt UV**

### Cài đặt plugin cho Houdini

1. Tải file `houdini_plugin.py`
2. Copy file này vào thư mục scripts của Houdini:
   - Windows: `C:\Users\<username>\Documents\houdini<version>\scripts\`
   - Mac: `/Users/<username>/Library/Preferences/houdini/<version>/scripts/`
   - Linux: `/home/<username>/houdini<version>/scripts/`
3. Mở Houdini, nhấn Alt+P để mở Python Shell
4. Chạy các lệnh sau:
   ```python
   import houdini_plugin
   houdini_plugin.show_dialog()
   ```

### Tích hợp với Claude Desktop

Vào Claude > Settings > Developer > Edit Config > claude_desktop_config.json và thêm đoạn sau:

```json
{
    "mcpServers": {
        "houdini": {
            "command": "uvx",
            "args": [
                "houdini-mcp"
            ]
        }
    }
}
```

### Tích hợp với Cursor

Vào Cursor Settings > MCP và dán lệnh sau:

```bash
uvx houdini-mcp
```

Đối với người dùng Windows, vào Settings > MCP > Add Server, thêm server mới với cài đặt sau:

```json
{
    "mcpServers": {
        "houdini": {
            "command": "cmd",
            "args": [
                "/c",
                "uvx",
                "houdini-mcp"
            ]
        }
    }
}
```

**⚠️ Chỉ chạy một instance của MCP server (hoặc trên Cursor hoặc Claude Desktop), không chạy cả hai**

## Sử dụng

### Bắt đầu kết nối

1. Trong Houdini, mở Python Shell (Alt+P)
2. Chạy lệnh `import houdini_plugin` và `houdini_plugin.show_dialog()`
3. Kết nối đến Claude
4. Đảm bảo MCP server đang chạy

### Sử dụng với Claude

Khi đã cấu hình xong file config cho Claude, và plugin đang chạy trong Houdini, bạn sẽ thấy biểu tượng công cụ cho HoudiniMCP.

#### Khả năng

- Lấy thông tin về cảnh và đối tượng
- Tạo, xóa và chỉnh sửa các đối tượng
- Tạo mô phỏng nước và lửa
- Thực thi mã Python bất kỳ trong Houdini

### Ví dụ các lệnh

Dưới đây là một số ví dụ về những gì bạn có thể yêu cầu Claude thực hiện:

- "Tạo mô phỏng nước với nguồn hình hộp và một quả cầu va chạm"
- "Tạo mô phỏng lửa với nguồn hình cầu, nhiệt độ 1.5, lượng nhiên liệu 1.0 và lực gió theo hướng X"
- "Tạo một đối tượng hình cầu và đặt nó phía trên hình hộp"
- "Hướng camera vào cảnh"

## Xử lý sự cố

- **Vấn đề kết nối**: Đảm bảo Houdini plugin server đang chạy và MCP server được cấu hình trên Claude
- **Lỗi timeout**: Thử đơn giản hóa yêu cầu hoặc chia nhỏ thành các bước
- **Kết nối không ổn định**: Khởi động lại cả Claude và Houdini server

## Chi tiết kỹ thuật

### Giao thức truyền thông

Hệ thống sử dụng giao thức dựa trên JSON qua TCP sockets:

- **Lệnh** được gửi dưới dạng đối tượng JSON với `type` và `params` tùy chọn
- **Phản hồi** là đối tượng JSON với `status` và `result` hoặc `message`

## Giới hạn và cân nhắc bảo mật

- Công cụ `execute_houdini_code` cho phép chạy mã Python tùy ý trong Houdini, điều này rất mạnh mẽ nhưng có thể nguy hiểm. Sử dụng cẩn thận trong môi trường sản xuất. LUÔN lưu công việc của bạn trước khi sử dụng.
- Các thao tác phức tạp có thể cần được chia thành các bước nhỏ hơn

## Đóng góp

Đóng góp luôn được chào đón! Vui lòng tạo Pull Request.

## Tuyên bố từ chối trách nhiệm

Đây là tích hợp của bên thứ ba và không phải do SideFX (công ty phát triển Houdini) tạo ra.
