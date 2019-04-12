from argparse import ArgumentParser

import pandas as pd
from statsmodels.api import OLS


def regress(bbo, underlying, vols):
    mid = bbo.mean(axis=1)
    mid = mid.unstack(['Class', 'Expiry', 'Strike'])
    mid_rets = mid.diff().iloc[1:]
    mid_rets.name = 'Mid'

    regressors = pd.concat([underlying['Price'], vols], axis=1).diff().iloc[1:]
    ols = mid_rets.agg(lambda o: OLS(o, regressors).fit())
    delta = ols.map(lambda x: x.params['Price'])
    vega = ols.map(lambda x: x.params['Volatility'])

    return pd.concat([delta, vega], keys=['Delta', 'Vega'], axis=1)

if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('bbo_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('vols_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename)
    vols = pd.read_parquet(args.vols_filename)['Volatility']

    coefs = regress(bbo, underlying, vols)
    coefs.to_parquet(args.dest_filename)
