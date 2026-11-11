# 🎬 Mind & Margin (`@mindmargin-t4k`) — Hệ Sinh Thái YouTube News-Shorts Hồ Sơ Thực Chứng & Tự Động Hóa 24/7

Hệ thống sản xuất, kiểm định chống trùng lặp và tự động phát hành hàng ngày cho kênh YouTube tiếng Anh RPM cao **Mind & Margin**:

1. **Kho 11 Dự Án News-Shorts Hồ Sơ Liên Bang (`content/short_00..short_10`)**:
   - `100%` kịch bản dựa trên đơn kiện tòa liên bang Mỹ (`SDNY`, `N.D. Cal.`) và lệnh thực thi `.gov` (`FTC`, `DOJ`, `SEC`, `CFPB`) với **42 trang bằng chứng gốc** trong `assets/evidence/`.
   - Lịch tự đăng định kỳ **hàng ngày lúc `20:00` giờ Việt Nam** (`08:00 AM` giờ Mỹ EST) qua GitHub Actions (`video_factory.yml`) + sổ cái chống đăng trùng 3 lớp (`content/published_ledger.json`).
2. **Phễu Kiếm Tiền Ngay Ngày 1 (`products/` & `docs/`)**:
   - **Trang Bio & Danh mục sách Amazon Associates (`mindandmarg06-20`)**: `https://kenvh0010-lang.github.io/admin/bio/`
   - **Ứng dụng sản phẩm số `$19` (`products/5_hour_asset_builder_os/index.html`)** & **Lead Magnet miễn phí (`products/free_lead_magnet/Wealth_and_Leverage_Playbook.md`)**.
   - **Website biên tập SEO công khai (`docs/`)**: `https://kenvh0010-lang.github.io/admin/` (11 bài phân tích kèm ảnh bằng chứng gốc + hồ sơ lưu trữ `dossier.html`).
3. **Bộ Lọc Chống Trùng Toàn Hệ Thống (`yt_studio/deduper.py` & `cli.py dedupe`)**:
   - Quét tự động trùng tên dự án, trùng tiêu đề (`title` / `alt_title`), trùng URL nguồn vụ án, trùng vùng cắt ảnh bằng chứng, độ tương đồng nội dung (`Jaccard`), thư mục `output/` mồ côi và file nhị phân trùng mã băm `SHA-256`.

---

## 🛠️ Lệnh Vận Hành & Luồng Xử Lý Kịch Bản Mới (`cli.py`)

```bash
# 1. Tạo bản nháp kịch bản cách ly an toàn trong content/drafts/ (kèm tự đo khung ảnh bằng chứng)
python3 cli.py draft-case --slug ftc_case_moi --topic "How an App Triggered a $50M FTC Order" --evidence-dir assets/evidence/ftc_case_moi

# 2. Kiểm duyệt 7 cổng tự động (Schema, Bằng chứng, Trích dẫn https, Brand/Glyph, Nhịp đọc, Amazon, Chống trùng)
python3 cli.py validate content/drafts/ftc_case_moi.json
python3 cli.py validate content/

# 3. Thăng cấp bản nháp đạt chuẩn vào hàng đợi Autopilot (tự gán short_NN_, tạo SRT + Thumbnail + Upload Pack + Web)
python3 cli.py promote content/drafts/ftc_case_moi.json

# 4. Kiểm tra lọc trùng & đồng bộ Website công khai + Sitemap + Amazon Tag
python3 cli.py dedupe --apply
python3 cli.py build-site --amazon-tag mindandmarg06-20

# 5. Render hàng loạt với giọng đọc Neural tiếng Anh Mỹ & tự nhận GPU NVIDIA RTX (h264_nvenc)
python3 cli.py batch content/ --tts edge --voice en_authoritative --encoder auto --workers 4 --skip-existing

# 6. Chạy trọn bộ kiểm thử tự động End-to-End
python3 -m unittest discover -s tests -v
```
