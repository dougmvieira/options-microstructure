from argparse import ArgumentParser
from itertools import starmap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fyne import blackscholes, heston
from matplotlib.patches import Patch
from scipy.stats import gaussian_kde

from align_settings import STARTTIME, ENDTIME
from utils import resample


def safe_xs(*args, **kwargs):
    try:
        return pd.Series.xs(*args, **kwargs)
    except KeyError:
        return np.nan


def get_tick_size(quote):
    diffs = (quote['Ask'] + quote['Bid']).diff()
    diffs = diffs[diffs > 1e-6]
    return np.round(diffs.min(), 2)


def build_cov_mat(underlying, strikes, expiry, vol, kappa, theta, nu, rho):
    rho_mat = np.array([[1, rho], [rho, 1]])
    vol_vec = np.array([np.sqrt(vol)*underlying, np.sqrt(vol)*nu])
    factors_cov_mat = rho_mat * vol_vec[:, None].dot(vol_vec[None, :])

    option_prices = heston.formula(underlying, strikes, expiry, vol, kappa,
                                   theta, nu, rho)
    implied_vols = blackscholes.implied_vol(underlying, strikes, expiry,
                                            option_prices)
    deltas = heston.delta(underlying, strikes, expiry, vol, kappa, theta, nu,
                          rho)
    heston_vegas = heston.vega(underlying, strikes, expiry, vol, kappa, theta,
                               nu, rho)
    implied_vol_deltas = 10*(
        blackscholes.implied_vol(underlying + 0.05, strikes, expiry,
                                 option_prices)
        - blackscholes.implied_vol(underlying - 0.05, strikes, expiry,
                                   option_prices))
    blackscholes_vegas = blackscholes.vega(underlying, strikes, expiry,
                                           implied_vols)
    greeks = np.stack([deltas/blackscholes_vegas + implied_vol_deltas,
                       heston_vegas/blackscholes_vegas], axis=-1)

    return greeks @ factors_cov_mat @ greeks.T


def filter_tick_size(data, quote, size):
    tick_size = quote.groupby('Strike').apply(get_tick_size)
    return data.reindex(tick_size[tick_size == size].index, level='Strike')


def filter_trade_on_book(quote, trade):
    max_expiry = np.max(quote.index.get_level_values('Expiry'))
    trade = trade[trade.index.get_level_values('Expiry') <= max_expiry]

    quote_aligned = trade.groupby(['Class', 'Expiry', 'Strike']
                        ).apply(lambda o: resample(quote.xs(o.name),
                                                   o.xs(o.name).index))
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
    time['Duration'] = time['Time'].groupby(['Class', 'Expiry', 'Strike']
                                  ).transform(lambda t: t.diff().shift(-1))
    time['Time'] += time['Duration']/2

    duration = time.set_index('Time', append=True)['Duration']
    duration /= pd.to_timedelta('1s')

    return duration


def compute_volume_duration(quote, trade):
    trade = filter_trade_on_book(quote, trade)
    volume = trade.set_index(['Depth', 'Buy'], append=True)['Volume']
    duration = compute_duration(quote)

    return volume, duration


def plot_arrival_rates_bubbles(volume, duration):
    volume = volume.groupby(['Class', 'Expiry', 'Strike', 'Depth', 'Buy']
                  ).sum()
    duration = duration.groupby(['Class', 'Expiry', 'Strike',
                                 'Depth']).sum()

    duration = duration[duration > 300]
    arrival_rate = volume.groupby(['Class', 'Expiry', 'Strike', 'Depth']
                        ).transform(lambda d: d.xs(d.name
                                              )/safe_xs(duration, d.name))
    arrival_rate.name = 'Arrival rate'

    fig, axes = plt.subplots(3, 2, sharey=True, sharex=True)
    patches = [Patch(color='b', alpha=.5, label='Call'),
               Patch(color='r', alpha=.5, label='Put')]
    axes[0, 1].legend(handles=patches)

    for row, (e, r_ex) in zip(axes, arrival_rate.groupby('Expiry')):
        for bs in ['Buy', 'Sell']:
            ax = row[0] if bs == 'Buy' else row[1]
            ax.set_title("Expiry: {}, {}".format(
                pd.to_datetime(e).strftime('%Y-%m-%d'), bs))

            for cp, cl in [('C', 'b'), ('P', 'r')]:
                r = r_ex.xs((cp, bs == 'Buy'), level=('Class', 'Buy'))
                r.reset_index(['Strike', 'Depth']).plot.scatter(
                    x='Strike', y='Depth', s=20*r/r_ex.mean(), ax=ax,
                    xlim=(325, 550), ylim=(0, None), alpha=.5, color=cl)

    return fig


