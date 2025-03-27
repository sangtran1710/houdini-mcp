# HoudiniMCP - Houdini Model Context Protocol Integration

HoudiniMCP kết nối Houdini với Claude AI thông qua Model Context Protocol (MCP), cho phép Claude trực tiếp tương tác và điều khiển Houdini. Tích hợp này giúp tạo mô phỏng nước, lửa, và các hiệu ứng khác thông qua lệnh văn bản.

## Tính năng

- **Giao tiếp hai chiều**: Kết nối Claude AI với Houdini thông qua máy chủ socket
- **Thao tác đối tượng**: Tạo, sửa đổi, và xóa các đối tượng 3D trong Houdini
- **Quản lý vật liệu**: Áp dụng và sửa đổi vật liệu và màu sắc
- **Mô phỏng nước**: Tạo và điều khiển mô phỏng chất lỏng với FLIP Solver
- **Mô phỏng lửa và khói**: Tạo và điều khiển mô phỏng lửa và khói với Pyro Solver
- **Kiểm tra cảnh**: Lấy thông tin chi tiết về cảnh Houdini hiện tại
- **Thực thi mã**: Chạy mã Python tùy ý trong Houdini từ Claude

## Thành phần

Hệ thống gồm hai thành phần chính:

1. **Plugin Houdini (`houdini_plugin.py`)**: Plugin Houdini tạo máy chủ socket trong Houdini để nhận và thực thi lệnh
2. **Máy chủ MCP (`src/houdini_mcp/server.py`)**: Máy chủ Python triển khai Model Context Protocol và kết nối với plugin Houdini

## Cài đặt

### Yêu cầu

- Houdini 18.0 hoặc mới hơn
- Python 3.10 hoặc mới hơn
- Trình quản lý gói uv:

**Trên Mac**
```bash
brew install uv
```

**Trên Windows**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```
và sau đó
```bash
set Path=C:\Users\username\.local\bin;%Path%
```

Hoặc tham khảo hướng dẫn tại: [Cài đặt uv](https://docs.astral.sh/uv/getting-started/installation/)

### Tích hợp Claude cho Desktop

Vào Claude > Settings > Developer > Edit Config > claude_desktop_config.json để thêm:

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

### Tích hợp Cursor

Chạy houdini-mcp không cần cài đặt vĩnh viễn qua uvx. Vào Cursor Settings > MCP và dán lệnh này:

```bash
uvx houdini-mcp
```

Với người dùng Windows, vào Settings > MCP > Add Server, thêm một máy chủ mới với cài đặt:

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

**⚠️ Chỉ chạy một phiên bản của máy chủ MCP (hoặc trên Cursor hoặc Claude Desktop), không phải cả hai**

### Cài đặt Plugin Houdini

1. Tải tệp `houdini_plugin.py` từ repo này
2. Đặt tệp vào thư mục script của Houdini:
   - Windows: `C:\Users\<username>\Documents\houdini19.5\scripts\`
   - Mac: `/Users/<username>/Library/Preferences/houdini/19.5/scripts/`
   - Linux: `/home/<username>/houdini19.5/scripts/`
3. Trong Houdini, mở Python Shell và chạy:
   ```python
   import houdini_plugin
   houdini_plugin.show_dialog()
   ```
4. Hoặc thêm vào menu của Houdini bằng cách tạo tệp shelf tool chạy lệnh trên

## Sử dụng

### Bắt đầu kết nối

1. Trong Houdini, chạy plugin như hướng dẫn ở trên
2. Trong hộp thoại hiện ra, click "Connect to Claude"
3. Đảm bảo máy chủ MCP đang chạy trong terminal của bạn

### Sử dụng với Claude

Khi tệp cấu hình đã được thiết lập trên Claude, và plugin đang chạy trên Houdini, bạn sẽ thấy biểu tượng công cụ cho HoudiniMCP.

#### Khả năng

- Lấy thông tin cảnh và đối tượng
- Tạo, xóa và chỉnh sửa các đối tượng
- Tạo mô phỏng chất lỏng với FLIP Solver
- Tạo mô phỏng lửa và khói với Pyro Solver
- Chạy mô phỏng trong khung thời gian chỉ định
- Thực thi mã Python tùy ý trong Houdini

### Ví dụ lệnh

Dưới đây là một số ví dụ về những gì bạn có thể yêu cầu Claude thực hiện:

- "Tạo mô phỏng nước đổ vào một cái cốc"
- "Tạo hiệu ứng lửa bao quanh một quả cầu"
- "Tạo một cột khói bay lên từ một ống khói"
- "Lấy thông tin về cảnh hiện tại"
- "Tạo một đối tượng hình khối và đặt nó ở trung tâm"
- "Tạo một vật liệu kim loại màu đỏ và áp dụng nó cho đối tượng"

## Xử lý sự cố

- **Vấn đề kết nối**: Đảm bảo máy chủ plugin Houdini đang chạy, và máy chủ MCP được cấu hình trên Claude. KHÔNG chạy lệnh uvx trong terminal.
- **Lỗi timeout**: Thử đơn giản hóa yêu cầu của bạn hoặc chia nhỏ chúng thành các bước nhỏ hơn.
- **Bạn đã thử tắt và bật lại?**: Nếu bạn vẫn gặp lỗi kết nối, hãy thử khởi động lại cả Claude và máy chủ Houdini.

## Chi tiết kỹ thuật

### Giao thức giao tiếp

Hệ thống sử dụng giao thức đơn giản dựa trên JSON qua socket TCP:

- **Lệnh** được gửi dưới dạng các đối tượng JSON với `type` và `params` tùy chọn
- **Phản hồi** là các đối tượng JSON với `status` và `result` hoặc `message`

## Giới hạn & Cân nhắc bảo mật

- Công cụ `execute_houdini_code` cho phép chạy mã Python tùy ý trong Houdini, có thể mạnh mẽ nhưng tiềm ẩn nguy hiểm. Sử dụng cẩn thận trong môi trường sản xuất. LUÔN lưu công việc của bạn trước khi sử dụng.
- Các thao tác phức tạp có thể cần được chia thành các bước nhỏ hơn.

## Đóng góp

Đóng góp luôn được chào đón! Vui lòng gửi Pull Request. 