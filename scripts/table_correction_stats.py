from argparse import ArgumentParser

import numpy as np
import pandas as pd

import settings


def get_table(bbo, stats):
    tick_size = bbo['Ask'].groupby(['Class', 'Expiry', 'Strike']).apply(
        lambda p: np.min(np.diff(np.unique(p.dropna()))))
    tick_size.name = 'Tick size'

    spread = bbo['Ask'] - bbo['Bid']
    spread = spread.groupby(['Class', 'Expiry', 'Strike']).median()/tick_size
    spread.name = 'Median spread in ticks'

    beta = stats[r'$\beta$']/tick_size
    beta.name = r'$\beta$'

    table = [tick_size, spread, beta, stats['$R^2$']]
    return pd.concat(table, axis=1).reset_index()


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_bbo_filename')
    cli.add_argument('src_stats_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_bbo_filename)
    stats = pd.read_parquet(args.src_stats_filename)
    table = get_table(bbo, stats)

    table.to_latex(args.dest_filename, index=False, **settings.TABLE)
