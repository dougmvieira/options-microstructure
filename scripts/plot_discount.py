from argparse import ArgumentParser

import pandas as pd

import settings
from utils import plot_shades, build_discount_curve


def plot_tseries(tseries, plot_filename):
    ax = plot_shades(tseries['Bid'].unstack(['Expiry', 'Strike']),
                     tseries['Ask'].unstack(['Expiry', 'Strike']),
                     **settings.PLOT)
    ax.set_ylim((1, None))
    ax.set_ylabel('Discount factor')
    ax.get_figure().savefig(args.dest_tseries_filename)
    ax.get_figure().clf()


def plot_curve(curve, plot_filename):
    ax = curve.plot(**settings.PLOT).set_ylabel('Discount factor')
    ax.get_figure().savefig(args.dest_curve_filename)


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
    plot_curve(curve, args.dest_curve_filename)
