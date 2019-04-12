from argparse import ArgumentParser

import pandas as pd

import settings


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    params = pd.read_parquet(args.src_filename).reset_index()
    params.to_latex(args.dest_filename, index=False, **settings.TABLE)
