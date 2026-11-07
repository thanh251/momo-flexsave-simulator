"""Run with: streamlit run app.py"""

import csv
import io

import pandas as pd
import streamlit as st

from core import HORIZON, CashFlow, Scenario, compare, flows_from_rows, presets, reserve_amount


st.set_page_config(page_title="FlexSave | Mô phỏng học thuật", page_icon="💜", layout="wide")
st.title("MoMo FlexSave · Mô phỏng dòng tiền")
st.caption("Nguyên mẫu học thuật · dữ liệu giả lập · không kết nối MoMo/ngân hàng · không chuyển tiền thật")


def vnd(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".") + " đ"


def event_table(income: tuple[CashFlow, ...], expense: tuple[CashFlow, ...]) -> list[dict]:
    rows = ([{"day": x.day, "kind": "Thu", "label": x.label,
              "amount": x.amount} for x in income] +
            [{"day": x.day, "kind": "Chi", "label": x.label,
              "amount": x.amount} for x in expense])
    return sorted(rows, key=lambda x: (x["day"], x["kind"]))


def edit_schedule(title: str, income: tuple[CashFlow, ...],
                  expense: tuple[CashFlow, ...], key: str) -> tuple[tuple[CashFlow, ...], tuple[CashFlow, ...]]:
    st.write(title)
    edited = st.data_editor(
        pd.DataFrame(event_table(income, expense), columns=["day", "kind", "label", "amount"]),
        key=key,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_order=["day", "kind", "label", "amount"],
        column_config={
            "day": st.column_config.NumberColumn("Ngày", min_value=1, max_value=HORIZON,
                                                  step=1, required=True),
            "kind": st.column_config.SelectboxColumn("Loại", options=["Thu", "Chi"],
                                                      required=True),
            "label": st.column_config.TextColumn("Nội dung", required=True),
            "amount": st.column_config.NumberColumn("Số tiền (đ)", min_value=0,
                                                     step=10_000, required=True),
        },
    )
    return flows_from_rows(edited.to_dict("records"))


def csv_bytes(paths: dict, reserve: int) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ngay", "nguong_du_phong", *paths.keys()])
    for day in range(HORIZON + 1):
        writer.writerow([day, reserve, *(path[day] for path in paths.values())])
    return output.getvalue().encode("utf-8-sig")


all_presets = presets()
with st.sidebar:
    st.header("Thiết lập mô phỏng")
    selected = st.selectbox("Tình huống dữ liệu giả lập", list(all_presets))
    base = all_presets[selected]
    opening = st.number_input("Số dư ban đầu (đ)", min_value=0, value=base.opening,
                              step=100_000, format="%d")
    user_reserve = st.number_input("Dự phòng người dùng chọn (đ)", min_value=0,
                                   value=1_500_000, step=100_000, format="%d")
    essential_daily = st.number_input("Chi thiết yếu bình quân/ngày (đ)", min_value=0,
                                      value=50_000, step=10_000, format="%d")
    reserve_days = st.number_input("Số ngày dự phòng", min_value=0, max_value=90,
                                   value=14, step=1)
    cap = st.number_input("Giới hạn tích lũy mỗi lần (đ)", min_value=0,
                          value=900_000, step=100_000, format="%d")
    remaining_goal = st.number_input("Phần mục tiêu còn thiếu (đ)", min_value=0,
                                     value=2_000_000, step=100_000, format="%d")
    actual_stress = st.toggle("Dòng tiền thực tế là kịch bản bất lợi", value=True)
    st.caption("Có thể sửa số dư và các giới hạn ở đây; lịch thu chi được chỉnh ở hai bảng bên dưới.")

st.subheader("Chỉnh lịch thu chi")
st.caption("Bấm vào ô để sửa; nhập vào dòng trống cuối bảng để thêm; chọn dòng rồi nhấn Delete để xóa. "
           "Các thay đổi chỉ dùng trong phiên mô phỏng hiện tại.")
expected_tab, stress_tab = st.tabs(["Đúng hạn", "Bất lợi"])
try:
    with expected_tab:
        expected_income, expected_expense = edit_schedule(
            "Lịch dòng tiền đúng hạn", base.expected_income, base.expected_expense,
            f"expected_{selected}")
    with stress_tab:
        stress_income, stress_expense = edit_schedule(
            "Lịch dòng tiền bất lợi", base.stress_income, base.stress_expense,
            f"stress_{selected}")