def find_quantiles(s):
    return s.index[np.searchsorted(s.cumsum()/s.sum(), [.25, .5, .75])]


def build_quartiles(volume, duration, quote):
    tick_size = quote.groupby('Strike').apply(get_tick_size)
    duration = duration.reindex(tick_size[tick_size == 0.05].index,
                                level='Strike')
    volume = volume.groupby(['Strike', 'Depth']).sum()
    volume = volume.reindex(tick_size[tick_size == 0.05].index, level='Strike')
    strikes = find_quantiles(volume.groupby('Strike').sum())

    slices = list(starmap(slice, zip([None, *strikes], [*strikes, None])))
    volume_quartiles = [volume.loc[s].groupby('Depth').sum() for s in slices]

    duration_quartiles = [duration.loc[volume.loc[s].index
                                 ].groupby('Depth').sum() for s in slices]
    arrival_rate_quartiles = [
        v/d for v, d in zip(volume_quartiles, duration_quartiles)]

    keys = pd.Index([1, 2, 3, 4], name='Quartile')
    volume_quartiles = pd.concat(volume_quartiles, keys=keys)
    duration_quartiles = pd.concat(duration_quartiles, keys=keys)
    arrival_rate_quartiles = pd.concat(arrival_rate_quartiles, keys=keys)

    return arrival_rate_quartiles, volume_quartiles, duration_quartiles


def plot_quartiles(volume, duration, quote):
    volume = volume.groupby(['Class', 'Expiry', 'Strike', 'Depth', 'Buy']
                  ).sum()
    duration = duration.groupby(['Class', 'Expiry', 'Strike',
                                 'Depth']).sum()

    sel_call = map(lambda s: s.xs(('C', pd.to_datetime('2016-02-19'))),
                   [volume, duration, quote])
    sel_put = map(lambda s: s.xs(('P', pd.to_datetime('2016-02-19'))),
                  [volume, duration, quote])
    arrival_rate_call, volume_call, duration_call = build_quartiles(*sel_call)
    arrival_rate_put, volume_put, duration_put = build_quartiles(*sel_put)

    fig, axes = plt.subplots(3, 2, sharex=True)
    arrival_rate_call.unstack('Quartile').loc[0.:].plot(ax=axes[0, 0], logy=True, xlim=(None, .225), ylim=(None, 10))
    volume_call.unstack('Quartile').loc[0:].plot(ax=axes[1, 0], logy=True, xlim=(None, .225))
    duration_call.unstack('Quartile').loc[0:].plot(ax=axes[2, 0], logy=True, xlim=(None, .225))
    arrival_rate_put.unstack('Quartile').loc[0.:].plot(ax=axes[0, 1], logy=True, xlim=(None, .225), ylim=(None, 10))
    volume_put.unstack('Quartile').loc[0:].plot(ax=axes[1, 1], logy=True, xlim=(None, .225))
    duration_put.unstack('Quartile').loc[0:].plot(ax=axes[2, 1], logy=True, xlim=(None, .225))
    axes[0, 0].set_title('Arrival rate, Call')
    axes[1, 0].set_title('Volume, Call')
    axes[2, 0].set_title('Duration, Call')
    axes[0, 1].set_title('Arrival rate, Put')
    axes[1, 1].set_title('Volume, Put')
    axes[2, 1].set_title('Duration, Put')

    return fig


