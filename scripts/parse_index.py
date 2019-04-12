from argparse import ArgumentParser

import pandas as pd


def parse(filename):
    all_names = ["EffectiveDate", "InternalCode", "ISINCode", "Symbol",
                 "InstrumentName", "MIC", "CurrencyCode", "Price", "PriceTime",
                 "PriceType"]
    names = ['EffectiveDate', 'Symbol', 'Price', 'PriceTime', "PriceType"]
    usecols = [all_names.index(col) for col in names]
    parse_dates = {'Time': [names.index(name)
                            for name in ["EffectiveDate", "PriceTime"]]}

    index = pd.read_csv(filename, sep=';', names=names, usecols=usecols,
                        parse_dates=parse_dates, index_col='PriceType')

    index = index.loc['2']
    index['Time'] -= pd.to_timedelta('1h')
    index.set_index(["Symbol", "Time"], inplace=True)
    index.sort_index(inplace=True)

    return index

if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    parse(args.src_filename).to_parquet(args.dest_filename,
                                        coerce_timestamps='us')