except (ValueError, TypeError) as error:
    st.error(f"Lịch thu chi chưa hợp lệ: {error}")
    st.stop()

scenario = Scenario(base.name, int(opening), expected_income, stress_income,
                    expected_expense, stress_expense, base.history_net_per_day,
                    base.description)
reserve = reserve_amount(int(user_reserve), int(essential_daily), int(reserve_days))
rec, paths, metrics = compare(scenario, reserve, int(cap), int(remaining_goal), actual_stress)

st.info(base.description + " Bạn có thể sửa toàn bộ lịch thu chi ở hai bảng phía trên.")
columns = st.columns(4)
columns[0].metric("Khuyến nghị FlexSave", vnd(rec["saving"]))
columns[1].metric("Số dư thấp nhất · đúng hạn", vnd(rec["expected_min"]))
columns[2].metric("Số dư thấp nhất · bất lợi", vnd(rec["stress_min"]))
columns[3].metric("Mức dự phòng áp dụng", vnd(reserve))

if rec["preexisting_shortfall"]:
    st.warning("Ngay cả khi chưa tích lũy, một kịch bản có thể thấp hơn dự phòng "
               f"{vnd(rec['preexisting_shortfall'])}. FlexSave đề xuất 0 đ và cảnh báo thiếu tiền.")
else:
    st.success("Khoản khuyến nghị không làm số dư dự báo ở các kịch bản được kiểm tra "
               "thấp hơn mức dự phòng.")

st.subheader("Vì sao đề xuất mức này?")
st.write(
    f"Số dư thấp nhất của hai kịch bản là **{vnd(rec['minimum'])}**. "
    f"Sau khi giữ dự phòng **{vnd(reserve)}**, phần dư an toàn là "
    f"**{vnd(rec['cushion'])}**. Khoản đề xuất bằng giá trị nhỏ nhất giữa "
    f"phần dư này, giới hạn mỗi lần **{vnd(cap)}**, phần mục tiêu còn thiếu "
    f"**{vnd(remaining_goal)}** và số dư nguồn **{vnd(opening)}**."
)

st.subheader("So sánh bốn phương án trên cùng dòng tiền thực tế")
rows = []
for name, result in metrics.items():
    rows.append({"Phương án": name,
                 "Đã tích lũy (đ)": result["saved"],
                 "Số ngày dưới dự phòng": result["days_below_reserve"],
                 "Số dư thấp nhất (đ)": result["min_balance"],
                 "Thiếu hụt lớn nhất (đ)": result["worst_shortfall"],
                 "Số dư cuối kỳ (đ)": result["closing_balance"]})
st.dataframe(rows, hide_index=True, width="stretch")
st.caption("Khoản tích lũy được trích vào ngày 0 và nằm ngoài số dư khả dụng trong 30 ngày. "
           "Số dư cuối kỳ chưa cộng lại khoản đã tích lũy.")

chart = {name: path for name, path in paths.items()}
chart["Ngưỡng dự phòng"] = [reserve] * (HORIZON + 1)
st.line_chart(chart, x_label="Ngày (0–30)", y_label="Số dư khả dụng (đ)")
st.download_button("Tải dữ liệu kết quả CSV", csv_bytes(paths, reserve),
                   file_name="flexsave_30_ngay.csv", mime="text/csv")

with st.expander("Phạm vi và cách hiểu kết quả"):
    st.markdown("""
- Đây là dữ liệu tổng hợp do nhóm đặt ra, không phải dữ liệu hoặc kết quả kinh doanh của MoMo.
- “Theo lịch sử 14 ngày” là **đối chứng giả định**: lấy dòng tiền ròng bình quân của 14 ngày trước để chiếu lên 30 ngày, không biết lịch nghĩa vụ. Nó **không tái tạo** thuật toán tham khảo hay bảng K1–K5 trong báo cáo.
- Bốn phương án dùng cùng số dư và cùng lịch dòng tiền thực tế. Khác biệt nằm ở khoản trích tại ngày 0.
- Mô hình chưa ước lượng xác suất từng kịch bản, lãi sinh ra, phí, rút tiền, giao dịch thật hoặc độ chính xác của dự báo từ dữ liệu người dùng.
- Nếu cả trước khi tích lũy số dư đã thấp hơn dự phòng, đề xuất 0 đ không xóa được thiếu hụt vốn có; phần cảnh báo cho thấy điều đó.
""")
