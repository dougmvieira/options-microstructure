from argparse import ArgumentParser

import numpy as np
import pandas as pd
from fyne import blackscholes, heston


def _years_to_expiry(date, expiry):
    return (expiry - date)/pd.to_timedelta('365d')


def calibrate(underlying, bbo, ivs, discount, date, params):

    mid = bbo.mean(axis=1)
    mid.name = 'Mid'
    mid = mid.unstack(['Class', 'Expiry', 'Strike'])

    vol, kappa, theta, nu, rho = params
    properties = mid.columns.to_frame(index=False)
    strikes = discount[properties['Expiry']].values*properties['Strike']
    expiries = _years_to_expiry(date, properties['Expiry'])
    put = properties['Class'] == 'P'

    vols = mid.agg(
        lambda o: heston.calibration_vol(underlying.loc[o.name, 'Price'],
                                         strikes, expiries, o.values, kappa,
                                         theta, nu, rho, put, vol),
        axis=1)

    return pd.DataFrame(vols, columns=['Volatility'])


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('bbo_filename')
    cli.add_argument('ivs_filename')
    cli.add_argument('discount_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('params_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename)
    discount = pd.read_parquet(args.discount_filename)['Discount']
    date = pd.to_datetime(args.date)
    ivs = pd.read_parquet(args.ivs_filename)
    params = pd.read_parquet(args.params_filename)['Value']

    ivs['Ask'] = 1
    ivs['Bid'] = 0

    vols = calibrate(underlying, bbo, ivs, discount, date, params)
    vols.to_parquet(args.dest_filename)
