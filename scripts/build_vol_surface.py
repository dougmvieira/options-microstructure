from argparse import ArgumentParser

import pandas as pd
from fyne import blackscholes


def _years_to_expiry(date, expiry):
    return (expiry - date)/pd.to_timedelta('365d')


def build(bbo, underlying, discount, date):
    return bbo.transform(
        lambda side: side.groupby(['Class', 'Expiry', 'Strike']).transform(
            lambda o: blackscholes.implied_vol(
                underlying['Price'], discount[o.name[1]]*o.name[2],
                _years_to_expiry(date, o.name[1]), o, o.name[0]=='P')))


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('bbo_filename')
    cli.add_argument('discount_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename)
    discount = pd.read_parquet(args.discount_filename)['Discount']
    date = pd.to_datetime(args.date)

    ivs = build(bbo, underlying, discount, date)
    ivs.to_parquet(args.dest_filename)
