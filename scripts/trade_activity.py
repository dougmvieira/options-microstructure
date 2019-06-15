from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from utils import resample


def get_volumes(trade, underlying):
    strikes = trade.index.get_level_values('Strike')
    timestamps = trade.index.get_level_values('Time')

    underlying_aligned = resample(underlying, timestamps).loc[timestamps]
    moneyness = strikes/underlying_aligned.mean(axis=1)
    trade['Log-moneyness'] = np.log(moneyness).values
    return trade.reset_index(['Strike', 'Time'], drop=True
               ).set_index('Log-moneyness', append=True
               )['Volume']


def plot_activity(volumes):
    fig, axes = plt.subplots(3, 1, sharex=True, sharey=True, figsize=(8, 10))

    expiries = np.unique(volumes.index.get_level_values('Expiry'))
    for ax, expiry in zip(axes, expiries):
        for option_type in ['Call', 'Put']:
            v = volumes.xs((option_type[0], expiry))
            sns.distplot(np.repeat(v.index.values, v), ax=ax,
                         label=option_type)
        ax.set_ylabel('Relative frequency')

        expiry = pd.to_datetime(expiry).strftime('%Y-%m-%d')
        ax.set_title("Expiry: {}".format(expiry))

    axes[0].legend()
    axes[-1].set_xlabel('Log-moneyness')

    return fig


def table_activity(volumes):
    total_volume = volumes.groupby('Expiry').sum()
    relative_volume = total_volume/total_volume.sum()
    table = pd.concat([total_volume, relative_volume],
                      keys=['Total volume', 'Relative volume'], axis=1)

    return table


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('ticker')
    cli.add_argument('trade_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('dest_plot_filename')
    cli.add_argument('dest_table_filename')
    args = cli.parse_args()

    trade = pd.read_parquet(args.trade_filename).xs(args.ticker)
    underlying = pd.read_parquet(args.underlying_filename)

    volumes = get_volumes(trade, underlying)
    fig = plot_activity(volumes)
    fig.savefig(args.dest_plot_filename)

    table = table_activity(volumes)
    table.to_latex(args.dest_table_filename,
                   float_format=lambda x: '{:.1f}%'.format(100*x))
