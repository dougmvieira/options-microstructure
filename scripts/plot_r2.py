from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import settings


def plot(r2):
    strikes = np.unique(r2.index.get_level_values('Strike'))

    fig, axs = plt.subplots(3, 1, sharex=True, sharey=True, **settings.PLOT)
    for ax, (e, s) in zip(axs, r2.groupby('Expiry')):
        s.loc[e].reindex(strikes).plot.bar(ax=ax)

    fig.tight_layout()

    return fig

if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_call_filename')
    cli.add_argument('dest_put_filename')
    args = cli.parse_args()

    r2 = pd.read_parquet(args.src_filename)

    plot(r2.loc['C']).savefig(args.dest_call_filename)
    plot(r2.loc['P']).savefig(args.dest_put_filename)
