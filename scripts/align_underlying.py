from argparse import ArgumentParser

import numpy as np
import pandas as pd

from align_settings import STARTTIME, ENDTIME, TIMESTEP
from utils import resample


def align_index(filename):
    time_grid = np.arange(STARTTIME, ENDTIME + TIMESTEP, TIMESTEP)

    index = pd.read_parquet(filename)
    aligned_index = resample(index, time_grid)
    aligned_index = aligned_index[~aligned_index.index.duplicated()]

    return aligned_index


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    align_index(args.src_filename).to_parquet(args.dest_filename,
                                              coerce_timestamps='us')
