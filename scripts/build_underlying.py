from argparse import ArgumentParser

import numpy as np
import pandas as pd

from align_settings import STARTTIME, ENDTIME, TIMESTEP
from utils import resample


def build(pair):
    strike = pair.index.get_level_values('Strike').drop_duplicates()[0]
    pair = pair.unstack('Class')
    pair.index = pair.index.droplevel(['Expiry', 'Strike'])
    pair.sort_index(inplace=True)
    pair.ffill(inplace=True)

    underlying = pd.DataFrame(index=pair.index, columns=['Bid', 'Ask'])
    underlying['Ask'] = pair[('Ask', 'C')] - pair[('Bid', 'P')] + strike
    underlying['Bid'] = pair[('Bid', 'C')] - pair[('Ask', 'P')] + strike

    return underlying


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    underlying = build(pd.read_parquet(args.src_filename))
    underlying.to_parquet(args.dest_filename, coerce_timestamps='us')
