from argparse import ArgumentParser

import numpy as np
import pandas as pd

from utils import autorreg_correction


def get_correction(bbo):
    returns = bbo.mean(axis=1
                ).groupby(['Class', 'Expiry', 'Strike'], group_keys=False
                ).apply(lambda o: o.diff().iloc[1:].dropna())

    return pd.DataFrame(returns.groupby(['Class', 'Expiry', 'Strike'],
                                        group_keys=False
                              ).apply(autorreg_correction),
                        columns=['Correction'])


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()


    bbo = pd.read_parquet(args.src_filename)
    bbo_corr = get_correction(bbo)

    bbo_corr.to_parquet(args.dest_filename, coerce_timestamps='us')
