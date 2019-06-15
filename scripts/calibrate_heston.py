from argparse import ArgumentParser

import numpy as np
import pandas as pd
from fyne import heston

from utils import years_to_expiry


def calibrate(underlying, bbo, ivs, discount, date):
    time = pd.to_datetime(f"{date} 12:15:00")

    mid = bbo.xs(time, level='Time').mean(axis=1)
    mid.name = 'Mid'
    mid = mid.reset_index()

    weights = 1/(ivs['Ask'] - ivs['Bid']).xs(time, level='Time').values

    initial_guess = np.array([0.08, 7.2, 0.05, 1.25, -0.54])
    strikes = discount[mid['Expiry']].values*mid['Strike']
    expiries = years_to_expiry(date, mid['Expiry'])

    params = heston.calibration_crosssectional(
        underlying.loc[time], strikes, expiries, mid['Mid'].values,
        initial_guess, mid['Class'] == 'P', weights)

    index = pd.Index(['$V_t$', '$\kappa$', '$\theta$', '$\nu$', '$\rho$'],
                     name='Parameter')
    return pd.DataFrame(list(params), index, columns=['Value'])


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('bbo_filename')
    cli.add_argument('ivs_filename')
    cli.add_argument('discount_filename')
    cli.add_argument('underlying_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.bbo_filename)
    underlying = pd.read_parquet(args.underlying_filename).mean(axis=1)
    discount = pd.read_parquet(args.discount_filename)['Discount']
    date = pd.to_datetime(args.date)
    ivs = pd.read_parquet(args.ivs_filename)

    params = calibrate(underlying, bbo, ivs, discount, date)
    params.to_parquet(args.dest_filename)
