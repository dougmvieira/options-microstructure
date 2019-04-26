from argparse import ArgumentParser

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import acf, pacf

import settings


def select_option(bbo):
    rets = bbo.diff().groupby(['Class', 'Expiry', 'Strike']
                    ).apply(lambda x: x[x.abs() < 3*x.std()]).mean(axis=1)

    autocorr = rets.groupby(['Class', 'Expiry', 'Strike']
                  ).agg(lambda x: acf(x.dropna(), 1)[1])
    sel = autocorr.sort_values().index[0]

    print(sel)
    return rets.xs(sel).dropna()


def plot_acf_pacf(rets):
    rets_acf_pacf = np.stack([acf(rets), pacf(rets)], axis=-1)
    rets_acf_pacf = pd.DataFrame(rets_acf_pacf, columns=['ACF', 'PACF'])
    rets_acf_pacf.index.name = 'Lag'

    ax = rets_acf_pacf.iloc[1:9].plot(marker='s', **settings.PLOT)
    ax.set_ylabel('Correlation')

    return ax.get_figure()


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_options_filename')
    cli.add_argument('src_underlying_filename')
    cli.add_argument('dest_option_acf_pacf_filename')
    cli.add_argument('dest_underlying_acf_pacf_filename')
    cli.add_argument('dest_option_rets_filename')
    args = cli.parse_args()

    bbo = pd.read_parquet(args.src_options_filename)
    underlying = pd.read_parquet(args.src_underlying_filename)

    option_rets = select_option(bbo)
    underlying_rets = underlying.mean(axis=1).diff().dropna()

    fig = plot_acf_pacf(option_rets)
    fig.savefig(args.dest_option_acf_pacf_filename)
    fig.clf()

    fig = plot_acf_pacf(underlying_rets)
    fig.savefig(args.dest_underlying_acf_pacf_filename)
    fig.clf()

    ax = option_rets.plot(**settings.PLOT).set_ylabel('Mid price change')
    ax.get_figure().savefig(args.dest_option_rets_filename)
