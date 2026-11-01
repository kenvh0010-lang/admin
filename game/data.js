// Dữ liệu game: ngành nghề, công ty, câu hỏi phỏng vấn, sự kiện ngẫu nhiên
const FIELDS = {
  it:  { name: "Công nghệ thông tin", icon: "💻", skill: "Lập trình" },
  mkt: { name: "Marketing",          icon: "📣", skill: "Sáng tạo nội dung" },
  acc: { name: "Kế toán – Tài chính", icon: "📊", skill: "Phân tích số liệu" },
};

// Công ty hư cấu. tier: 1 = dễ, 3 = khó
const COMPANIES = [
  { name: "Startup Mầm Xanh",  tier: 1 },
  { name: "Công ty Sao Mai",   tier: 1 },
  { name: "Tập đoàn Hồng Lam", tier: 2 },
  { name: "Cty TNHH Bến Nghé", tier: 2 },
  { name: "Ngân hàng Phương Nam", tier: 2 },
  { name: "Tập đoàn Đại Việt Tech", tier: 3 },
  { name: "Quỹ đầu tư Cửu Long", tier: 3 },
];

const ROLES = {
  it:  ["Lập trình viên Web", "Kỹ sư Backend", "Tester", "Lập trình viên Mobile", "Kỹ sư Dữ liệu"],
  mkt: ["Chuyên viên Content", "Digital Marketing", "Chuyên viên Thương hiệu", "Social Media Executive"],
  acc: ["Kế toán tổng hợp", "Chuyên viên Phân tích Tài chính", "Kiểm toán viên", "Kế toán thuế"],
};

// score: 0 = tệ, 1 = tạm, 2 = tốt
const COMMON_QUESTIONS = [
  { q: "Hãy giới thiệu ngắn về bản thân bạn.", a: [
    ["Kể toàn bộ tiểu sử từ hồi mẫu giáo.", 0],
    ["Tóm tắt học vấn, kỹ năng chính và lý do ứng tuyển vị trí này.", 2],
    ["Em là người chăm chỉ, ham học hỏi.", 1] ] },
  { q: "Điểm yếu lớn nhất của bạn là gì?", a: [
    ["Em không có điểm yếu nào cả.", 0],
    ["Em hay cầu toàn, nhưng đang học cách ưu tiên và đặt deadline cho mình.", 2],
    ["Em hay đi làm muộn.", 0] ] },
  { q: "Vì sao bạn muốn làm việc ở công ty chúng tôi?", a: [
    ["Vì lương cao.", 0],
    ["Em đã tìm hiểu sản phẩm và văn hoá công ty, thấy phù hợp với định hướng của mình.", 2],
    ["Vì công ty gần nhà.", 1] ] },
  { q: "Bạn thấy mình ở đâu sau 5 năm nữa?", a: [
    ["Ngồi vào ghế của anh/chị.", 0],
    ["Trở thành chuyên viên vững nghề, có thể dẫn dắt một nhóm nhỏ.", 2],
    ["Em chưa nghĩ tới.", 0] ] },
  { q: "Kể về một lần bạn làm việc nhóm gặp mâu thuẫn.", a: [
    ["Em làm hết phần của mọi người cho nhanh.", 1],
    ["Em lắng nghe từng bên, đề xuất chia việc rõ ràng và cả nhóm hoàn thành đúng hạn.", 2],
    ["Em rời nhóm.", 0] ] },
  { q: "Mức lương mong muốn của bạn là bao nhiêu?", a: [
    ["Bao nhiêu cũng được ạ.", 1],
    ["Em đã tham khảo mặt bằng thị trường, mong muốn trong khoảng phù hợp và sẵn sàng trao đổi thêm.", 2],
    ["Gấp đôi mức công ty đưa ra.", 0] ] },
  { q: "Bạn có câu hỏi gì cho chúng tôi không?", a: [
    ["Không ạ.", 0],
    ["Một ngày làm việc điển hình của vị trí này như thế nào, và nhóm đo lường thành công ra sao?", 2],
    ["Công ty có cho nghỉ nhiều không ạ?", 0] ] },
];

