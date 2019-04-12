import pandas as pd
import numpy as np
import statsmodels.api as sm


def get_variogram(ts, n_lags):
    lags = pd.Series(range(1, 1 + n_lags), name='Lag')
    lagged = pd.concat([ts.diff(h) for h in lags], keys=lags)
    return (lagged**2).groupby('Lag').mean()

def get_hurst(variogram):
    regressors = sm.add_constant(np.log(variogram.index.to_frame(index=False)))
    ols = sm.OLS(np.log(variogram), regressors).fit()
    return ols.params['Lag']/2
