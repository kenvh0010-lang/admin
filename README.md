# 🎬 Mind & Margin — Hệ Sinh Thái Kênh YouTube Ẩn Danh & Tự Động Hóa (Trọn Gói Đa Phòng Ban)

Hệ thống hoàn chỉnh từ A–Z vận hành kênh YouTube ẩn danh tiếng Anh (**RPM cao `$12–$25`**) với quỹ thời gian **dưới 5 giờ/tuần**, được xây dựng và kiểm định đồng bộ bởi 4 Phòng ban chuyên trách:

1. **Phòng Nội Dung & Biên Kịch (`content/`)**: Trọn bộ **16/16 kịch bản phân cảnh JSON** cho cả Tháng 1 (12 YouTube Shorts 9:16 + 4 Video dài Visual Essay 16:9) cùng lịch đăng bài 30 ngày (`calendar_30_days.csv`).
2. **Phòng Sản Phẩm Số & Kiếm Tiền Phễu (`products/`)**:
   - **Ứng dụng sản phẩm số `$19` (`products/5_hour_asset_builder_os/index.html`)**: Tích hợp Đồng hồ Ultradian 90 phút, Máy tính lãi kép Anti-Diderot, Bảng kế hoạch 52 tuần và Ma trận quyết định 80/20.
   - **Trang đích Link-in-Bio Affiliate (`products/bio_funnel_page/index.html`)**: Thu email tự động, tặng Ebook miễn phí và điều hướng sang Audible / Notion / Make / Beehiiv + gói `$19`.
   - **Ebook Lead Magnet tiếng Anh (`products/free_lead_magnet/Wealth_and_Leverage_Playbook.md`)** & **Cẩm nang vận hành rút tiền về Việt Nam (`products/monetization_ops_guide.md`)**.
3. **Phòng Thiết Kế Mỹ Thuật (`assets/`)**: Bộ nhận diện thương hiệu (`avatar.jpg`, `banner.jpg`) + trọn bộ 4 Thumbnail 16:9 độ tương phản cao cho 4 Video dài Tháng 1 (`assets/thumbnails/`).
4. **Phòng Kỹ Thuật & Web Studio (`yt_studio/`, `cli.py`, `studio_server.py`, `web_studio/`)**:
   - Dây chuyền Python + FFmpeg tự động tạo giọng đọc (`edge-tts` miễn phí / OpenAI / ElevenLabs), nhạc nền Ambient không bản quyền Content ID, đồ họa Infographic động, phụ đề `.srt` và gói SEO.
   - **Creator Command Center (`studio_server.py`)**: Bảng điều khiển Web quản lý toàn bộ 16 video, phát thử `.mp4`, copy SEO 1 chạm, kích hoạt render trực tiếp trên trình duyệt và xem trước các sản phẩm số.

---

## 🚀 Cài Đặt & Khởi Chạy Nhanh (2 Phút)

Yêu cầu: **Python 3.10+** và **FFmpeg** đã cài trên máy.

```bash
# 1. Tạo môi trường ảo & cài thư viện (gồm Pillow + edge-tts miễn phí)
python3 -m venv .venv
source .venv/bin/activate   # Trên Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Mở Bảng điều khiển Web Studio (Creator Command Center) tại http://localhost:8765
python3 studio_server.py --port 8765
```

---

## 🛠️ Lệnh Sản Xuất Dòng Lệnh (`cli.py`)

```bash
# Render hàng loạt toàn bộ 16 video Tháng 1 (xuất MP4 + SRT + Thumbnail + Gói SEO)
python3 cli.py batch content/

# Render lẻ 1 kịch bản bất kỳ
python3 cli.py render content/short_04_rich_vs_wealthy.json

# Tạo kịch bản AI mới (tự sinh JSON qua GEMINI_API_KEY / OPENAI_API_KEY hoặc xuất prompt $0)
python3 cli.py script \
  --topic "Why Parkinson's Law Doubles Your Output" \
  --format short \
  --out content/new_short.json

# Chạy kiểm thử tự động
python3 -m unittest discover -s tests -v
```

---

## 📂 Cấu Trúc Dự Án

- `studio_server.py` & `web_studio/index.html` — Web Dashboard quản trị kênh & xem trước sản phẩm.
- `cli.py` & `yt_studio/` — Lõi tự động hóa sản xuất video, âm thanh, phụ đề và SEO.
- `content/` — Đủ 16 kịch bản JSON Tháng 1 + `calendar_30_days.csv`.
- `products/` — Ứng dụng `$19` 5-Hour Asset Builder OS, Bio Funnel Page, Ebook Lead Magnet & Hướng dẫn kiếm tiền.
- `assets/` — Avatar, Banner và bộ Thumbnail 16:9.
- `output/` — Kho chứa file `.mp4`, `.srt`, `*_thumbnail.png` và `youtube_upload_pack.md` đã xuất.
