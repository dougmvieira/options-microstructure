from argparse import ArgumentParser

import pandas as pd

import settings


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    vols = pd.read_parquet(args.src_filename)['Volatility']
    ax = vols.plot(**settings.PLOT).set_ylabel('Volatility')
    ax.get_figure().savefig(args.dest_filename)
