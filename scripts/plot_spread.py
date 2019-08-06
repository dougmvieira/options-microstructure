from argparse import ArgumentParser

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def build_spread(bbo):
    spread = (bbo['Ask'] - bbo['Bid'])/bbo.mean(axis=1)
    spread = pd.concat([bbo['Log-moneyness'], spread], axis=1,
                       keys=['Log-moneyness', 'Spread'])
    spread.reset_index('Time', inplace=True)
    spread['Time'] = spread['Time'].groupby(['Class', 'Expiry', 'Strike']
                                  ).transform(lambda t: t.diff().shift(-1))
    spread.reset_index(['Class', 'Strike'], drop=True, inplace=True)
    spread.dropna(inplace=True)
    spread = spread.groupby(['Expiry', 'Log-moneyness', 'Spread']).sum()
    spread.reset_index(['Log-moneyness', 'Spread'], inplace=True)
    return spread


def plot(spread):
    fig, axs = plt.subplots(3, sharex=True, figsize=(8, 10))
    for ax, expiry in zip(axs, np.unique(spread.index)[:3]):
        rel_time = spread.loc[expiry, 'Time']/spread.loc[expiry, 'Time'].max()
        spread.loc[expiry].plot.scatter(x='Log-moneyness', y='Spread',
                                        s=rel_time/4, alpha=0.1, ax=ax,
                                        xlim=(-0.4, 0.2), ylim=(0, .6))
        ax.set_title("Expiry: {}".format(
            pd.to_datetime(expiry).strftime('%Y-%m-%d')))
    return fig


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_filename)
    spread = build_spread(bbo)
    fig = plot(spread)
    fig.savefig(args.dest_filename)
