from argparse import ArgumentParser

import pandas as pd


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    aex_index = pd.read_parquet(args.src_filename).loc['AEX']
    aex_index.to_parquet(args.dest_filename, coerce_timestamps='us')
