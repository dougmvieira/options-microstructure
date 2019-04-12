from argparse import ArgumentParser

import pandas as pd

import settings


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    index = pd.read_parquet(args.src_filename).loc['AEX', 'Price']
    ax = index.plot(**settings.PLOT).set_ylabel('Price')
    ax.get_figure().savefig(args.dest_filename)
