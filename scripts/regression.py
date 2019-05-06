from argparse import ArgumentParser

import pandas as pd
from statsmodels.api import OLS


def regress(bbo, underlying, vols):
    mid = bbo.mean(axis=1)
    mid = mid.unstack(['Class', 'Expiry', 'Strike'])
    mid_rets = mid.diff().iloc[1:]
    mid_rets.name = 'Mid'

    underlying.name = 'Price'
    regressors = pd.concat([underlying, vols], axis=1).diff().iloc[1:]

    ols = mid_rets.agg(lambda o: OLS(o, regressors).fit())
    delta = ols.map(lambda x: x.params['Price'])
    vega = ols.map(lambda x: x.params['Volatility'])

    r2 = ols.map(lambda x: x.rsquared)
    r2_und = mid_rets.agg(
        lambda o: OLS(o, regressors['Price']).fit().rsquared)
    r2_vol = mid_rets.agg(
        lambda o: OLS(o, regressors['Volatility']).fit().rsquared)
    r2_table = pd.concat([r2, r2 - r2_vol, r2 - r2_und], axis=1,
                         keys=[r'$R^2$', r'Price $sR^2$', r'Volatility $sR^2$'])

    return pd.concat([delta, vega], keys=['Delta', 'Vega'], axis=1), r2_table


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('bbo_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('vols_filename')
    cli.add_argument('dest_coefs_filename')
    cli.add_argument('dest_r2_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename).mean(axis=1)
    vols = pd.read_parquet(args.vols_filename)['Volatility']

    coefs, r2_table = regress(bbo, underlying, vols)
    coefs.to_parquet(args.dest_coefs_filename)
    r2_table.to_parquet(args.dest_r2_filename)
