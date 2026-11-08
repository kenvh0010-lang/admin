# 🤖 Hướng Dẫn Kích Hoạt Chế Độ "Chạy Ngầm 100%" Tự Động Đăng Video Lên YouTube (24/7 Cloud Autopilot)

Hệ thống đám mây **GitHub Actions** tại `.github/workflows/video_factory.yml` đã được bật chạy ngầm tự động trên máy chủ của GitHub (**miễn phí 100%, không cần bật máy tính của bạn**):

- **Tự động Render Giọng Đọc Thật (`en-US-ChristopherNeural`)**: Xuất toàn bộ video `.mp4` chuẩn tiếng Anh giọng Mỹ tự nhiên, đóng gói vào mục **Releases**: https://github.com/kenvh0010-lang/admin/releases
- **Lịch chạy ngầm tự động (`cron`)**: **20:00 tối Thứ 3, Thứ 5, Thứ 7 và Chủ nhật** (giờ Việt Nam — đúng 08:00–09:00 sáng giờ Mỹ có giá quảng cáo RPM cao nhất).

---

## Cách 1: Bán Tự Động An Toàn Tuyệt Đối (Khuyên dùng 2 tuần đầu — 5 phút/tuần)
1. Mở trang Releases trên điện thoại hoặc máy tính: https://github.com/kenvh0010-lang/admin/releases
2. Tải gói `.zip` của tuần (`week1_videos_mp4_srt.zip`...) đã có sẵn **video `.mp4` lồng tiếng Mỹ thật + phụ đề `.srt` + Thumbnail + mô tả SEO**.
3. Kéo thả lên **YouTube Studio** và hẹn giờ đăng!

---

## Cách 2: Tự Động Đăng Thẳng Lên Kênh YouTube 100% Khi Tắt Máy (Qua YouTube Data API v3)

Chỉ cần cài đặt 1 lần duy nhất (5 phút), máy chủ GitHub sẽ tự lấy video tiếp theo trong hàng đợi (theo đúng lịch 3 Shorts + 1 Video dài/tuần) đăng thẳng lên kênh YouTube của bạn:

### Bước 1: Tạo khóa YouTube API miễn phí trên Google Cloud
1. Đăng nhập Gmail chủ kênh YouTube vào https://console.cloud.google.com/
2. Tạo Project mới tên `MindAndMargin` → vào **APIs & Services → Library** → tìm **YouTube Data API v3** → bấm **Enable**.
3. Vào **OAuth consent screen** → chọn **External** → điền tên app `MindAndMargin Uploader` → ở mục **Test users**, bấm **Add Users** và điền chính địa chỉ Gmail kênh YouTube của bạn.
4. Vào **Credentials → Create Credentials → OAuth client ID** → chọn **Web application** → tại mục **Authorized redirect URIs**, thêm dòng:
   `https://developers.google.com/oauthplayground`
5. Bấm **Create** → Copy lưu lại **`Client ID`** và **`Client Secret`**.

### Bước 2: Lấy mã `Refresh Token` vĩnh viễn (1 phút)
1. Mở https://developers.google.com/oauthplayground
2. Bấm biểu tượng **Bánh răng ⚙️** (góc trên bên phải) → tích chọn **Use your own OAuth credentials** → dán `Client ID` và `Client Secret` vào.
3. Ở cột bên trái (Step 1), tìm **YouTube Data API v3** → tích chọn:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
   → Bấm **Authorize APIs** và chọn đúng kênh YouTube **Mind & Margin** của bạn.
4. Ở Step 2, bấm **Exchange authorization code for tokens** → Copy dòng **`Refresh token`**.

### Bước 3: Dán 3 khóa vào GitHub Secrets để Hệ thống Tự Chạy Ngầm 24/7
1. Mở trang cài đặt bảo mật kho GitHub của bạn:
   https://github.com/kenvh0010-lang/admin/settings/secrets/actions
2. Bấm **New repository secret** tạo lần lượt 3 khóa:
   - `YOUTUBE_CLIENT_ID` = *(Client ID vừa lấy)*
   - `YOUTUBE_CLIENT_SECRET` = *(Client Secret vừa lấy)*
   - `YOUTUBE_REFRESH_TOKEN` = *(Refresh token vừa lấy)*
3. *(Tuỳ chọn)* Chuyển sang tab **Variables** cạnh đó, tạo biến `AMAZON_ASSOC_TAG` (ví dụ `mindandmargin-20`) để hệ thống tự động gắn mã tiếp thị Amazon của bạn vào mọi bài viết và mô tả video!

🎉 **Xong!** Từ thời điểm này, cứ đúng 20:00 tối Thứ 3, 5, 7, Chủ nhật hàng tuần, hệ thống đám mây sẽ tự động render giọng đọc thật và đăng video kèm Thumbnail + mô tả Affiliate lên kênh YouTube của bạn mà bạn không cần mở máy tính!
