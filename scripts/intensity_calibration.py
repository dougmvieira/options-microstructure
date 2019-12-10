from argparse import ArgumentParser

import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch.bootstrap import StationaryBootstrap
from statsmodels.nonparametric.kernel_regression import KernelReg

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
    filtered['Half-spread'] = (quote_aligned['Ask'] - quote_aligned['Bid']).round(2)/2

    return filtered


def compute_duration(quote):
    quote = quote.copy()
    quote['Half-spread'] = (quote['Ask'] - quote['Bid']).round(2)/2

    time = quote.reset_index('Time'
               ).set_index('Half-spread', append=True)[['Time']]
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
        lambda o: filter_trade_on_book(quote_gridded.xs(o.name, level='Grid'),
                                       o.xs(o.name, level='Grid')))
    volume = filtered_trade.set_index(['Half-spread', 'Buy'], append=True)['Volume']
    duration = quote_gridded.groupby('Grid').apply(
        lambda g: compute_duration(g.xs(g.name, level='Grid')))

    volume = volume.groupby(['Class', 'Strike', 'Half-spread', 'Buy', 'Grid']).sum()
    duration = duration.groupby(['Class', 'Strike', 'Half-spread', 'Grid']).sum()

    return volume, duration


def find_quantiles(s, quantile):
    quantiles = np.arange(quantile, 1 - quantile/2, quantile)
    return s.index[np.searchsorted(s.cumsum()/s.sum(), quantiles)]


def build_quartiles(volume, duration):
    volume_by_strike = volume.groupby('Class').apply(lambda c: c.groupby('Strike').sum())
    strikes = volume_by_strike.groupby('Class').apply(
        lambda c: pd.Index(find_quantiles(c.xs(c.name), 1/4), name='Strike'))

    volume = volume.groupby(['Class', 'Strike', 'Half-spread', 'Grid']).sum()
    volume_duration = pd.concat(
        [o.xs((slice(STARTTIME, ENDTIME), slice(0.025, 0.100)),
              level=('Grid', 'Half-spread'), drop_level=False)
         for o in [volume, duration]], axis=1).fillna(0)

    return volume_duration, strikes


def compute_arrival_rate(volume, duration, strikes):
    volume_duration = pd.concat([volume.sum(), duration.sum()],
                                keys=['Volume', 'Duration'], axis=1)
    volume_duration_kernel = volume_duration.apply(
        lambda vd: vd.groupby('Half-spread').apply(
            lambda d: KernelReg(d.xs(d.name, level='Half-spread'),
                                d.xs(d.name, level='Half-spread').index,
                                'c', 'lc')))
    arrival_rate = volume_duration_kernel.apply(
        lambda vd: vd.groupby('Half-spread').apply(
            lambda k: pd.Series(k.xs(k.name).fit(strikes)[0], strikes)))
    return np.log(arrival_rate['Volume']/arrival_rate['Duration'])


def calibrate(volume_duration, strikes, reps):
    volume_duration = volume_duration.unstack(['Half-spread', 'Strike'])

    arrival_rate = volume_duration.groupby('Class').apply(
        lambda c: compute_arrival_rate(c.loc[c.name, 'Volume'],
                                       c.loc[c.name, 'Duration'],
                                       strikes[c.name]))
    arrival_rate.name = 'Arrival rate'
    arrival_rate.index = arrival_rate.index.reorder_levels(['Class', 'Strike',
                                                            'Half-spread'])

    sbs = volume_duration.groupby('Class').apply(
        lambda c: StationaryBootstrap(25, volume=c.loc[c.name, 'Volume'],
                                      duration=c.loc[c.name, 'Duration']))

    conf_int = sbs.groupby('Class').apply(lambda c: pd.DataFrame(
        c[c.name].conf_int(lambda volume, duration: compute_arrival_rate(
            volume, duration, strikes[c.name]), reps=reps),
        ['2.5%', '97.5%'], arrival_rate.loc[c.name].index))
    conf_int = conf_int.T.stack('Class')
    conf_int.index = conf_int.index.reorder_levels(['Class', 'Strike', 'Half-spread'])

    sigma = sbs.groupby('Class').apply(lambda c: pd.DataFrame(
        c[c.name].cov(lambda volume, duration: compute_arrival_rate(
            volume, duration, strikes[c.name]), reps=reps),
        arrival_rate.loc[c.name].index, arrival_rate.loc[c.name].index))
    sigma = sigma.groupby('Strike').apply(lambda k: k.xs(k.name, level='Strike',
                                                         axis=1))
    sigma.dropna(how='all', inplace=True)
    gls = arrival_rate.loc[sigma.index].groupby(['Class', 'Strike']).apply(
        lambda k: sm.GLS(k.values,
                         sm.add_constant(k.index.get_level_values('Half-spread')),
                         sigma=sigma.xs(k.name, level=['Class', 'Strike']
                                   ).dropna(axis=1)).fit())
    params = gls.apply(lambda g: pd.Series([np.exp(g.params[0]), -g.params[1]],
                                           ['A', '$\\kappa$']))
    base_conf_int = gls.apply(
        lambda g: pd.Series(np.exp(g.conf_int(alpha=.1)[0]), ['A 5%', 'A 95%']))
    decay_conf_int = gls.apply(
        lambda g: pd.Series(-g.conf_int(alpha=.1)[1, ::-1],
                            ['$\\kappa$ 5%', '$\\kappa$ 95%']))
    params = pd.concat([params, base_conf_int, decay_conf_int], axis=1)

    arrival_rate = np.exp(pd.concat([arrival_rate, conf_int], axis=1))
    return arrival_rate, params


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('expiry')
    cli.add_argument('tick_size')
    cli.add_argument('reps')
    cli.add_argument('quote_filename')
    cli.add_argument('trade_filename')
    cli.add_argument('dest_arrival_rate_filename')
    cli.add_argument('dest_params_filename')
    args = cli.parse_args()

    expiry = pd.to_datetime(args.expiry)
    tick_size = float(args.tick_size)

    quote = pd.read_parquet(args.quote_filename)
    trade = pd.read_parquet(args.trade_filename).xs('AEX')

    quote.sort_index(inplace=True)

    volume, duration = compute_volume_duration(quote, trade, expiry, tick_size)
    volume_duration, strikes = build_quartiles(volume, duration)
    arrival_rate, params = calibrate(volume_duration, strikes, int(args.reps))

    arrival_rate.to_parquet(args.dest_arrival_rate_filename)
    params.to_parquet(args.dest_params_filename)
