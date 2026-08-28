import pytest

from quantshield import costs as ic


def test_equity_round_trip_pct_small_size() -> None:
    pct = ic.round_trip_pct(2000, etf=False)
    assert 0.100 <= pct <= 0.112


def test_etf_round_trip_pct_small_size() -> None:
    pct = ic.round_trip_pct(2000, etf=True)
    assert 0.100 <= pct <= 0.112
    assert pct == pytest.approx(ic.round_trip_pct(2000, etf=False))


def test_brokerage_cap_binds_at_large_size() -> None:
    assert ic.brokerage(100000) == pytest.approx(20.0)
    assert ic.brokerage(50000) == pytest.approx(15.0)
    assert ic.round_trip_pct(200000, etf=False) < ic.round_trip_pct(2000, etf=False)


def test_leg_cost_sides() -> None:
    assert ic.leg_cost(2000, 'SELL') > ic.leg_cost(2000, 'BUY')
    assert ic.leg_cost(0, 'BUY') == 0.0
    assert ic.leg_cost(-5, 'SELL') == 0.0


def test_intraday_etf_sell_pays_same_stt_as_equity() -> None:
    eq = ic.leg_cost(2000, 'SELL', etf=False)
    etf = ic.leg_cost(2000, 'SELL', etf=True)
    assert ic.STT_INTRADAY_SELL_ETF == ic.STT_INTRADAY_SELL_EQUITY
    assert eq == pytest.approx(etf)


def test_breakeven_includes_spread() -> None:
    assert ic.breakeven_move_pct(2000, etf=True, spread_pct=0.03) == pytest.approx(
        ic.round_trip_pct(2000, etf=True) + 0.03
    )


def test_squareoff_penalty_constant() -> None:
    assert ic.MIS_SQUAREOFF_PENALTY == pytest.approx(59.0)


def test_round_trip_asymmetric_values() -> None:
    c = ic.round_trip_cost(2000, 1900, etf=False)
    assert c == pytest.approx(ic.leg_cost(2000, 'BUY') + ic.leg_cost(1900, 'SELL'))


def test_round_trip_pct_zero_value() -> None:
    assert ic.round_trip_pct(0) == 0.0


def test_delivery_buy_has_stamp_duty_and_no_dp_charge() -> None:
    value = 3000.0
    buy = ic.delivery_cost('BUY', value)
    expected = (ic.STT_DELIVERY + ic.STAMP_DUTY_DELIVERY_BUY + ic.EXCH_TXN_NSE + ic.SEBI_CHARGE) * value
    expected += ic.GST_RATE * (ic.EXCH_TXN_NSE + ic.SEBI_CHARGE) * value
    assert buy == pytest.approx(expected)
    assert buy < ic.DP_CHARGE


def test_delivery_sell_adds_dp_charge() -> None:
    value = 3000.0
    sell = ic.delivery_cost('SELL', value)
    expected = (ic.STT_DELIVERY + ic.EXCH_TXN_NSE + ic.SEBI_CHARGE) * value
    expected += ic.GST_RATE * (ic.EXCH_TXN_NSE + ic.SEBI_CHARGE) * value + ic.DP_CHARGE
    assert sell == pytest.approx(expected)
    assert sell - ic.delivery_cost('BUY', value) == pytest.approx(ic.DP_CHARGE - ic.STAMP_DUTY_DELIVERY_BUY * value)


def test_delivery_etf_stt_is_lower() -> None:
    value = 3000.0
    assert ic.delivery_cost('BUY', value, etf=True) == pytest.approx(ic.delivery_cost('BUY', value) - ic.STT_DELIVERY * value)
    eq_sell = ic.delivery_cost('SELL', value)
    etf_sell = ic.delivery_cost('SELL', value, etf=True)
    assert eq_sell - etf_sell == pytest.approx((ic.STT_DELIVERY - ic.STT_DELIVERY_SELL_ETF) * value)


@pytest.mark.parametrize('action,etf,expected', [
    ('BUY', False, 2.372452),
    ('SELL', False, 18.002452),
    ('BUY', True, 0.372452),
    ('SELL', True, 16.022452),
])
def test_delivery_cost_literal_values_on_2000(action: str, etf: bool, expected: float) -> None:
    assert ic.delivery_cost(action, 2000.0, etf=etf) == pytest.approx(expected, abs=1e-6)


def test_delivery_cost_hand_formula_on_2000() -> None:
    txn = 2000.0 * 0.0000297
    sebi = 2000.0 * 0.000001
    gst = 0.18 * (txn + sebi)
    assert ic.delivery_cost('BUY', 2000.0) == pytest.approx(2.0 + 0.30 + txn + sebi + gst, abs=1e-9)
    assert ic.delivery_cost('SELL', 2000.0) == pytest.approx(2.0 + txn + sebi + gst + 15.93, abs=1e-9)
    assert ic.delivery_cost('SELL', 2000.0, etf=True) == pytest.approx(0.02 + txn + sebi + gst + 15.93, abs=1e-9)
    assert ic.delivery_cost('SELL', 2000.0, etf=True) < ic.delivery_cost('SELL', 2000.0)
    assert ic.delivery_cost('BUY', 2000.0, etf=True) < ic.delivery_cost('BUY', 2000.0)
