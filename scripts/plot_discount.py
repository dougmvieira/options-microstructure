from argparse import ArgumentParser

import pandas as pd
from matplotlib.dates import DateFormatter

import settings
from utils import plot_shades


def plot_tseries(tseries, plot_filename):
    expiries = tseries.index.levels[tseries.index.names.index('Expiry')]
    expiries = expiries.strftime('%Y-%m-%d')
    tseries.index.set_levels(expiries, 'Expiry', inplace=True)

    bid = tseries['Bid'].unstack(['Expiry', 'Strike'])
    ask = tseries['Ask'].unstack(['Expiry', 'Strike'])

    ax = plot_shades(bid, ask, **settings.PLOT)
    ax.set_ylim((1, None))
    ax.set_xlabel('Time')
    ax.set_ylabel('Discount factor')
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))

    ax.get_figure().savefig(args.dest_tseries_filename)
    ax.get_figure().clf()


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('tseries_filename')
    cli.add_argument('curve_filename')
    cli.add_argument('dest_tseries_filename')
    cli.add_argument('dest_curve_filename')
    args = cli.parse_args()

    tseries = pd.read_parquet(args.tseries_filename)
    plot_tseries(tseries, args.dest_tseries_filename)

    curve = pd.read_parquet(args.curve_filename)
    curve.reset_index().to_latex(args.dest_curve_filename, index=False,
                                 **settings.TABLE)
