from argparse import ArgumentParser

import pandas as pd

import settings


def options_selection(bbo):
    sel = bbo.index.to_frame(index=False)[['Class', 'Expiry', 'Strike']]
    sel['Class'] = sel['Class'].map(lambda k: {'C': 'Call', 'P': 'Put'}[k])
    sel.drop_duplicates(inplace=True)

    strikes = [pd.Series(g['Strike'].values, name=k)
               for k, g in sel.groupby(['Class', 'Expiry'])]
    strikes = pd.concat(strikes, axis=1)
    strikes.columns.names = ['Option type', 'Expiry']
    strikes.index = strikes.index.map(lambda _: '')

    return strikes


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_filename)
    strikes = options_selection(bbo)

    strikes.to_latex(args.dest_filename, na_rep='', **settings.TABLE)
