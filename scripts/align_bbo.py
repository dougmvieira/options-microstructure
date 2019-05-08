from argparse import ArgumentParser

import numpy as np
import pandas as pd

from align_settings import STARTTIME, ENDTIME, TIMESTEP
from utils import resample


def align_bbo(bbo):
    time_grid = np.arange(STARTTIME, ENDTIME + TIMESTEP, TIMESTEP)

    return bbo.groupby(['Class', 'Expiry', 'Strike']
                    ).apply(lambda o: resample(o.loc[o.name], time_grid))


def align_underlying(underlying):
    time_grid = np.arange(STARTTIME, ENDTIME + TIMESTEP, TIMESTEP)
    return resample(underlying, time_grid)


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_bbo_filename')
    cli.add_argument('src_pairs_filename')
    cli.add_argument('src_underlying_filename')
    cli.add_argument('dest_bbo_filename')
    cli.add_argument('dest_pairs_filename')
    cli.add_argument('dest_underlying_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_bbo_filename)
    pairs = pd.read_parquet(args.src_pairs_filename)
    underlying = pd.read_parquet(args.src_underlying_filename)

    aligned_bbo = align_bbo(bbo)
    aligned_pairs = align_bbo(pairs)
    aligned_underlying = align_underlying(underlying)

    aligned_bbo.to_parquet(args.dest_bbo_filename)
    aligned_pairs.to_parquet(args.dest_pairs_filename)
    aligned_underlying.to_parquet(args.dest_underlying_filename)
