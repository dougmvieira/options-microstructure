from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot(intensities, params):
    fit = intensities['Arrival rate'].groupby(['Class', 'Strike']).apply(
        lambda k: pd.Series(
            params.loc[k.name, 'A']*np.exp(-params.loc[k.name, '$\\kappa$']
                                           *k.xs(k.name).index.values),
            k.xs(k.name).index))
    fit.name = 'Fit'
    intensities = pd.concat([intensities, fit], axis=1)

    fig, axes = plt.subplots(3, 2, figsize=(10, 8), sharex=True, sharey=True)
    for ((c, k), g), ax in zip(intensities.groupby(['Class', 'Strike']),
                               axes.T.ravel()):
        g.loc[(c, k), ['Arrival rate', 'Fit']].plot(logy=True, ax=ax,
                                                    ylim=(.0003, 10))
        g.loc[(c, k), ['2.5%', '97.5%']].plot(logy=True, ax=ax,
                                              ylim=(.0003, 10),
                                              linestyle='dashed')
        ax.set_title('{}, Strike {}, $A = {:.2f}$, $\\kappa = {:.2f}$'.format(
            'Call' if c == 'C' else 'Put', int(k), *params.xs((c, k))))
        ax.set_ylabel('events per minute')

    fig.tight_layout()
    return fig


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('intensities_filename')
    cli.add_argument('params_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    intensities = pd.read_parquet(args.intensities_filename)
    params = pd.read_parquet(args.params_filename)
    fig = plot(intensities, params)
    fig.savefig(args.dest_filename)
