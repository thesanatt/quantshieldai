import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform


def hrp_weights(returns: pd.DataFrame) -> pd.Series:
    cov = returns.cov()
    corr = returns.corr()
    dist = np.sqrt((1 - corr) / 2)
    dist_condensed = squareform(dist.values, checks=False)
    dist_condensed = np.nan_to_num(dist_condensed, nan=0.5, posinf=1.0, neginf=0.0)
    link = linkage(dist_condensed, method='ward')
    sort_ix = leaves_list(link)
    sorted_tickers = [corr.columns[i] for i in sort_ix]

    def get_cluster_var(cov: pd.DataFrame, tickers: list) -> float:
        cov_slice = cov.loc[tickers, tickers]
        diag = np.diag(cov_slice.values)
        diag = np.where(diag < 1e-10, 1e-10, diag)
        ivp = 1 / diag
        ivp /= ivp.sum()
        return np.dot(ivp, np.dot(cov_slice.values, ivp))

    def recursive_bisect(cov: pd.DataFrame, sorted_tickers: list) -> pd.Series:
        w = pd.Series(1.0, index=sorted_tickers)
        clusters = [sorted_tickers]
        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left, right = cluster[:mid], cluster[mid:]
                var_left = get_cluster_var(cov, left)
                var_right = get_cluster_var(cov, right)
                alpha = 1 - var_left / (var_left + var_right)
                w[left] *= alpha
                w[right] *= (1 - alpha)
                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)
            clusters = new_clusters
        return w / w.sum()

    return recursive_bisect(cov, sorted_tickers)
