from argparse import ArgumentParser

import numpy as np
import pandas as pd
from statsmodels.api import OLS

from align_settings import STARTTIME, ENDTIME


def regress(returns):
    return OLS(returns.iloc[1:], np.sign(returns.shift().iloc[1:])).fit()


def get_correction(bbo):
    returns = bbo.mean(axis=1
                ).groupby(['Class', 'Expiry', 'Strike'], group_keys=False
                ).apply(lambda o: o.diff().iloc[1:].dropna())

    ols = returns.groupby(['Class', 'Expiry', 'Strike'], group_keys=False
                ).apply(regress)

    rsquared = ols.map(lambda x: x.rsquared)
    beta = ols.map(lambda x: x.params[0])
    stats = pd.concat([rsquared, beta], axis=1, keys=['$R^2$', r'$\beta$'])

    correction = returns.groupby(['Class', 'Expiry', 'Strike'], group_keys=False
                       ).apply(lambda o: regress(o).fittedvalues)
    correction = pd.DataFrame(correction, columns=['Correction'])

    return correction, stats


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('dest_correction_filename')
    cli.add_argument('dest_stats_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_filename)

    times = bbo.index.get_level_values('Time')
    mask = (STARTTIME <= times) & (times <= ENDTIME)
    mask[:-3] |= mask[3:]

    correction, stats = get_correction(bbo[mask])
    correction.to_parquet(args.dest_correction_filename, coerce_timestamps='us')
    stats.to_parquet(args.dest_stats_filename)
