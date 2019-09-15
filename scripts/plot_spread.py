from argparse import ArgumentParser

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.patches import Patch
from scipy.stats import gaussian_kde

from align_settings import STARTTIME, ENDTIME


def build_spread(bbo):
    time = bbo.index.get_level_values('Time')
    bbo = bbo[(STARTTIME <= time) & (time <= ENDTIME)]
    spread = (bbo['Ask'] - bbo['Bid'])/bbo.mean(axis=1)
    spread = pd.concat([bbo['Log-moneyness'], spread], axis=1,
                       keys=['Log-moneyness', 'Spread'])
    spread.reset_index('Time', inplace=True)
    spread['Time'] = spread['Time'].groupby(['Class', 'Expiry', 'Strike']
                                  ).transform(lambda t: t.diff().shift(-1))
    spread['Time'] /= pd.to_timedelta('1s')
    spread.reset_index('Strike', drop=True, inplace=True)
    spread.dropna(inplace=True)
    spread = spread.groupby(['Class', 'Expiry', 'Log-moneyness', 'Spread']).sum()
    spread.reset_index(['Log-moneyness', 'Spread'], inplace=True)
    return spread


def plot(spread):
    spread = spread[spread['Spread'] > 0]
    bandwidth = 0.025
    kernel = (
        spread.groupby(['Class', 'Expiry']
             ).apply(lambda e: gaussian_kde(e[['Log-moneyness', 'Spread']].T,
                                            bandwidth, e['Time'])))

    xlen, ylen = 200, 150
    xmin, xmax, ymin, ymax = -0.4, 0.2, 0.0, 0.3
    x = np.linspace(xmin, xmax, xlen)
    y = np.linspace(ymin, ymax, ylen)
    x_b, y_b = np.broadcast_arrays(x[:, None], y[None, :])

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 10))
    patches = [Patch(color='tab:blue', label='Call'),
               Patch(color='tab:red', label='Put')]
    axes[0].legend(handles=patches)
    for ax, (e, k) in zip(axes, kernel.groupby('Expiry')):
        ax.set_title("Expiry: {}".format(
            pd.to_datetime(e).strftime('%Y-%m-%d')))
        for cp, cm in [('C', plt.cm.Blues), ('P', plt.cm.Reds)]:
            z = k.xs((cp, e))(np.array([x_b.ravel(), y_b.ravel()]))
            z = np.rot90(np.reshape(z, x_b.shape))
            ax.imshow(z, extent=[xmin, xmax, ymin, ymax], cmap=cm,
                      aspect='auto', alpha=.5)

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
