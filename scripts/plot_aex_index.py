from argparse import ArgumentParser

import pandas as pd
from matplotlib.dates import DateFormatter

import settings


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    index = pd.read_parquet(args.src_filename)
    index = index.loc['2016-01-04 08:00:00':'2016-01-04 16:30:00']

    ax = index.plot(**settings.PLOT)
    ax.set_ylabel('Price')
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))

    ax.get_figure().savefig(args.dest_filename)
