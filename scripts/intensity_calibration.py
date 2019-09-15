from argparse import ArgumentParser
from itertools import starmap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch.bootstrap import StationaryBootstrap

from utils import resample
from align_settings import STARTTIME, ENDTIME


SESSIONSTART = pd.to_datetime('2016-01-04 08:00:00')
SESSIONEND = pd.to_datetime('2016-01-04 16:30:00')
TIMESTEP = pd.to_timedelta('1m')


def get_tick_size(quote):
    diffs = (quote['Ask'] + quote['Bid']).diff()
    diffs = diffs[diffs > 1e-6]
    return np.round(diffs.min(), 2)


def compute_grid(time, step):
    return pd.to_datetime(0) + step*np.floor((time - pd.to_datetime(0))/step)


def grid_trade(trade, step):
    gridded = trade.copy()
    gridded['Grid'] = compute_grid(trade.index, step)
    gridded.set_index('Grid', append=True, inplace=True)
    return gridded


def grid_quote(quote, time_grid, step):
    time_grid = pd.Index(time_grid, name=quote.index.name)
    grid_start = pd.DataFrame(np.nan, time_grid, quote.columns)
    grid_end = pd.DataFrame(np.nan, time_grid + step, quote.columns)
    gridded = pd.concat([quote, grid_start, grid_end])
    gridded.sort_index(inplace=True)
    gridded.ffill(inplace=True)
    gridded['Grid'] = compute_grid(gridded.index, step)
    gridded['Grid'] = gridded['Grid'].shift(fill_value=time_grid[0])
    gridded.set_index('Grid', append=True, inplace=True)
    return gridded


def grid_quote_trade(quote, trade):
    time_grid = np.arange(SESSIONSTART, SESSIONEND, TIMESTEP)
    quote_gridded = quote.groupby(['Class', 'Strike']
                        ).apply(lambda o: grid_quote(o.xs(o.name), time_grid,
                                                     TIMESTEP))
    trade_gridded = trade.groupby(['Class', 'Strike']
                        ).apply(lambda o: grid_trade(o.xs(o.name), TIMESTEP))

    return quote_gridded, trade_gridded


def filter_trade_on_book(quote, trade):
    quote_aligned = trade.groupby(['Class', 'Strike']
                        ).apply(lambda o: resample(quote.xs(o.name),
                                                   trade.xs(o.name).index))
    valid_trades = ((trade['Price'] == quote_aligned['Bid']) |
                    (trade['Price'] == quote_aligned['Ask']))

    filtered = trade[valid_trades]
    quote_aligned = quote_aligned.loc[valid_trades]
    filtered['Buy'] = filtered['Price'] == quote_aligned['Ask']
    filtered['Depth'] = (quote_aligned['Ask'] - quote_aligned['Bid']).round(2)/2

    return filtered


def compute_duration(quote):
    quote = quote.copy()
    quote['Depth'] = (quote['Ask'] - quote['Bid']).round(2)/2

    time = quote.reset_index('Time'
               ).set_index('Depth', append=True)[['Time']]
    time['Duration'] = time['Time'].groupby(['Class', 'Strike']
                                  ).transform(lambda t: t.diff().shift(-1))
    time['Time'] += time['Duration']/2

    duration = time.set_index('Time', append=True)['Duration']
    duration /= pd.to_timedelta('1s')

    return duration


def compute_volume_duration(quote, trade, expiry, tick_size):
    quote = quote.xs(expiry, level='Expiry')
    trade = trade.xs(expiry, level='Expiry')

    tick_sizes = quote.groupby(['Class', 'Strike']).apply(get_tick_size)
    strikes = tick_sizes[tick_sizes == tick_size]
    quote = quote.groupby('Class'
                ).apply(lambda c: c.xs(c.name).loc[strikes.xs(c.name).index])
    trade = trade.groupby('Class'
                ).apply(lambda c: c.xs(c.name).loc[strikes.xs(c.name).index])

    quote_gridded, trade_gridded = grid_quote_trade(quote, trade)
    filtered_trade = trade_gridded.groupby('Grid').apply(
        lambda o: filter_trade_on_book(quote_gridded.xs(o.name, level='Grid'), o.xs(o.name, level='Grid')))
    volume = filtered_trade.set_index(['Depth', 'Buy'], append=True)['Volume']
    duration = quote_gridded.groupby('Grid'
                           ).apply(lambda g: compute_duration(g.xs(g.name, level='Grid')))

    volume = volume.groupby(['Class', 'Strike', 'Depth', 'Buy', 'Grid']).sum()
    duration = duration.groupby(['Class', 'Strike', 'Depth', 'Grid']).sum()

    return volume, duration


def find_quantiles(s, quantile):
    quantiles = np.arange(0, 1 - quantile/2, quantile)
    left = np.searchsorted(s.cumsum()/s.sum(), quantiles)
    right = [*(left[1:] - 1), -1]
    return list(zip(s.index[left], s.index[right]))


