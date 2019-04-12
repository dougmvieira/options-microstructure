from argparse import ArgumentParser

import pandas as pd

import settings


def options_selection(filename):
    bbo = pd.read_parquet(filename)
    sel = bbo.index.to_frame(index=False)[['Class', 'Expiry', 'Strike']]

    sel.drop_duplicates(inplace=True)
    sel.set_index('Class', inplace=True)

    return sel.loc['C'], sel.loc['P']


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_calls_filename')
    cli.add_argument('dest_puts_filename')
    args = cli.parse_args()

    calls, puts = options_selection(args.src_filename)

    calls.to_latex(args.dest_calls_filename, index=False, **settings.TABLE)
    puts.to_latex(args.dest_puts_filename, index=False, **settings.TABLE)
