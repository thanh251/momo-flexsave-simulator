"""Run with: streamlit run app.py"""

import csv
import io
import re

import pandas as pd
import streamlit as st

from core import HORIZON, CashFlow, Scenario, cash_path, compare, flows_from_rows, presets, reserve_amount


st.set_page_config(page_title="FlexSave | Mô phỏng học thuật", page_icon="💜", layout="wide")
st.markdown("""
<style>
    :root {
        --momo-pink: #A50064;
        --momo-pink-soft: #FFEFF4;
        --momo-pink-border: #FEC8DC;
    }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #FFEFF4 0, #FFFFFF 220px);
    }
    [data-testid="stSidebar"] {
        background-color: #FFF5F8;
        border-right: 1px solid var(--momo-pink-border);
    }
    [data-testid="stSidebar"] h2,
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3 {
        color: var(--momo-pink);
    }
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--momo-pink-border);
        border-radius: 14px;
        padding: 14px 16px;
    }
    [data-testid="stMetricValue"] {
        color: var(--momo-pink);
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: var(--momo-pink);
    }
    [data-testid="stDownloadButton"] button {
        background-color: var(--momo-pink);
        border-color: var(--momo-pink);
        color: #FFFFFF;
    }
    [data-testid="stDownloadButton"] button:hover {
        background-color: #85004F;
        border-color: #85004F;
        color: #FFFFFF;
    }
</style>
""", unsafe_allow_html=True)
st.title("MoMo FlexSave · Mô phỏng dòng tiền")
st.caption("Nguyên mẫu học thuật · dữ liệu giả lập · không kết nối MoMo/ngân hàng · không chuyển tiền thật")


def vnd(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".") + " đ"


def money_text(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def parse_money_text(value: str) -> int:
    value = value.strip()
    if not (re.fullmatch(r"\d+", value) or
            re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value)):
        raise ValueError("Chỉ nhập số nguyên không âm, ví dụ 1000000 hoặc 1.000.000.")
    return int(value.replace(".", ""))


def format_money_field(key: str) -> None:
    try:
        st.session_state[key] = money_text(parse_money_text(st.session_state[key]))
    except ValueError:
        pass  # Keep the typed value visible so the user can correct it.


def money_input(label: str, default: int, key: str) -> int:
    if key not in st.session_state:
        st.session_state[key] = money_text(default)
    value = st.text_input(label, key=key,
                          on_change=format_money_field, args=(key,))
    try:
        return parse_money_text(value)
    except ValueError as error:
        st.error(f"{label}: {error}")
        st.stop()


def lowest_balance_context(scenario: Scenario, minimum: int) -> str:
    cases = (("đúng hạn", scenario.expected_income, scenario.expected_expense),
             ("bất lợi", scenario.stress_income, scenario.stress_expense))
    details = []
    for name, income, expense in cases:
        path = cash_path(scenario.opening, income, expense)
        if min(path) == minimum:
            day = path.index(minimum)
            details.append(f"kịch bản {name}, ngày {day}")
    return "; ".join(details)


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
                                                  step=1, required=True, width="small"),
            "kind": st.column_config.SelectboxColumn("Loại", options=["Thu", "Chi"],
                                                      required=True, width="small"),
            "label": st.column_config.TextColumn("Nội dung", required=True, width="small"),
            "amount": st.column_config.NumberColumn("Số tiền (đ)", min_value=0,
                                                     step=10_000, required=True, width="small"),
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
    opening = money_input("Số dư ban đầu (đ)", base.opening, f"opening_{selected}")
    user_reserve = money_input("Dự phòng người dùng chọn (đ)", 1_500_000, "user_reserve")
    essential_daily = money_input("Chi thiết yếu bình quân/ngày (đ)", 50_000, "essential_daily")
    reserve_days = st.number_input("Số ngày dự phòng", min_value=0, max_value=90,
                                   value=14, step=1)
    cap = money_input("Giới hạn tích lũy mỗi lần (đ)", 900_000, "cap")
    remaining_goal = money_input("Phần mục tiêu còn thiếu (đ)", 2_000_000, "remaining_goal")
    actual_stress = st.toggle("Dòng tiền thực tế là kịch bản bất lợi", value=True)
    essential_reserve = int(essential_daily) * int(reserve_days)
    preview_reserve = reserve_amount(int(user_reserve), int(essential_daily), int(reserve_days))
    st.markdown(f"**Dự phòng theo thiết lập: {vnd(preview_reserve)}**")
    st.caption(f"Lấy mức cao hơn giữa dự phòng bạn chọn ({vnd(user_reserve)}) và "
               f"chi thiết yếu ({vnd(essential_daily)} × {reserve_days} ngày = "
               f"{vnd(essential_reserve)}).")
    st.caption("Nhập 1000000 hoặc 1.000.000; sau khi nhấn Enter hoặc rời ô, số tiền sẽ có dấu chấm. Lịch thu chi được chỉnh ở hai bảng bên dưới.")

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
current_inputs = (scenario, int(user_reserve), int(essential_daily), int(reserve_days),
                  int(cap), int(remaining_goal), actual_stress)
