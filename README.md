# MoMo FlexSave — mô phỏng học thuật

Ứng dụng Streamlit dùng **dữ liệu giả lập** để tính khoản tích lũy theo dự báo 30 ngày và so sánh với ba phương án đối chứng. Không kết nối MoMo, ngân hàng hoặc giao dịch tiền thật.

## Chạy ứng dụng

```bash
cd FlexSave-Simulator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit sẽ mở trang cục bộ, thường là `http://localhost:8501`.

Để đưa bản demo lên Streamlit Community Cloud, tạo một GitHub repo riêng chứa
`app.py`, `core.py`, `requirements.txt` và `README.md`; chọn `app.py` làm file chạy.
Không đưa môi trường `.venv` hoặc dữ liệu cá nhân lên repo.

## Nội dung mô phỏng

- 30 ngày, hai lịch dòng tiền: đúng hạn và bất lợi.
- Có thể thêm, sửa, xóa từng khoản thu/chi và ngày phát sinh ở cả hai lịch ngay trên giao diện. Bấm vào ô để sửa; nhập vào dòng trống cuối bảng để thêm; chọn dòng và nhấn Delete để xóa. Dữ liệu chỉ giữ trong phiên ứng dụng, không ghi ra file.
- Khoản dự phòng `R = max(R_user, số_ngày_dự_phòng × chi_thiết_yếu/ngày)`.
- `B_min` là số dư thấp nhất trong **cả hai** lịch dòng tiền.
- Khoản tích lũy `S = min(max(0, B_min - R), giới_hạn_mỗi_lần, mục_tiêu_còn_thiếu, số_dư_nguồn)`.
- So sánh không tích lũy, tích lũy cố định, đối chứng giả định theo lịch sử 14 ngày và FlexSave dự báo 30 ngày.
- Đánh giá số ngày dưới ngưỡng, số dư thấp nhất và mức thiếu hụt lớn nhất trên một lịch dòng tiền thực tế được chọn.

Tình huống mặc định tái hiện ví dụ của bài: số dư 5 triệu đồng, khoản thu 3 triệu đến ngày 4 hoặc 20, số dư thấp nhất lần lượt 2,6 triệu và 1,4 triệu. Khi mức dự phòng là 1,5 triệu, FlexSave đề xuất 0 đồng và cảnh báo thiếu hụt 100.000 đồng.

Các kịch bản K1–K5 trong ứng dụng là **dữ liệu minh họa mới**, không phải lần chạy lại bảng kết quả 90 ngày của thuật toán tham khảo trong báo cáo. Công cụ chỉ kiểm chứng logic trong phạm vi giả định; không chứng minh hiệu quả trên người dùng thực.
