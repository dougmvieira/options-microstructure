from argparse import ArgumentParser

import pandas as pd
from fyne import heston


def _years_to_expiry(date, expiry):
    return (expiry - date)/pd.to_timedelta('365d')


def get_heston_greeks(date, bbo, underlying, discount, vols, params):
    _, kappa, theta, nu, rho = params

    mid = bbo.mean(axis=1).unstack(['Class', 'Expiry', 'Strike'])
    mid.name = 'Mid'
    properties = mid.columns.to_frame(index=False)

    strikes = discount[properties['Expiry']].values*properties['Strike'].values
    expiries = _years_to_expiry(date, properties['Expiry'])
    put = (properties['Class']=='P')

    deltas = pd.DataFrame(heston.delta(underlying['Price'].values[:, None],
                                       strikes, expiries, vols.values[:, None],
                                       kappa, theta, nu, rho, put),
                          mid.index, mid.columns).unstack('Time')

    vegas = pd.DataFrame(heston.vega(underlying['Price'].values[:, None],
                                     strikes, expiries, vols.values[:, None],
                                     kappa, theta, nu, rho),
                         mid.index, mid.columns).unstack('Time')

    return pd.concat([deltas, vegas], keys=['Delta', 'Vega'], axis=1)


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('bbo_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('discount_filename')
    cli.add_argument('params_filename')
    cli.add_argument('vols_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    date = pd.to_datetime(args.date)
    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename)
    discount = pd.read_parquet(args.discount_filename)['Discount']
    params = pd.read_parquet(args.params_filename)['Value']
    vols = pd.read_parquet(args.vols_filename)['Volatility']

    greeks = get_heston_greeks(date, bbo, underlying, discount, vols, params)
    greeks.to_parquet(args.dest_filename)