def plot_arrival_rates(arrival_rate):
    depths = arrival_rate.index.get_level_values('Depth')
    arrival_rate = arrival_rate[depths > 0].dropna()
    bandwidth = 0.25
    levels = ['Class', 'Expiry', 'Buy']
    kernel = arrival_rate.groupby(levels).apply(
        lambda r: gaussian_kde(np.stack(r.xs(r.name, level=levels).index, axis=-1),
                               bandwidth, r.values))

    xlen, ylen = 200, 150
    xmin, xmax, ymin, ymax = -0.2, 0.15, 0.0, 0.3
    x = np.linspace(xmin, xmax, xlen)
    y = np.linspace(ymin, ymax, ylen)
    x_b, y_b = np.broadcast_arrays(x[:, None], y[None, :])

    fig, axes = plt.subplots(3, 2, sharex=True, sharey=True, figsize=(8, 10))
    patches = [Patch(color='tab:blue', label='Call'),
               Patch(color='tab:red', label='Put')]
    axes[0, 1].legend(handles=patches)
    for row, (e, k) in zip(axes, kernel.groupby('Expiry')):
        row[0].set_title("Expiry: {}, Buy".format(
            pd.to_datetime(e).strftime('%Y-%m-%d')))
        row[1].set_title("Expiry: {}, Sell".format(
            pd.to_datetime(e).strftime('%Y-%m-%d')))
        for cp, cm in [('C', plt.cm.Blues), ('P', plt.cm.Reds)]:
            z = k.xs((cp, e, True))(np.array([x_b.ravel(), y_b.ravel()]))
            z = np.rot90(np.reshape(z, x_b.shape))
            row[0].imshow(z, extent=[xmin, xmax, ymin, ymax], cmap=cm,
                          aspect='auto', alpha=.5)
            z = k.xs((cp, e, False))(np.array([x_b.ravel(), y_b.ravel()]))
            z = np.rot90(np.reshape(z, x_b.shape))
            row[1].imshow(z, extent=[xmin, xmax, ymin, ymax], cmap=cm,
                          aspect='auto', alpha=.5)

    return fig


def quote_slice(quote, start, end):
    quote = quote.copy()
    quote.loc[start] = np.nan
    quote.sort_index(inplace=True)
    quote.ffill(inplace=True)
    return quote.loc[start:end]


