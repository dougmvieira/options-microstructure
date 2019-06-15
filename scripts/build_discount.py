from argparse import ArgumentParser

import pandas as pd

from utils import build_discount_curve


def build(filename, underlying):
    pairs = pd.read_parquet(filename)

    tseries = pairs.groupby(['Expiry', 'Strike']).apply(
        lambda o: build_discount_curve(o.loc[('C', *o.name), 'Ask'],
                                       o.loc[('C', *o.name), 'Bid'],
                                       o.loc[('P', *o.name), 'Ask'],
                                       o.loc[('P', *o.name), 'Bid'],
                                       underlying['Ask'], underlying['Bid'],
                                       o.name[1]))

    curve = pd.DataFrame(tseries.mean(axis=1).groupby('Expiry').mean(),
                         columns=['Discount'])

    return tseries, curve


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('pairs_filename')
    cli.add_argument('und_filename')
    cli.add_argument('dest_tseries_filename')
    cli.add_argument('dest_curve_filename')
    args = cli.parse_args()

    underlying = pd.read_parquet(args.und_filename)
    tseries, curve = build(args.pairs_filename, underlying)

    tseries.to_parquet(args.dest_tseries_filename)
    curve.to_parquet(args.dest_curve_filename)