run_pressed = st.button("Chạy mô phỏng", type="primary")
if run_pressed or "simulation_result" not in st.session_state:
    rec, paths, metrics = compare(scenario, reserve, int(cap), int(remaining_goal), actual_stress)
    st.session_state["simulation_result"] = {
        "inputs": current_inputs,
        "scenario": scenario,
        "reserve": reserve,
        "cap": int(cap),
        "remaining_goal": int(remaining_goal),
        "rec": rec,
        "paths": paths,
        "metrics": metrics,
    }

result = st.session_state["simulation_result"]
if current_inputs != result["inputs"]:
    st.warning("Bạn đã thay đổi tham số hoặc lịch thu chi. Kết quả bên dưới vẫn thuộc lần chạy trước; "
               "nhấn **Chạy mô phỏng** để áp dụng toàn bộ thay đổi.")
else:
    st.caption("Kết quả đã được tính từ toàn bộ tham số và hai lịch thu chi đang hiển thị.")

scenario = result["scenario"]
reserve = result["reserve"]
cap = result["cap"]
remaining_goal = result["remaining_goal"]
opening = scenario.opening
rec, paths, metrics = result["rec"], result["paths"], result["metrics"]

st.info(scenario.description + " Bạn có thể sửa toàn bộ lịch thu chi ở hai bảng phía trên.")
st.subheader("Đánh giá khuyến nghị")
low_point = lowest_balance_context(scenario, rec["minimum"])
if rec["preexisting_shortfall"]:
    st.error(
        f"**Không khả thi để tích lũy lúc này — đề xuất 0 đ.** "
        f"Tại {low_point}, số dư dự báo thấp nhất là **{vnd(rec['minimum'])}**, "
        f"thấp hơn mức dự phòng **{vnd(reserve)}** một khoản "
        f"**{vnd(rec['preexisting_shortfall'])}** ngay cả khi chưa tích lũy. "
        "Nên giữ tiền khả dụng và xem lại lịch thu chi hoặc mức dự phòng."
    )
elif remaining_goal == 0:
    st.warning("**Không cần tích lũy thêm — đề xuất 0 đ.** Phần mục tiêu còn thiếu "
               "được đặt bằng 0 đ; hãy tăng mục tiêu nếu muốn tiếp tục mô phỏng tích lũy.")
elif cap == 0:
    st.warning("**Tạm dừng theo thiết lập — đề xuất 0 đ.** Giới hạn tích lũy "
               "mỗi lần đang là 0 đ; hãy tăng giới hạn nếu muốn nhận khuyến nghị.")
elif rec["saving"] == 0:
    st.error(
        f"**Không khả thi để tích lũy lúc này — đề xuất 0 đ.** "
        f"Tại {low_point}, số dư dự báo thấp nhất là **{vnd(rec['minimum'])}**, "
        f"không cao hơn mức dự phòng **{vnd(reserve)}**. "
        "Trích thêm tiền sẽ làm số dư thấp hơn ngưỡng an toàn đã chọn."
    )
else:
    constraints = (("phần dư an toàn", rec["cushion"]),
                   ("giới hạn mỗi lần", cap),
                   ("phần mục tiêu còn thiếu", remaining_goal),
                   ("số dư nguồn", opening))
    binding = ", ".join(name for name, amount in constraints if amount == rec["saving"])
    remaining_at_low = rec["minimum"] - rec["saving"]
    st.success(
        f"**Khả thi trong phạm vi mô phỏng — đề xuất tích lũy {vnd(rec['saving'])}.** "
        f"Điểm thấp nhất nằm ở {low_point}: trước khi trích tiền là "
        f"**{vnd(rec['minimum'])}**, sau khi trích còn **{vnd(remaining_at_low)}**, "
        f"vẫn không thấp hơn dự phòng **{vnd(reserve)}**. "
        f"Mức đề xuất bị giới hạn bởi **{binding}**."
    )

first_row = st.columns(2)
second_row = st.columns(2)
first_row[0].metric("Khuyến nghị FlexSave", vnd(rec["saving"]))
first_row[1].metric("Số dư thấp nhất · đúng hạn", vnd(rec["expected_min"]))
second_row[0].metric("Số dư thấp nhất · bất lợi", vnd(rec["stress_min"]))
second_row[1].metric("Mức dự phòng áp dụng", vnd(reserve))

st.subheader("Cách tính mức đề xuất")
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
           "Số dư cuối kỳ chưa cộng lại khoản đã tích lũy. "
           "Trên màn hình nhỏ, kéo ngang bảng để xem các chỉ số còn lại.")

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
