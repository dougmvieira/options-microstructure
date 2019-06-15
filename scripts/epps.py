from argparse import ArgumentParser

import numpy as np
import pandas as pd

import settings
from align_settings import STARTTIME, ENDTIME
from utils import resample


def get_signature(mids, time_steps):
    time_grids = (np.arange(STARTTIME, ENDTIME + dt, dt) for dt in time_steps)
    return_grids = (resample(mids, grid).diff().iloc[1:]
                    for grid in time_grids)
    correlations = [returns.corr().iloc[0, 1] for returns in return_grids]
    signature = pd.Series(correlations, time_steps)

    return signature


def plot_epps(bbo, underlying, correction):
    time_steps = pd.to_timedelta('1s')*np.arange(1, 61)
    time_steps = pd.Index(time_steps, name='Seconds')

    option_mids = bbo.loc[correction.index].mean(axis=1) - correction
    option_mids_unc = bbo.mean(axis=1)
    underlying_mids = underlying.mean(axis=1)

    mids = pd.concat([option_mids, underlying_mids],
                     keys=['Option', 'Underlying'], axis=1)
    mids_unc = pd.concat([option_mids_unc, underlying_mids],
                         keys=['Option', 'Underlying'], axis=1)

    signature = get_signature(mids, time_steps)
    signature_unc = get_signature(mids_unc, time_steps)
    signatures = pd.concat([signature_unc, signature], axis=1,
                           keys=['Original', 'Corrected'])

    ax = signatures.plot(**settings.PLOT).set_ylabel('Correlation')
    return ax.get_figure()


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('option_selection')
    cli.add_argument('src_bbo_filename')
    cli.add_argument('src_underlying_filename')
    cli.add_argument('src_correction_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    sel = eval(args.option_selection)
    bbo = pd.read_parquet(args.src_bbo_filename)
    underlying = pd.read_parquet(args.src_underlying_filename)
    correction = pd.read_parquet(args.src_correction_filename)['Correction']

    bbo = bbo.loc[sel]
    correction = correction.loc[sel]

    fig = plot_epps(bbo, underlying, correction)
    fig.savefig(args.dest_filename)
