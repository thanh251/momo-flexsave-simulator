"""Pure-Python calculation engine for the academic FlexSave simulation.

All amounts are VND. A saving is moved out of the spendable balance on day 0
and is not withdrawn during the 30-day horizon. No real accounts are used.
"""

from dataclasses import dataclass


HORIZON = 30


@dataclass(frozen=True)
class CashFlow:
    day: int
    amount: int
    label: str


@dataclass(frozen=True)
class Scenario:
    name: str
    opening: int
    expected_income: tuple[CashFlow, ...]
    stress_income: tuple[CashFlow, ...]
    expected_expense: tuple[CashFlow, ...]
    stress_expense: tuple[CashFlow, ...]
    history_net_per_day: int
    description: str


def cash_path(opening: int, income: tuple[CashFlow, ...],
              expense: tuple[CashFlow, ...], saving: int = 0) -> list[int]:
    """Balances from day 0 to day 30, after an optional day-0 saving."""
    if opening < 0 or saving < 0 or saving > opening:
        raise ValueError("Số dư và khoản tích lũy phải hợp lệ.")
    delta = [0] * (HORIZON + 1)
    for flow in income:
        if not 1 <= flow.day <= HORIZON or flow.amount < 0:
            raise ValueError("Khoản thu không hợp lệ.")
        delta[flow.day] += flow.amount
    for flow in expense:
        if not 1 <= flow.day <= HORIZON or flow.amount < 0:
            raise ValueError("Khoản chi không hợp lệ.")
        delta[flow.day] -= flow.amount
    balances = [opening - saving]
    for day in range(1, HORIZON + 1):
        balances.append(balances[-1] + delta[day])
    return balances


def reserve_amount(user_reserve: int, essential_daily: int, reserve_days: int) -> int:
    if min(user_reserve, essential_daily, reserve_days) < 0:
        raise ValueError("Mức dự phòng không được âm.")
    return max(user_reserve, essential_daily * reserve_days)


def recommendation(scenario: Scenario, reserve: int, per_transfer_cap: int,
                   remaining_goal: int) -> dict:
    """Robust rule: S=min(max(0,B_min-R),L,max(0,G-A),Q).

    B_min is taken across every day in both expected and adverse cash paths.
    Q is the amount currently transferable from the source balance.
    """
    if min(reserve, per_transfer_cap, remaining_goal) < 0:
        raise ValueError("Các giới hạn không được âm.")
    expected = cash_path(scenario.opening, scenario.expected_income,
                         scenario.expected_expense)
    stress = cash_path(scenario.opening, scenario.stress_income,
                       scenario.stress_expense)
    minimum = min(min(expected), min(stress))
    cushion = max(0, minimum - reserve)
    transferable = scenario.opening
    saving = min(cushion, per_transfer_cap, remaining_goal, transferable)
    return {
        "saving": saving,
        "expected_min": min(expected),
        "stress_min": min(stress),
        "minimum": minimum,
        "cushion": cushion,
        "reserve": reserve,
        "preexisting_shortfall": max(0, reserve - minimum),
    }


def historical_reference(scenario: Scenario, reserve: int,
                         per_transfer_cap: int, remaining_goal: int) -> int:
    """Illustrative 14-day-history proxy; not the original report algorithm.

    Projects the past average daily net cash flow without dated obligations.
    """
    projected_low = scenario.opening + min(0, scenario.history_net_per_day * HORIZON)
    return min(max(0, projected_low - reserve), per_transfer_cap,
               remaining_goal, scenario.opening)


def evaluate_path(path: list[int], reserve: int, saving: int) -> dict:
    return {
        "saved": saving,
        "min_balance": min(path),
        "days_below_reserve": sum(balance < reserve for balance in path[1:]),
        "worst_shortfall": max(0, reserve - min(path)),
        "closing_balance": path[-1],
    }


def compare(scenario: Scenario, reserve: int, cap: int, remaining_goal: int,
            actual_stress: bool) -> tuple[dict, dict, dict]:
    rec = recommendation(scenario, reserve, cap, remaining_goal)
    income = scenario.stress_income if actual_stress else scenario.expected_income
    expense = scenario.stress_expense if actual_stress else scenario.expected_expense
    amounts = {
        "Không tích lũy": 0,
        "Tích lũy cố định": min(cap, remaining_goal, scenario.opening),
        "Theo lịch sử 14 ngày (đối chứng giả định)": historical_reference(
            scenario, reserve, cap, remaining_goal),
        "FlexSave dự báo 30 ngày": rec["saving"],
    }
    paths = {name: cash_path(scenario.opening, income, expense, amount)
             for name, amount in amounts.items()}
    metrics = {name: evaluate_path(paths[name], reserve, amount)
               for name, amount in amounts.items()}
    return rec, paths, metrics


def f(day: int, amount: int, label: str) -> CashFlow:
    return CashFlow(day, amount, label)


