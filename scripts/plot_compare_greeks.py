from argparse import ArgumentParser

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import settings


def plot_greek(heston, reg):
    greek = pd.concat([heston.groupby(['Expiry', 'Strike']).mean(), reg],
                      axis=1, keys=['Model', 'Regression'])

    edges = greek['Model'].min(), greek['Model'].max()
    id_line = pd.Series(edges, edges)

    _, ax = plt.subplots(**settings.PLOT)
    colours = cm.get_cmap('tab10' if len(greek.groupby('Expiry')) <= 10 else 'tab20').colors
    for (label, group), colour in zip(greek.groupby('Expiry'), colours):
        group.plot.scatter(x='Model', y='Regression', ax=ax, label=label, color=colour)
    plt.legend(title='Expiry')
    id_line.plot(ax=ax)

    return ax.get_figure()


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('reg_greeks_filename')
    cli.add_argument('heston_greeks_filename')
    cli.add_argument('dest_deltas_call_filename')
    cli.add_argument('dest_deltas_put_filename')
    cli.add_argument('dest_vegas_call_filename')
    cli.add_argument('dest_vegas_put_filename')
    args = cli.parse_args()

    reg = pd.read_parquet(args.reg_greeks_filename)
    heston = pd.read_parquet(args.heston_greeks_filename)

    fig = plot_greek(heston.loc['C', 'Delta'], reg.loc['C', 'Delta'])
    fig.savefig(args.dest_deltas_call_filename)
    fig.clf()

    fig = plot_greek(heston.loc['P', 'Delta'], reg.loc['P', 'Delta'])
    fig.savefig(args.dest_deltas_put_filename)
    fig.clf()

    fig = plot_greek(heston.loc['C', 'Vega'], reg.loc['C', 'Vega'])
    fig.savefig(args.dest_vegas_call_filename)
    fig.clf()

    fig = plot_greek(heston.loc['P', 'Vega'], reg.loc['P', 'Vega'])
    fig.savefig(args.dest_vegas_put_filename)
