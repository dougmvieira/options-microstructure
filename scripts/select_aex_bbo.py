from argparse import ArgumentParser

import pandas as pd

from utils import resample


NOPTS = 40
PAIRSSEL = [('C', '2016-02-19', 430), ('P', '2016-02-19', 430),
            ('C', '2016-03-18', 430), ('P', '2016-03-18', 430),
            ('C', '2016-06-17', 420), ('P', '2016-06-17', 420),
            ('C', '2016-06-17', 440), ('P', '2016-06-17', 440)]


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('trade_filename')
    cli.add_argument('dest_bbo_filename')
    cli.add_argument('dest_bbo_pairs_filename')
    args = cli.parse_args()

    trade = pd.read_parquet(args.trade_filename)['Volume'].loc['AEX']

    opt_sel = trade.xs(slice('2016-02-19', '2016-06-17'), level='Expiry',
                       drop_level=False
                  ).groupby(['Class', 'Expiry', 'Strike']
                  ).sum(
                  ).sort_values(
                  ).iloc[-NOPTS:
                  ].sort_index(
                  ).index

    bbo = pd.read_parquet(args.src_filename).loc['AEX'].loc[['C', 'P']]
    bbo.sort_index(inplace=True)

    bbo_pairs = pd.concat([bbo.xs(sel, drop_level=False) for sel in PAIRSSEL])
    bbo = pd.concat([bbo.xs(sel, drop_level=False) for sel in opt_sel])

    bbo.to_parquet(args.dest_bbo_filename, coerce_timestamps='us')
    bbo_pairs.to_parquet(args.dest_bbo_pairs_filename, coerce_timestamps='us')