def flows_from_rows(rows: list[dict]) -> tuple[tuple[CashFlow, ...], tuple[CashFlow, ...]]:
    """Validate user-edited transaction rows and split income from expenses."""
    incomes = []
    expenses = []
    for number, row in enumerate(rows, start=1):
        day, kind, label, amount = (row.get(key) for key in
                                    ("day", "kind", "label", "amount"))
        if all(value is None or value == "" for value in (day, kind, label, amount)):
            continue  # A new, untouched editor row.
        if day is None or isinstance(day, bool) or int(day) != day or not 1 <= int(day) <= HORIZON:
            raise ValueError(f"Dòng {number}: ngày phải là số nguyên từ 1 đến {HORIZON}.")
        if kind not in ("Thu", "Chi"):
            raise ValueError(f"Dòng {number}: chọn loại Thu hoặc Chi.")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Dòng {number}: cần nhập nội dung.")
        if amount is None or isinstance(amount, bool) or int(amount) != amount or amount < 0:
            raise ValueError(f"Dòng {number}: số tiền phải là số nguyên không âm.")
        flow = CashFlow(int(day), int(amount), label.strip())
        (incomes if kind == "Thu" else expenses).append(flow)
    return tuple(incomes), tuple(expenses)


def presets() -> dict[str, Scenario]:
    """Illustrative synthetic inputs, not observed MoMo customer data."""
    example_expenses = (f(1, 2_400_000, "Tiền nhà và sinh hoạt"),
                        f(10, 1_200_000, "Hóa đơn và sinh hoạt"))
    return {
        "Ví dụ chính: thù lao đến chậm": Scenario(
            "Ví dụ chính: thù lao đến chậm", 5_000_000,
            (f(4, 3_000_000, "Thù lao dự án"),),
            (f(20, 3_000_000, "Thù lao dự án đến chậm"),),
            example_expenses, example_expenses, 0,
            "Khoản thu 3 triệu đồng đến ngày 4 hoặc ngày 20. Hai khoản chi "
            "được đặt để kiểm tra ví dụ 2,6 triệu đồng so với 1,4 triệu đồng."),
        "K1: thu nhập đều": Scenario(
            "K1: thu nhập đều", 3_000_000,
            tuple(f(d, 700_000, "Thu nhập tuần") for d in (3, 10, 17, 24)),
            tuple(f(d, 700_000, "Thu nhập tuần") for d in (5, 12, 19, 26)),
            tuple(f(d, 450_000, "Chi phí tuần") for d in (4, 11, 18, 25)),
            tuple(f(d, 450_000, "Chi phí tuần") for d in (4, 11, 18, 25)),
            20_000, "Thu nhập đều nhưng trong kịch bản bất lợi đến chậm 2 ngày."),
        "K2: thu nhập dao động": Scenario(
            "K2: thu nhập dao động", 3_500_000,
            tuple(f(d, a, "Thu nhập biến động") for d, a in
                  ((3, 300_000), (9, 1_000_000), (16, 450_000), (23, 1_100_000))),
            tuple(f(d, a, "Thu nhập biến động thấp") for d, a in
                  ((3, 200_000), (12, 650_000), (19, 300_000), (27, 700_000))),
            tuple(f(d, 500_000, "Chi phí tuần") for d in (5, 12, 19, 26)),
            tuple(f(d, 500_000, "Chi phí tuần") for d in (5, 12, 19, 26)),
            10_000, "Thu nhập theo tuần thay đổi cả số tiền và thời điểm."),
        "K3: thu nhập tập trung": Scenario(
            "K3: thu nhập tập trung", 4_000_000,
            (f(6, 3_000_000, "Thù lao dự án"),),
            (f(19, 3_000_000, "Thù lao dự án đến chậm"),),
            (f(2, 1_800_000, "Tiền nhà"), f(14, 900_000, "Sinh hoạt")),
            (f(2, 1_800_000, "Tiền nhà"), f(14, 900_000, "Sinh hoạt")),
            40_000, "Một khoản thu lớn; rủi ro nằm ở ngày nhận tiền."),
        "K4: thu nhập giảm mạnh": Scenario(
            "K4: thu nhập giảm mạnh", 4_000_000,
            tuple(f(d, 900_000, "Thu nhập dự kiến") for d in (5, 12, 19, 26)),
            tuple(f(d, 350_000, "Thu nhập thực tế thấp") for d in (5, 12, 19, 26)),
            tuple(f(d, 650_000, "Chi phí thiết yếu") for d in (7, 14, 21, 28)),
            tuple(f(d, 650_000, "Chi phí thiết yếu") for d in (7, 14, 21, 28)),
            35_000, "Kịch bản bất lợi giảm mạnh từng khoản thu."),
        "K5: chi phí bất thường": Scenario(
            "K5: chi phí bất thường", 4_000_000,
            (f(10, 1_800_000, "Thu nhập"), f(25, 1_800_000, "Thu nhập")),
            (f(10, 1_800_000, "Thu nhập"), f(25, 1_800_000, "Thu nhập")),
            (f(5, 1_100_000, "Tiền nhà"), f(20, 900_000, "Sinh hoạt")),
            (f(5, 1_100_000, "Tiền nhà"), f(16, 1_400_000, "Chi phí phát sinh"),
             f(20, 900_000, "Sinh hoạt")),
            30_000, "Chi phí phát sinh 1,4 triệu đồng ở ngày 16."),
    }
