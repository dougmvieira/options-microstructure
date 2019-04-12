import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.api import OLS


def plot_shades(bottom, upper, ax=None, **kwargs):
    if ax is None:
        _, ax = plt.subplots(**kwargs)

    for col in bottom.columns:
        ax.fill_between(bottom.index, bottom[col], upper[col], label=col)
    ax.legend(title=', '.join(bottom.columns.names))

    return ax


def is_consecutive_unique(df):
    is_value_uniq = df != df.shift()
    is_nan_uniq = ~(df.isnull() & df.isnull().shift()).fillna(False)
    return (is_value_uniq & is_nan_uniq).any(axis=1)


def resample(df, index):
    empty = pd.DataFrame(np.nan, pd.Index(index, name=df.index.name),
                         df.columns)
    return pd.concat([df, empty]).sort_index().ffill().loc[index]


def autorreg_correction(returns):
    return OLS(returns.iloc[1:], returns.shift().iloc[1:]).fit().fittedvalues


def build_discount_curve(calls_ask, calls_bid, puts_ask, puts_bid, strikes,
                         underlying_price):
    return pd.concat([(underlying_price - calls_ask + puts_bid)/strikes,
                      (underlying_price - calls_bid + puts_ask)/strikes],
                     axis=1, keys=['Bid', 'Ask'])
