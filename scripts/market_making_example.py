from argparse import ArgumentParser

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from fyne import heston
from scipy.integrate import solve_ivp
from statsmodels.api import OLS

import settings


_EPS = 1.e-12


def optimal_controls(time, inventory_bounds, price_risk_aversion,
                     exec_risk_aversion, base_intensities, intensity_decays,
                     covariance_matrix):
    t = time
    Q = inventory_bounds
    γ = price_risk_aversion
    ξ = exec_risk_aversion
    A = base_intensities
    k = intensity_decays
    Σ = covariance_matrix

    d = len(A)
    C = (1 + ξ/k)**-(1 + k/ξ) if ξ > _EPS else np.exp(-np.ones(d))
    η = A*C

    q = np.stack(np.meshgrid(*(np.arange(-Qi, Qi + 1) for Qi in Q),
                             indexing='ij'), axis=-1)
    ẏ0 = -γ*(q.dot(Σ)*q).sum(axis=-1)/2

    Ib = np.full((d, d), slice(None))
    Ia = Ib.copy()
    np.fill_diagonal(Ia, slice(1, None))
    np.fill_diagonal(Ib, slice(None, -1))
    Ia = list(map(tuple, Ia))
    Ib = list(map(tuple, Ib))

    sol = solve_ivp(multiasset_ode_rhs(ẏ0, Ib, Ia, η, k, Q), (0, t),
                    np.zeros(ẏ0.shape).ravel())
    θ = np.reshape(sol.y[:, -1], ẏ0.shape)

    δ_b = np.full(q.shape, np.nan)
    δ_a = np.full(q.shape, np.nan)
    for i in range(d):
        Hb = η[i]*np.exp(-k[i]*(θ[Ib[i]] - θ[Ia[i]]))/k[i]
        Ha = η[i]*np.exp(-k[i]*(θ[Ia[i]] - θ[Ib[i]]))/k[i]

        δ_b[(*Ib[i], i)] = -np.log((ξ*Hb + k[i]*Hb)/A[i])/k[i]
        δ_a[(*Ia[i], i)] = -np.log((ξ*Ha + k[i]*Ha)/A[i])/k[i]

    return δ_b, δ_a


def multiasset_ode_rhs(ẏ0, Ib, Ia, η, k, Q):
    def closure(t, y):
        y = np.reshape(y, ẏ0.shape)

        ẏ = ẏ0.copy()
        for i in range(len(Q)):
            Hb = η[i]*np.exp(-k[i]*(y[Ib[i]] - y[Ia[i]]))/k[i]
            Ha = η[i]*np.exp(-k[i]*(y[Ia[i]] - y[Ib[i]]))/k[i]
            ẏ[Ib[i]] += Hb
            ẏ[Ia[i]] += Ha

        return ẏ.ravel()

    return closure


def options_cov_matrix(underlying_price, strikes, expiry, vol, kappa, theta,
                       nu, rho, put):
    deltas = heston.delta(underlying_price, strikes, expiry, vol, kappa, theta,
                          nu, rho, put)
    vegas = heston.vega(underlying_price, strikes, expiry, vol, kappa, theta,
                        nu, rho)

    greeks = np.stack([deltas, vegas], axis=-1)
    rho_mat = np.array([[1, rho], [rho, 1]])
    vol_vec = np.array([np.sqrt(vol)*underlying_price, np.sqrt(vol)*nu])

    factors_cov_mat = rho_mat * vol_vec[:, None].dot(vol_vec[None, :])
    return greeks, greeks @ factors_cov_mat @ greeks.T


def adjust_decay(trade, decay, expiry):
    turnover = trade['Price']*trade['Volume']
    med_trade_size = turnover.xs(expiry, level='Expiry').median()
    return decay/med_trade_size


def model_inputs(date, expiry, bbo, underlying, trade, intensity_params,
                 heston_params):
    time = pd.to_datetime(f"{date} 12:15:00")
    bbo = bbo.xs(expiry, level='Expiry')
    mid = bbo.xs(time, level='Time').mean(axis=1)
    underlying_price = underlying.loc[time].mean()
    strikes = mid.index.get_level_values('Strike')
    put = mid.index.get_level_values('Class') == 'P'
    time_to_expiry = (expiry - time)/pd.to_timedelta('1y')
    greeks, cov_matrix = options_cov_matrix(
        underlying_price, strikes, time_to_expiry, *heston_params, put=put)
    greeks = pd.DataFrame(greeks, mid.index, ['Delta', 'Vega'])
    greeks.columns.name = 'Greek'
    cov_matrix = pd.DataFrame(cov_matrix, mid.index, mid.index)/(252*6)
    base_intensity = intensity_params['A']/3600

    return base_intensity, greeks, cov_matrix, mid


def market_relative_spread(bbo, expiry):
    bbo = bbo.xs(expiry, level='Expiry')
    return bbo.groupby(['Class', 'Strike']).apply(
        lambda o: ((o['Ask'] - o['Bid'])/o.mean(axis=1)).mean())


