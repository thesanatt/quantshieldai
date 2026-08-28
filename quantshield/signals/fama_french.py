import io
import zipfile
from typing import Any

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

from quantshield.utils import log

KEN_FRENCH_BASE = 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/'
FF5_FILE = 'F-F_Research_Data_5_Factors_2x3_CSV.zip'
MOM_FILE = 'F-F_Momentum_Factor_CSV.zip'
FACTOR_COLS = ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom']
MIN_MONTHS = 12

_FF_CACHE: dict[str, pd.DataFrame] = {}


def _parse_monthly(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line[:6].isdigit() and line[6:7] == ',')
    end = next((i for i in range(start, len(lines)) if not lines[i].strip()), len(lines))
    frame = pd.read_csv(io.StringIO('\n'.join(lines[start - 1:end])), index_col=0)
    frame.columns = [str(c).strip() for c in frame.columns]
    frame.index = pd.to_datetime(frame.index.astype(str), format='%Y%m')
    return frame.replace([-99.99, -999.0], np.nan) / 100.0


def _download_monthly(file_name: str) -> pd.DataFrame:
    resp = requests.get(KEN_FRENCH_BASE + file_name, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        text = archive.read(archive.namelist()[0]).decode('latin-1')
    return _parse_monthly(text)


def _month_start(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).to_period('M').to_timestamp()


def get_factor_data(start_date: str, end_date: str) -> pd.DataFrame | None:
    if 'monthly' not in _FF_CACHE:
        try:
            ff5 = _download_monthly(FF5_FILE)
            mom = _download_monthly(MOM_FILE)
        except Exception as exc:
            log(f'Ken French factor download failed: {exc}')
            return None
        _FF_CACHE['monthly'] = ff5.join(mom['Mom'], how='inner')
    window = _FF_CACHE['monthly'].loc[_month_start(start_date):_month_start(end_date)]
    if len(window) < MIN_MONTHS:
        return None
    return window


def _to_calendar_months(monthly_returns: pd.Series) -> pd.Series:
    clean = monthly_returns.dropna().astype(float)
    months = pd.DatetimeIndex(clean.index).to_period('M').to_timestamp()
    return (1.0 + clean).groupby(months).prod() - 1.0


def decompose_returns(portfolio_monthly_returns: pd.Series) -> dict[str, Any]:
    port = _to_calendar_months(portfolio_monthly_returns)
    if len(port) < MIN_MONTHS:
        return {'error': 'insufficient_data', 'n_months': int(len(port))}

    factors = get_factor_data(str(port.index.min().date()), str(port.index.max().date()))
    if factors is None:
        return {'error': 'factor_data_unavailable', 'n_months': int(len(port))}

    cols = [c for c in FACTOR_COLS if c in factors.columns]
    common = port.index.intersection(factors.dropna(subset=cols).index)
    if len(common) < MIN_MONTHS:
        return {'error': 'insufficient_overlap', 'n_months': int(len(common))}

    rf = factors.loc[common, 'RF'].to_numpy() if 'RF' in factors.columns else np.zeros(len(common))
    excess = port.loc[common].to_numpy() - rf
    design = sm.add_constant(factors.loc[common, cols].to_numpy())
    lags = max(1, int(len(common) ** (1.0 / 3.0)))
    try:
        fit = sm.OLS(excess, design).fit(cov_type='HAC', cov_kwds={'maxlags': lags})
    except Exception as exc:
        return {'error': 'regression_failed', 'detail': str(exc), 'n_months': int(len(common))}

    alpha = float(fit.params[0])
    return {
        'alpha': round(alpha, 6),
        'alpha_tstat': round(float(fit.tvalues[0]), 4),
        'alpha_pvalue': round(float(fit.pvalues[0]), 4),
        'factor_betas': {
            col: {
                'beta': round(float(fit.params[j + 1]), 6),
                'tstat': round(float(fit.tvalues[j + 1]), 4),
                'pvalue': round(float(fit.pvalues[j + 1]), 4),
            }
            for j, col in enumerate(cols)
        },
        'r_squared': round(float(fit.rsquared), 4),
        'residual_alpha_annualized': round(alpha * 12.0, 4),
        'n_months': int(len(common)),
        'factors_used': cols,
        'newey_west_lags': lags,
    }
