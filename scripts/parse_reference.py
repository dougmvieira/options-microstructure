from argparse import ArgumentParser

import pandas as pd


def _date_parser(s):
    return pd.to_datetime(s, format='%Y%m%d')


def parse(filename):
    usecols = ['InstrumentID', 'OptionCategory', 'ExpiryDate',
               'ActualExercisePrice', 'InstrumentTradingSymbol']
    mapper = {'OptionCategory': 'Class',
              'ExpiryDate': 'Expiry',
              'ActualExercisePrice': 'Strike',
              'InstrumentTradingSymbol': 'Underlying'}

    reference = pd.read_csv(filename, sep=';', skipfooter=1, skiprows=1,
                            engine='python', usecols=usecols,
                            date_parser=_date_parser, parse_dates=[2],
                            index_col='InstrumentID')
    reference.rename(mapper, axis=1, inplace=True)

    return reference[['Underlying', 'Class', 'Expiry', 'Strike']]


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    parse(args.src_filename).to_parquet(args.dest_filename)