def plot_intraday(volume, duration):
    filtered_volume = volume.groupby(['Class',  'Expiry']).apply(lambda e: filter_tick_size(e.xs(e.name), quote.xs(e.name), 0.05))
    filtered_duration = duration.groupby(['Class', 'Expiry']).apply(lambda e: e.xs(e.name).reindex(np.unique(filtered_volume.xs(e.name).index.get_level_values('Strike')), level='Strike').dropna())
    filtered_duration = filtered_duration.groupby(['Class', 'Expiry', 'Strike']).apply(lambda o: o.xs(o.name).reindex(np.unique(filtered_volume.xs(o.name).index.get_level_values('Depth')), level='Depth').dropna())
    volume_by_depth = filtered_volume.groupby('Expiry').apply(lambda e: e.groupby('Depth').sum().loc[.025:.225])
    duration_by_depth = filtered_duration.groupby('Expiry').apply(lambda e: e.groupby('Depth').sum().loc[.025:.225])
    volume_kde = filtered_volume.groupby('Expiry').apply(lambda e: e.groupby(['Depth', 'Time']).sum().loc[.025:.225].groupby('Depth').apply(lambda d: gaussian_kde((d.xs(d.name).index - pd.to_datetime('2016-01-04'))/pd.to_timedelta('1s'), weights=d, bw_method=.25)))
    duration_kde = filtered_duration.groupby('Expiry').apply(lambda e: e.groupby(['Depth', 'Time']).sum().loc[.025:.225].groupby('Depth').apply(lambda d: gaussian_kde((d.xs(d.name).index - pd.to_datetime('2016-01-04'))/pd.to_timedelta('1s'), weights=d, bw_method=.05)))

    fig_volume, axes = plt.subplots(3, 1, sharex=True)
    tmin, tmax = 8*3600, 16.5*3600
    t = np.linspace(tmin, tmax, 100)
    for ax, (e, v) in zip(axes, volume_kde.groupby('Expiry')):
        z = volume_by_depth.xs(e).values*np.array([k.xs(d)(t) for d, k in v.xs(e).groupby('Depth')]).T
        ax.imshow(np.rot90(z), extent=[tmin/3600, tmax/3600, 0.025, 0.225], aspect='auto')
        ax.set_ylabel('Depth (€)')
        ax.set_title('Expiry: {}'.format(pd.to_datetime(e).strftime('%Y-%m-%d')))
    ax.set_xlabel('Time (hours)')
    fig_volume.tight_layout()

    fig_duration, axes = plt.subplots(3, 1, sharex=True)
    tmin, tmax = 8*3600, 16.5*3600
    t = np.linspace(tmin, tmax, 100)
    for ax, (e, du) in zip(axes, duration_kde.groupby('Expiry')):
        z = duration_by_depth.xs(e).values*np.array([k.xs(d)(t) for d, k in du.xs(e).groupby('Depth')]).T
        ax.imshow(np.rot90(z), extent=[tmin/3600, tmax/3600, 0.025, 0.225], aspect='auto')
        ax.set_ylabel('Depth (€)')
        ax.set_title('Expiry: {}'.format(pd.to_datetime(e).strftime('%Y-%m-%d')))
    ax.set_xlabel('Time (hours)')
    fig_duration.tight_layout()

    fig_arrival, axes = plt.subplots(3, 1, sharex=True)
    tmin, tmax = 8*3600, 16.5*3600
    t = np.linspace(tmin, tmax, 100)
    for ax, (e, du), (_, v) in zip(axes, duration_kde.groupby('Expiry'), volume_kde.groupby('Expiry')):
        z_v = volume_by_depth.xs(e).values*np.array([k.xs(d)(t) for d, k in v.xs(e).groupby('Depth')]).T
        z_d = duration_by_depth.xs(e).values*np.array([k.xs(d)(t) for d, k in du.xs(e).groupby('Depth')]).T
        z = np.clip(z_v/z_d, 1e-3, 1e1)
        ax.imshow(np.rot90(np.log(z)), extent=[tmin/3600, tmax/3600, 0.025, 0.225], aspect='auto')
        ax.set_ylabel('Depth (€)')
        ax.set_title('Expiry: {}'.format(pd.to_datetime(e).strftime('%Y-%m-%d')))
    ax.set_xlabel('Time (hours)')
    fig_arrival.tight_layout()

    return fig_volume, fig_duration, fig_arrival


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('quote_filename')
    cli.add_argument('trade_filename')
    cli.add_argument('dest_bubbles_filename')
    cli.add_argument('dest_intraday_volume_filename')
    cli.add_argument('dest_intraday_duration_filename')
    cli.add_argument('dest_intraday_arrival_filename')
    cli.add_argument('dest_quartiles_filename')
    args = cli.parse_args()

    quote = pd.read_parquet(args.quote_filename)
    trade = pd.read_parquet(args.trade_filename).xs('AEX')

    quote.sort_index(inplace=True)
    volume, duration = compute_volume_duration(quote, trade)
    fig = plot_arrival_rates_bubbles(volume, duration)
    fig.savefig(args.dest_bubbles_filename)

    figs = plot_intraday(volume, duration)
    figs[0].savefig(args.dest_intraday_volume_filename)
    figs[1].savefig(args.dest_intraday_duration_filename)
    figs[2].savefig(args.dest_intraday_arrival_filename)

    quote = quote.groupby(['Class', 'Expiry', 'Strike']).apply(lambda o: quote_slice(o.xs(o.name), STARTTIME, ENDTIME))
    trade = trade.groupby(['Class', 'Expiry', 'Strike']).apply(lambda o: o.xs(o.name).loc[STARTTIME:ENDTIME])
    volume, duration = compute_volume_duration(quote, trade)
    fig = plot_quartiles(volume, duration, quote)
    fig.savefig(args.dest_quartiles_filename)
