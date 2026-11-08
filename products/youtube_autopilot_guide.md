# 🤖 Hướng Dẫn Cầm Tay Chỉ Việc: Kết Nối Tự Động Đăng Kênh YouTube 24/7 (`YOUTUBE_REFRESH_TOKEN`)

Hệ thống đám mây **GitHub Actions** tại `.github/workflows/video_factory.yml` đã được nâng cấp toàn diện cho **6 tháng nội dung (96 kịch bản — Quý 1 & Quý 2)**:

- **Tự động Render Giọng Đọc Mỹ (`en-US-ChristopherNeural`) + Chuyển Động Ken Burns + Nhạc Nền Bản Quyền Sạch**: Toàn bộ video `.mp4`, phụ đề `.srt`, Thumbnail độ tương phản cao, mô tả SEO kèm mã Amazon `mindandmarg06-20`, và bình luận tiếp thị đầu tiên đều được xử lý tự động 100%.
- **Chế độ Lịch hẹn thông minh (`cron` siêu tốc < 90 giây)**: Cứ **20:00 tối Thứ 3, Thứ 5, Thứ 7 và Chủ nhật** (giờ Việt Nam — đúng 08:00–09:00 sáng giờ Mỹ có giá quảng cáo RPM cao nhất), máy chủ GitHub chỉ render đúng 1 video tiếp theo trong hàng đợi và tự động đăng lên kênh YouTube của bạn!

---

## ⚡ 3 Bước Cài Đặt Duy Nhất (Chỉ làm 1 lần — Mất đúng 4 phút)

### Bước 1: Tạo khóa `Client ID` & `Client Secret` miễn phí trên Google Cloud (2 phút)
1. Đăng nhập đúng Gmail quản lý kênh YouTube vào: https://console.cloud.google.com/
2. Bấm chọn Project ở góc trên bên trái → **New Project** → đặt tên `MindAndMargin` → **Create**.
3. Vào menu **APIs & Services → Library** → tìm **YouTube Data API v3** → bấm **Enable**.
4. Vào **APIs & Services → OAuth consent screen** (hoặc **Google Auth Platform → Audience**):
   - Chọn **External** → điền App name: `MindAndMargin Autopilot` và email của bạn → **Save**.
   - Tại mục **Test users**, bấm **Add Users** → nhập chính địa chỉ Gmail kênh YouTube của bạn → **Save** *(Rất quan trọng để không bị lỗi 403 `access_denied`!)*.
   - *(Mẹo chống hết hạn 7 ngày)*: Bạn có thể bấm nút **Publish App** (chuyển từ *Testing* sang *In production* — không cần gửi xác minh Google vì chỉ mình bạn dùng, giúp `Refresh Token` sống vĩnh viễn không hết hạn sau 7 ngày!).
5. Vào **APIs & Services → Credentials → + Create Credentials → OAuth client ID**:
   - Application type: chọn **Web application**
   - Name: `MindAndMargin GitHub Actions`
   - Kéo xuống mục **Authorized redirect URIs** → bấm **+ Add URI** và dán chính xác dòng này:
     `https://developers.google.com/oauthplayground`
   - Bấm **Create** → Copy lưu lại **Client ID** và **Client Secret**.

---

### Bước 2: Đổi lấy mã `YOUTUBE_REFRESH_TOKEN` trên OAuth Playground (1 phút)
1. Mở trang công cụ chính thức của Google: https://developers.google.com/oauthplayground
2. Bấm biểu tượng **Bánh răng ⚙️** (góc trên bên phải):
   - Tích chọn ô **Use your own OAuth credentials**
   - Dán **OAuth Client ID** và **OAuth Client Secret** vừa lấy ở Bước 1 vào → bấm **Close**.
3. Ở khung bên trái (**Step 1 — Select & authorize APIs**), kéo xuống ô *Input your own scopes* và dán 3 quyền sau (cách nhau bằng dấu cách):
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl`
   *(Quyền `youtube.force-ssl` giúp hệ thống tự động tải lên cả phụ đề tiếng Anh `.srt` và đăng sẵn bình luận tiếp thị Bio/Amazon dưới video cho bạn!)*
4. Bấm nút xanh **Authorize APIs**:
   - Chọn tài khoản Google → chọn đúng kênh phụ/kênh thương hiệu **Mind & Margin** (`@MindAndMargin`).
   - Nếu hiện cảnh báo *"Google hasn't verified this app"*, bấm **Advanced (Nâng cao)** → **Go to MindAndMargin Autopilot (unsafe)** → **Continue**.
5. Tự động chuyển sang **Step 2** → bấm nút **Exchange authorization code for tokens** → Copy dòng **`Refresh token`** (bắt đầu bằng `1//0...`).

---

### Bước 3: Dán 3 khóa vào GitHub Secrets & Bấm Nút Kiểm Tra Kết Nối (1 phút)
1. Mở thẳng trang bảo mật kho GitHub của bạn:
   https://github.com/kenvh0010-lang/admin/settings/secrets/actions
2. Bấm **New repository secret** và thêm đủ 3 khóa với tên **chính xác in hoa** như sau:
   - `YOUTUBE_CLIENT_ID` → dán Client ID
   - `YOUTUBE_CLIENT_SECRET` → dán Client Secret
   - `YOUTUBE_REFRESH_TOKEN` → dán Refresh token (`1//0...`)
3. **Kiểm tra kết nối ngay trong 10 giây**:
   - Mở tab Actions: https://github.com/kenvh0010-lang/admin/actions/workflows/video_factory.yml
   - Bấm **Run workflow**:
     - Chọn chế độ `verify_youtube_only` để kiểm tra kết nối kênh mà chưa đăng bài, **HOẶC**
     - Chọn chế độ `auto_publish_next` kèm quyền riêng tư `unlisted` (Không công khai) để hệ thống tự render và đăng thử video đầu tiên lên kênh cho bạn xem duyệt trước!
     - Khi đã ưng ý 100%, bạn cứ để mặc định — cứ đúng **20:00 tối Thứ 3, Thứ 5, Thứ 7, Chủ nhật**, GitHub sẽ tự động render và đăng `public` từng video theo đúng lịch 6 tháng (Tuần 1 → Tuần 24) và ghi sổ vào `content/published_ledger.json` để không bao giờ đăng trùng!
