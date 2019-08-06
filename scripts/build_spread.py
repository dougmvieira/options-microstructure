from argparse import ArgumentParser

import pandas as pd
import numpy as np
from py_vollib.black_scholes.implied_volatility import implied_volatility

from utils import resample, years_to_expiry


def implied_volatility_robust(underlying_price, strike, expiry, option_price, put_bool):
    underlying_price, strike, expiry, option_price, put_bool = (
        np.broadcast_arrays(underlying_price, strike, expiry, option_price,
                            put_bool))
    mask = ~np.any([np.isnan(obj) for obj in (underlying_price, strike, expiry, option_price, put_bool)], axis=0)
    option_price[mask] = np.where(put_bool[mask], option_price[mask] + underlying_price[mask] - strike[mask], option_price[mask])
    mask[mask] = option_price[mask] > np.maximum(underlying_price[mask] - strike[mask], 0.)
    mask[mask] = option_price[mask] < underlying_price[mask]

    ivs = np.full(option_price.shape, np.nan)
    if np.sum(mask):
        ivs[mask] = np.vectorize(implied_volatility)(
            option_price[mask], underlying_price[mask], strike[mask],
            expiry[mask], 0., 'c')
    return ivs


def ivs_transform(o):
    underlying_aligned = resample(underlying, o.xs(o.name).index).mean(axis=1)
    strike = o.name[2]*discount[o.name[1]]
    expiry = years_to_expiry(date, o.name[1])
    return implied_volatility_robust(underlying_aligned, strike, expiry, o,
                                     o.name[0]=='P')


def build_ivs(bbo, discount):
    discount.loc[pd.to_datetime('2016-01-15')] = 1
    return bbo.transform(lambda side: side.groupby(['Class', 'Expiry', 'Strike']
                                         ).transform(ivs_transform))


def moneyness_transform(o):
    return o.name[2]/resample(underlying, o.xs(o.name).index).mean(axis=1)


def build_logmoneyness(bbo):
    return np.log(bbo['Bid'].groupby(['Class', 'Expiry', 'Strike']
                           ).transform(moneyness_transform)
            ).to_frame('Log-moneyness')


def filter_bbo(bbo, discount):
    expiries = bbo.index.get_level_values('Expiry')
    return bbo[expiries <= np.max(discount.index.values)]


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('discount_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('bbo_filename')
    cli.add_argument('dest_prices_filename')
    cli.add_argument('dest_ivs_filename')
    args = cli.parse_args()

    date = pd.to_datetime(args.date)
    discount = pd.read_parquet(args.discount_filename)['Discount']
    underlying = pd.read_parquet(args.underlying_filename)
    bbo = pd.read_parquet(args.bbo_filename).loc['AEX'].loc[['C', 'P']]

    bbo = filter_bbo(bbo, discount)
    logmoneyness = build_logmoneyness(bbo)
    ivs = build_ivs(bbo, discount)

    pd.concat([bbo, logmoneyness], axis=1).to_parquet(
        args.dest_prices_filename, coerce_timestamps='us')
    pd.concat([ivs, logmoneyness], axis=1).to_parquet(
        args.dest_ivs_filename, coerce_timestamps='us')
