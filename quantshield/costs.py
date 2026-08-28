
BROKERAGE_RATE = 0.0003
BROKERAGE_CAP = 20.0
STT_INTRADAY_SELL_EQUITY = 0.00025
STT_INTRADAY_SELL_ETF = 0.00025
EXCH_TXN_NSE = 0.0000297
SEBI_CHARGE = 0.000001
STAMP_DUTY_BUY = 0.00003
GST_RATE = 0.18
MIS_SQUAREOFF_PENALTY = 50.0 * (1 + GST_RATE)


def brokerage(order_value: float) -> float:
    return min(BROKERAGE_CAP, order_value * BROKERAGE_RATE)


def leg_cost(order_value: float, side: str, etf: bool = False) -> float:
    if order_value <= 0:
        return 0.0
    b = brokerage(order_value)
    txn = order_value * EXCH_TXN_NSE
    sebi = order_value * SEBI_CHARGE
    stt = 0.0
    stamp = 0.0
    if side == 'SELL':
        stt = order_value * (STT_INTRADAY_SELL_ETF if etf else STT_INTRADAY_SELL_EQUITY)
    else:
        stamp = order_value * STAMP_DUTY_BUY
    gst = GST_RATE * (b + txn + sebi)
    return b + txn + sebi + stt + stamp + gst


def round_trip_cost(buy_value: float, sell_value: float | None = None, etf: bool = False) -> float:
    sv = buy_value if sell_value is None else sell_value
    return leg_cost(buy_value, 'BUY', etf) + leg_cost(sv, 'SELL', etf)


def round_trip_pct(position_value: float, etf: bool = False) -> float:
    if position_value <= 0:
        return 0.0
    return round_trip_cost(position_value, position_value, etf) / position_value * 100


def breakeven_move_pct(position_value: float, etf: bool = False, spread_pct: float = 0.03) -> float:
    return round_trip_pct(position_value, etf) + spread_pct


STT_DELIVERY = 0.001
STT_DELIVERY_SELL_ETF = 0.00001
STAMP_DUTY_DELIVERY_BUY = 0.00015
DP_CHARGE = 15.93


def delivery_cost(action: str, value: float, etf: bool = False) -> float:
    if etf:
        stt = 0.0 if action == 'BUY' else STT_DELIVERY_SELL_ETF * value
    else:
        stt = STT_DELIVERY * value
    txn = EXCH_TXN_NSE * value
    sebi = SEBI_CHARGE * value
    gst = GST_RATE * (txn + sebi)
    if action == 'BUY':
        return stt + STAMP_DUTY_DELIVERY_BUY * value + txn + sebi + gst
    return stt + txn + sebi + gst + DP_CHARGE