def build_terciles(volume, duration):
    volume_by_strike = volume.groupby('Class').apply(lambda c: c.groupby('Strike').sum())
    strikes = volume_by_strike.groupby('Class').apply(lambda c: find_quantiles(c.xs(c.name), 1/3))
    volume = volume.groupby('Class').apply(lambda c: pd.concat([c.xs(c.name).loc[sl] for sl in starmap(slice, strikes.xs(c.name))], keys=range(3), names=['Tercile']))
    duration = duration.groupby('Class').apply(lambda c: pd.concat([c.xs(c.name).loc[sl] for sl in starmap(slice, strikes.xs(c.name))], keys=range(3), names=['Tercile']))
    volume = volume.groupby(['Class', 'Tercile', 'Depth', 'Grid']).sum()
    duration = duration.groupby(['Class', 'Tercile', 'Depth', 'Grid']).sum()
    volume_duration = pd.concat([volume, duration], axis=1,
                                keys=['Volume', 'Duration']).fillna(0)
    volume_duration = volume_duration.groupby(['Class', 'Tercile', 'Depth']
                                    ).apply(lambda d: d.xs(d.name
                                                      ).loc[STARTTIME:ENDTIME])

    return volume_duration, strikes


def plot_terciles(volume_duration, strikes):
    arrival_rate = volume_duration.groupby(['Class', 'Tercile', 'Depth']).sum()
    arrival_rate = arrival_rate.groupby(['Class', 'Tercile']
                              ).apply(lambda t: t.xs(t.name).loc[:.225])
    arrival_rate['Arrival rate'] = (
        arrival_rate['Volume']/arrival_rate['Duration'])

    fig, axes = plt.subplots(3, 2, sharex=True)
    for ax_row, name in zip(axes, ['Arrival rate', 'Volume', 'Duration']):
        for ax, payoff in zip(ax_row, ['Call', 'Put']):
            sel = arrival_rate.xs(payoff[0])[name].unstack('Tercile')
            sel.plot(ax=ax, logy=True)
            ax.set_title('{}, {}'.format(name, payoff))
            labels = ['{}-{}'.format(int(k1), int(k2))
                      for k1, k2 in strikes[payoff[0]]]
            ax.legend(labels, title='Strike range')

    return fig


def compute_arrival_rate(volume, duration):
    return np.log(volume.sum()/duration.sum())


def compute_gls_confint(volume_duration):
    volume_by_depth = volume_duration['Volume'].sum(level='Depth')
    volume_duration = volume_duration.loc[volume_by_depth.index[volume_by_depth > 30]]
    volume_duration = volume_duration.unstack('Depth')
    volume, duration = volume_duration['Volume'], volume_duration['Duration']
    sbs = StationaryBootstrap(15, volume=volume, duration=duration)
    depths = volume_duration['Volume'].columns
    sigma = sbs.cov(compute_arrival_rate)
    conf_int = pd.DataFrame(sbs.conf_int(compute_arrival_rate), ['2.5%', '97.5%'], depths).T

    arrival_rate = compute_arrival_rate(volume, duration)
    arrival_rate.name = 'Arrival rate'
    gls = sm.WLS(arrival_rate, sm.add_constant(arrival_rate.index), sigma=1/np.diag(sigma)).fit()
    fitted = gls.fittedvalues
    fitted.name = 'WLS fit'

    return map(np.exp, [arrival_rate, conf_int, fitted])


def plot_gls_confint(volume_duration, strikes):
    fig, axes = plt.subplots(3, 2, figsize=(16, 10))
    for (t, g1), ax_row in zip(volume_duration.groupby('Tercile'), axes):
        for (c, g2), ax in zip(g1.xs(t, level='Tercile').groupby('Class'), ax_row):
            arrival_rate, conf_int, fitted = compute_gls_confint(g2.xs(c))
            pd.concat([arrival_rate, fitted], axis=1).plot(logy='True', ax=ax)
            conf_int.plot(ax=ax, linestyle='dashed')
            ax.set_title('Tercile {}, {}'.format(t, 'Call' if c == 'C' else 'Put'))

    fig.tight_layout()
    return fig


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('expiry')
    cli.add_argument('tick_size')
    cli.add_argument('quote_filename')
    cli.add_argument('trade_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    expiry = pd.to_datetime(args.expiry)
    tick_size = float(args.tick_size)

    quote = pd.read_parquet(args.quote_filename)
    trade = pd.read_parquet(args.trade_filename).xs('AEX')

    quote.sort_index(inplace=True)

    volume, duration = compute_volume_duration(quote, trade, expiry, tick_size)
    volume_duration, strikes = build_terciles(volume, duration)

    fig = plot_gls_confint(volume_duration, strikes)
    fig.savefig(args.dest_filename)
