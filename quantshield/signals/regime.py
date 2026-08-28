from typing import Any

import pandas as pd

RegimeResult = tuple[str, float, dict[str, Any]]


def _new_scores() -> dict[str, int]:
    return {'risk_on': 0, 'risk_off': 0, 'crisis': 0}


def _vix_trend_vote(vix: pd.Series, scores: dict[str, int], details: dict[str, Any]) -> None:
    if len(vix) < 50:
        details['vix_sma50'] = None
        details['vix_trend'] = 'unavailable'
        return
    current = vix.iloc[-1]
    sma50 = vix.rolling(50).mean().iloc[-1]
    details['vix_sma50'] = round(sma50, 1)
    if current > sma50 * 1.2:
        scores['crisis'] += 1
        details['vix_trend'] = 'rising_fast'
    elif current > sma50:
        scores['risk_off'] += 1
        details['vix_trend'] = 'rising'
    else:
        scores['risk_on'] += 1
        details['vix_trend'] = 'falling'


def _scores_to_regime(scores: dict[str, int], details: dict[str, Any], block_risk_on: bool = False) -> RegimeResult:
    total = sum(scores.values()) or 1
    detected = max(scores, key=scores.get)
    if detected == 'risk_on' and block_risk_on:
        detected = 'risk_off'
        details['oil_override'] = 'Oil above 90 USD blocks risk_on. Downgraded to risk_off.'
    confidence = scores[detected] / total
    details['regime_scores'] = scores
    details['regime_probs'] = {k: round(v / total, 3) for k, v in scores.items()}
    details['detected_regime'] = detected
    details['confidence'] = round(confidence, 2)
    return detected, confidence, details


def us_detect_regime(macro_close: pd.DataFrame) -> RegimeResult:
    scores = _new_scores()
    details: dict[str, Any] = {}

    if '^VIX' in macro_close.columns:
        vix = macro_close['^VIX']
        current_vix = vix.iloc[-1]
        details['vix_current'] = round(current_vix, 1)
        if current_vix < 15:
            scores['risk_on'] += 3
        elif current_vix < 20:
            scores['risk_on'] += 2
        elif current_vix < 25:
            scores['risk_off'] += 2
        elif current_vix < 30:
            scores['risk_off'] += 2
            scores['crisis'] += 1
        elif current_vix < 35:
            scores['crisis'] += 2
            scores['risk_off'] += 1
        else:
            scores['crisis'] += 3
        _vix_trend_vote(vix, scores, details)
    else:
        details['vix_current'] = None
        details['vix_trend'] = 'unavailable'

    if 'GLD' in macro_close.columns:
        gld = macro_close['GLD']
        gld_ret_1m = (gld.iloc[-1] / gld.iloc[-21] - 1) if len(gld) >= 21 else 0
        gld_ret_3m = (gld.iloc[-1] / gld.iloc[-63] - 1) if len(gld) >= 63 else 0
        details['gold_1m_return'] = round(gld_ret_1m * 100, 1)
        details['gold_3m_return'] = round(gld_ret_3m * 100, 1)
        if gld_ret_1m > 0.05:
            scores['crisis'] += 2
        elif gld_ret_1m > 0.02:
            scores['risk_off'] += 1
        else:
            scores['risk_on'] += 1

    if 'USO' in macro_close.columns:
        uso = macro_close['USO']
        oil_ret_1m = (uso.iloc[-1] / uso.iloc[-21] - 1) if len(uso) >= 21 else 0
        details['oil_1m_return'] = round(oil_ret_1m * 100, 1)
        if oil_ret_1m > 0.10:
            scores['crisis'] += 2
        elif oil_ret_1m > 0.05:
            scores['risk_off'] += 1
        elif oil_ret_1m < -0.05:
            scores['risk_on'] += 1

    if 'UUP' in macro_close.columns:
        uup = macro_close['UUP']
        dollar_ret_1m = (uup.iloc[-1] / uup.iloc[-21] - 1) if len(uup) >= 21 else 0
        details['dollar_1m_return'] = round(dollar_ret_1m * 100, 1)
        if dollar_ret_1m > 0.02:
            scores['risk_off'] += 1
        elif dollar_ret_1m < -0.02:
            scores['risk_on'] += 1

    if '^TNX' in macro_close.columns:
        tnx = macro_close['^TNX']
        current_yield = tnx.iloc[-1]
        yield_1m_ago = tnx.iloc[-21] if len(tnx) >= 21 else current_yield
        yield_change = current_yield - yield_1m_ago
        details['treasury_10y'] = round(current_yield, 2)
        details['yield_1m_change'] = round(yield_change, 2)
        if yield_change > 0.3:
            scores['risk_off'] += 2
        elif yield_change > 0.1:
            scores['risk_off'] += 1
        elif yield_change < -0.3:
            scores['risk_on'] += 1

    return _scores_to_regime(scores, details)


def india_detect_regime(macro_close: pd.DataFrame) -> RegimeResult:
    scores = _new_scores()
    details: dict[str, Any] = {}

    if '^INDIAVIX' in macro_close.columns:
        vix = macro_close['^INDIAVIX']
        current_vix = vix.iloc[-1]
        details['vix_current'] = round(current_vix, 1)
        if current_vix < 15:
            scores['risk_on'] += 3
        elif current_vix < 22:
            scores['risk_off'] += 2
        else:
            scores['crisis'] += 3
        _vix_trend_vote(vix, scores, details)
    else:
        details['vix_current'] = None
        details['vix_trend'] = 'unavailable'

    if 'USDINR=X' in macro_close.columns:
        usdinr = macro_close['USDINR=X']
        details['usdinr'] = round(float(usdinr.iloc[-1]), 2)
        if len(usdinr) >= 21:
            rupee_change = (usdinr.iloc[-1] / usdinr.iloc[-21] - 1) * 100
            details['rupee_1m_change'] = round(rupee_change, 2)
            if rupee_change > 4:
                scores['crisis'] += 1
            elif rupee_change > 2:
                scores['risk_off'] += 1
            elif rupee_change < -1:
                scores['risk_on'] += 1

    oil_blocks_risk_on = False
    if 'CL=F' in macro_close.columns:
        oil = macro_close['CL=F']
        oil_level = float(oil.iloc[-1])
        details['oil_level'] = round(oil_level, 1)
        if oil_level > 90:
            scores['risk_off'] += 1
            oil_blocks_risk_on = True
        if len(oil) >= 21:
            oil_ret = (oil.iloc[-1] / oil.iloc[-21] - 1) * 100
            details['oil_1m_return'] = round(oil_ret, 1)
            if oil_ret > 15 and oil_level > 90:
                scores['crisis'] += 1
            if oil_ret > 10:
                scores['crisis'] += 2
            elif oil_ret > 5:
                scores['risk_off'] += 1
            elif oil_ret < -5:
                scores['risk_on'] += 1

    if '^NSEI' in macro_close.columns:
        nifty = macro_close['^NSEI']
        if len(nifty) >= 50:
            nifty_sma50 = nifty.rolling(50).mean().iloc[-1]
            nifty_current = nifty.iloc[-1]
            details['nifty_current'] = round(nifty_current, 1)
            if nifty_current > nifty_sma50:
                scores['risk_on'] += 1
            else:
                scores['risk_off'] += 1

    return _scores_to_regime(scores, details, block_risk_on=oil_blocks_risk_on)
