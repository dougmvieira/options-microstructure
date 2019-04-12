from argparse import ArgumentParser

import pandas as pd
import numpy as np
from fyne import blackscholes, heston

import matplotlib.pyplot as plt


def _years_to_expiry(date, expiry):
    return (expiry - date)/pd.to_timedelta('365d')


def plot(underlying, ivs, params, date):
    time = pd.to_datetime(f"{date} 12:15:00")

    ivs.columns.name = 'Side'
    groups = ivs.xs(time, level='Time').stack().groupby('Expiry')
    fig, axs = plt.subplots(len(groups), sharex=True, figsize=(8, 10))

    strike_min = np.min(ivs.index.get_level_values('Strike').values)
    strike_max = np.max(ivs.index.get_level_values('Strike').values)
    strike_grid = np.linspace(strike_min, strike_max, 20)

    for ax, (e, g) in zip(axs, groups):
        g.index = g.index.droplevel(['Expiry', 'Side'])
        g.xs('C').plot(ax=ax, linewidth=0, marker='_', markersize=3)
        g.xs('P').plot(ax=ax, linewidth=0, marker='_', markersize=3, color='g')

        heston_prices = heston.formula(underlying.loc[time, 'Price'], strike_grid,
                                       _years_to_expiry(date, e), *params)

        heston_ivs = pd.Series(
            blackscholes.implied_vol(underlying.loc[time, 'Price'], strike_grid,
                                     _years_to_expiry(date, e), heston_prices),
            strike_grid)

        heston_ivs.plot(ax=ax, color='gray').set_ylabel('Implied volatility')
        ax.set_title(f"Expiry: {e}")

    return fig


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('date')
    cli.add_argument('underlying_filename')
    cli.add_argument('ivs_filename')
    cli.add_argument('params_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    underlying = pd.read_parquet(args.underlying_filename)
    ivs = pd.read_parquet(args.ivs_filename)
    date = pd.to_datetime(args.date)
    params = pd.read_parquet(args.params_filename)['Value']

    fig = plot(underlying, ivs, params, date)
    fig.savefig(args.dest_filename)