const FIELD_QUESTIONS = {
  it: [
    { q: "Khi gặp bug khó trên môi trường production, bạn xử lý thế nào?", a: [
      ["Sửa thẳng trên server cho nhanh.", 0],
      ["Đọc log, tái hiện lỗi, viết test rồi mới sửa và triển khai lại.", 2],
      ["Khởi động lại server và hy vọng.", 0] ] },
    { q: "Git dùng để làm gì?", a: [
      ["Quản lý phiên bản mã nguồn và cộng tác giữa các lập trình viên.", 2],
      ["Để lưu trữ hình ảnh.", 0],
      ["Là một ngôn ngữ lập trình.", 0] ] },
    { q: "Bạn ưu tiên điều gì khi viết code?", a: [
      ["Càng ngắn càng tốt, không cần ai đọc hiểu.", 0],
      ["Dễ đọc, dễ bảo trì, có test đi kèm.", 2],
      ["Chạy được là được.", 1] ] },
  ],
  mkt: [
    { q: "Làm sao đo hiệu quả một chiến dịch quảng cáo?", a: [
      ["Đếm số like.", 1],
      ["Đặt KPI từ đầu: chuyển đổi, chi phí trên mỗi khách hàng, ROI, rồi so sánh.", 2],
      ["Hỏi sếp có thích không.", 0] ] },
    { q: "Khách hàng phàn nàn gay gắt trên fanpage, bạn làm gì?", a: [
      ["Xoá bình luận.", 0],
      ["Phản hồi lịch sự, nhận thông tin, chuyển bộ phận liên quan và cập nhật lại.", 2],
      ["Cãi lại cho ra lẽ.", 0] ] },
    { q: "Chân dung khách hàng (persona) dùng để làm gì?", a: [
      ["Để trang trí slide.", 0],
      ["Hiểu nhu cầu, hành vi của nhóm mục tiêu để chọn thông điệp và kênh phù hợp.", 2],
      ["Không cần thiết lắm.", 0] ] },
  ],
  acc: [
    { q: "Phát hiện số liệu sổ sách lệch với sao kê ngân hàng, bạn làm gì?", a: [
      ["Điều chỉnh cho khớp rồi thôi.", 0],
      ["Đối chiếu từng giao dịch, tìm nguyên nhân, ghi nhận bút toán điều chỉnh có chứng từ.", 2],
      ["Báo cáo là không sao.", 0] ] },
    { q: "Bảng cân đối kế toán thể hiện điều gì?", a: [
      ["Tình hình tài sản, nợ phải trả và vốn chủ sở hữu tại một thời điểm.", 2],
      ["Doanh thu trong năm.", 0],
      ["Danh sách nhân viên.", 0] ] },
    { q: "Bạn dùng công cụ nào để xử lý số liệu lớn?", a: [
      ["Máy tính bỏ túi.", 0],
      ["Excel nâng cao (PivotTable, hàm tra cứu) và phần mềm kế toán.", 2],
      ["Tính nhẩm.", 0] ] },
  ],
};

// Sự kiện ngẫu nhiên mỗi ngày (xác suất ~25%)
const EVENTS = [
  { text: "Bạn cũ giới thiệu một vị trí nội bộ — CV của bạn được chú ý hơn.", fx: s => { s.network += 10; } },
  { text: "Xe hỏng giữa đường, tốn tiền sửa.", fx: s => { s.money -= 300000; } },
  { text: "Một buổi hội thảo nghề nghiệp miễn phí giúp bạn học thêm.", fx: s => { s.skill += 5; } },
  { text: "Bị từ chối liên tục khiến bạn hơi nản.", fx: s => { s.confidence -= 10; } },
  { text: "Gia đình gửi thêm chút tiền động viên.", fx: s => { s.money += 500000; } },
  { text: "Bạn đọc được một cuốn sách hay về phỏng vấn.", fx: s => { s.confidence += 8; } },
  { text: "Mất ngủ cả đêm vì lo lắng.", fx: s => { s.energy -= 15; } },
];
