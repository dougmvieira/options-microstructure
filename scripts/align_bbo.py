from argparse import ArgumentParser

import numpy as np
import pandas as pd

from align_settings import STARTTIME, ENDTIME, TIMESTEP
from utils import resample


def align_bbo(bbo):
    time_grid = np.arange(STARTTIME, ENDTIME + TIMESTEP, TIMESTEP)

    return bbo.groupby(['Class', 'Expiry', 'Strike']
                    ).apply(lambda o: resample(o.loc[o.name], time_grid))


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_bbo_filename')
    cli.add_argument('src_pairs_filename')
    cli.add_argument('src_corr_filename')
    cli.add_argument('dest_bbo_filename')
    cli.add_argument('dest_pairs_filename')
    cli.add_argument('dest_corr_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_bbo_filename)
    pairs = pd.read_parquet(args.src_pairs_filename)
    corr = pd.read_parquet(args.src_corr_filename)

    aligned_bbo = align_bbo(bbo)
    aligned_pairs = align_bbo(pairs)
    aligned_corr = align_bbo(corr)['Correction']
    aligned_corr = aligned_bbo.apply(lambda side: side - aligned_corr)

    aligned_bbo.to_parquet(args.dest_bbo_filename)
    aligned_pairs.to_parquet(args.dest_pairs_filename)
    aligned_corr.to_parquet(args.dest_corr_filename)
