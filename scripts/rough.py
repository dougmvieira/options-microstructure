from argparse import ArgumentParser

import pandas as pd
import numpy as np
import statsmodels.api as sm
from matplotlib.dates import DateFormatter


def get_variogram(ts, n_lags):
    lags = pd.Series(range(1, 1 + n_lags), name='Lag')
    lagged = pd.concat([ts.diff(h).dropna() for h in lags], keys=lags)
    variogram = (lagged**2).groupby('Lag').mean()
    variogram.name = 'Variogram'
    return variogram


def get_hurst(variogram):
    regressors = sm.add_constant(np.log(variogram.index.to_frame(index=False)))
    ols = sm.OLS(np.log(variogram.values), regressors).fit()
    return ols.params['Lag']/2


def clean(ts):
    diffs = ts.diff()
    return ts[~(diffs.abs() > 3*diffs.std())]


def plot_vols(heston_vols, implied_vols, heston_params):
    vols = pd.concat([np.sqrt(heston_vols), implied_vols],
                     keys=['Heston', 'Implied'], axis=1)
    vols['Long-term'] = np.sqrt(heston_params['$\theta$'])
    vols.index.name = 'Time'

    ax = vols.plot()
    ax.set_ylabel('Volatility')
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    return ax.get_figure()


def plot_variogram(vols, **plot_kwargs):
    variogram = get_variogram(vols, 100)
    hurst_index = get_hurst(variogram.iloc[:10])

    x = np.log(variogram.index.values)
    fit_line = np.exp(np.log(variogram.values[0]) + 2*hurst_index*(x - x[0]))
    fit_line = pd.Series(fit_line, variogram.index)

    ax = fit_line.plot(label='$H = {:.3f}$'.format(hurst_index), logx=False,
                       logy=False, legend=True, **plot_kwargs)
    colour = ax.get_lines()[-1].get_color()
    ax = variogram.reset_index(
                 ).plot.scatter(x='Lag', y='Variogram', logx=True, logy=True,
                                ax=ax, label=vols.name, c=colour)

    return ax


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('option')
    cli.add_argument('src_implied_vols_filename')
    cli.add_argument('src_heston_vols_filename')
    cli.add_argument('src_heston_params_filename')
    cli.add_argument('dest_vols_filename')
    cli.add_argument('dest_variogram_filename')
    args = cli.parse_args()

    implied_vols = pd.read_parquet(args.src_implied_vols_filename)
    implied_vols = implied_vols.loc[eval(args.option)]
    implied_vols = clean(implied_vols.mean(axis=1))
    implied_vols.name = 'Implied volatility'

    heston_vols = pd.read_parquet(args.src_heston_vols_filename)['Volatility']
    heston_vols = clean(heston_vols)
    heston_vols.name = 'Heston volatility'

    heston_params = pd.read_parquet(args.src_heston_params_filename)['Value']

    fig = plot_vols(heston_vols, implied_vols, heston_params)
    fig.savefig(args.dest_vols_filename)
    fig.clf()

    ax = plot_variogram(heston_vols)
    ax = plot_variogram(implied_vols, ax=ax)

    ax.get_figure().savefig(args.dest_variogram_filename)