def compute_optimal_spreads(base_intensity, intensity_decay, cov_matrix, mid,
                            risk_aversion):
    variances = pd.Series(np.diag(cov_matrix), mid.index)

    intensity_decay += 0*mid
    params = dict(
        time=3, inventory_bounds=(1, 1, 1, 1, 1, 1),
        covariance_matrix=cov_matrix.loc[base_intensity.index,
                                         base_intensity.index],
        base_intensities=base_intensity.values,
        intensity_decays=intensity_decay.loc[base_intensity.index].values,
        exec_risk_aversion=0.0, price_risk_aversion=risk_aversion)

    bid_control, ask_control = optimal_controls(**params)
    optimal_quotes = pd.concat([mid.loc[base_intensity.index] - bid_control[1, 1, 1, 1, 1, 1],
                                mid.loc[base_intensity.index] + ask_control[1, 1, 1, 1, 1, 1]], axis=1,
                                keys=['Bid', 'Ask'])

    optimal_rel_spread_gueant = (optimal_quotes['Ask'] - optimal_quotes['Bid']
                                 )/mid.loc[base_intensity.index]

    optimal_rel_spread_risk_neutral = 2/(intensity_decay*mid)
    optimal_spread_small_time = 2/intensity_decay + risk_aversion*3*variances
    optimal_rel_spread_small_time = optimal_spread_small_time/mid


    return optimal_rel_spread_risk_neutral, optimal_rel_spread_small_time, optimal_rel_spread_gueant


def optimal_spreads_regression(cov_matrix, mid, market_rel_spread):
    regressors = 3*pd.DataFrame([np.diag(cov_matrix)], ['Variance'], mid.index).T
    regressors['Inverse decay'] = 1
    fit = OLS(market_rel_spread*mid, regressors).fit()
    risk_aversion = fit.params['Variance']
    intensity_decay = 2/fit.params['Inverse decay']
    return risk_aversion, intensity_decay, fit.rsquared


def plot_greeks(greeks):
    ax = greeks[['Delta']].unstack('Class').plot()
    ax2 = greeks[['Vega']].unstack('Class').plot(ax=ax, secondary_y=True)
    ax.set_ylabel('Delta')
    ax2.set_ylabel('Vega (€)')
    return ax.get_figure()


def plot_spreads(decay, risk_aversion, r2, market_rel_spread,
                 optimal_rel_spread_risk_neutral,
                 optimal_rel_spread_small_time, optimal_rel_spread_gueant,
                 rel=False):
    spreads = pd.concat(
        [market_rel_spread, optimal_rel_spread_risk_neutral,
         optimal_rel_spread_small_time, optimal_rel_spread_gueant],
        keys=['Market', 'Optimal risk neutral', 'Optimal small time',
              'Optimal Guéant'], names=['Name'])

    fig, ax = plt.subplots(**settings.PLOT)
    for (n, c), g in spreads.groupby(['Name', 'Class']):
        g.loc[(n, c)].plot(ax=ax, linestyle='-' if n == 'Market' else '--',
                           label=(n, c), marker='d')
    ax.legend()
    ax.set_title('$\kappa = {:.2f}$, $\gamma = {:.3f}$, $R^2 = {:.2f}$'.format(decay, risk_aversion, r2))

    if rel:
        ax.set_yticklabels(['{:.0%}'.format(x) for x in ax.get_yticks()])
        ax.set_ylabel('Relative spread')
    else:
        ax.set_ylabel('Spread (€)')

    return fig


def format_table(intensity_params):
    base = intensity_params[['A', 'A 5%', 'A 95%']]
    decay = intensity_params[['$\kappa$', '$\kappa$ 5%', '$\kappa$ 95%']]
    decay.columns = base.columns = ['Value', '5%', '95%']
    table = pd.concat([base, decay], keys=['A', '$\kappa$'])
    table = table.apply(lambda r: '{:.2f} ({:.2f}, {:.2f})'.format(*r), axis=1)
    return table.unstack(0)


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('ticker')
    cli.add_argument('date')
    cli.add_argument('expiry')
    cli.add_argument('underlying_filename')
    cli.add_argument('intensity_filename')
    cli.add_argument('heston_params_filename')
    cli.add_argument('bbo_filename')
    cli.add_argument('trade_filename')
    cli.add_argument('dest_params_filename')
    cli.add_argument('dest_decay_filename')
    cli.add_argument('dest_greeks_filename')
    cli.add_argument('dest_spread_abs_filename')
    cli.add_argument('dest_spread_rel_filename')
    args = cli.parse_args()

    date = pd.to_datetime(args.date)
    expiry = pd.to_datetime(args.expiry)
    underlying = pd.read_parquet(args.underlying_filename)
    intensity_params = pd.read_parquet(args.intensity_filename)
    heston_params = pd.read_parquet(args.heston_params_filename)['Value']
    bbo = pd.read_parquet(args.bbo_filename)
    trade = pd.read_parquet(args.trade_filename).xs(args.ticker)

    market_rel_spread = market_relative_spread(bbo, expiry)
    base_intensity, greeks, cov_matrix, mid = model_inputs(
        date, expiry, bbo, underlying, trade, intensity_params, heston_params)
    risk_aversion, intensity_decay, r2 = optimal_spreads_regression(
        cov_matrix, mid, market_rel_spread)
    optimal_spreads = compute_optimal_spreads(base_intensity, intensity_decay,
                                              cov_matrix, mid, risk_aversion)
    decay_table = adjust_decay(trade, intensity_params['$\kappa$'], expiry)

    params_table = format_table(intensity_params)
    params_table.to_latex(args.dest_params_filename, **settings.TABLE)
    decay_table.to_latex(args.dest_decay_filename, **settings.TABLE)

    fig = plot_greeks(greeks)
    fig.savefig(args.dest_greeks_filename)

    fig = plot_spreads(intensity_decay, risk_aversion, r2,
                       market_rel_spread*mid,
                       *(s*mid.loc[s.index] for s in optimal_spreads))
    fig.savefig(args.dest_spread_abs_filename)

    fig = plot_spreads(intensity_decay, risk_aversion, r2, market_rel_spread,
                       *optimal_spreads, rel=True)
    fig.savefig(args.dest_spread_rel_filename)
