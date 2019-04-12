all: results/aex_index.png selection discount calibration regression


selection: results/sel_calls.tex results/sel_puts.tex

discount: results/discount_tseries.png results/discount_curve.png

calibration: results/heston_fit.png results/heston_params.tex results/heston_vols.png

regression: results/compare_deltas_call.png results/compare_deltas_put.png results/compare_vegas_call.png results/compare_vegas_put.png


DER_EU_ENXT_ALL_BBO_20160104.csv.zip:
	wget ftp://nextsamples:nextsamples@ftp.eua-data.euronext.com/NEXTHISTORY_SAMPLES/CURRENT/DER_EU_ENXT_ALL_BBO_20160104.csv.zip

cache/reference.parquet: scripts/parse_reference.py
	python3 scripts/parse_reference.py ftp://nextsamples:nextsamples@ftp.eua-data.euronext.com/NEXTHISTORY_SAMPLES/CURRENT/DER_EU_ENXT_ALL_REF_20160104.csv.zip cache/reference.parquet

cache/trade.parquet: scripts/parse_trade.py cache/reference.parquet
	python3 scripts/parse_trade.py ftp://nextsamples:nextsamples@ftp.eua-data.euronext.com/NEXTHISTORY_SAMPLES/CURRENT/DER_EU_ENXT_ALL_TRADE_20160104.csv.zip cache/reference.parquet cache/trade.parquet

cache/index.parquet: scripts/parse_index.py
	python3 scripts/parse_index.py ftp://nextsamples:nextsamples@ftp.eua-data.euronext.com/NEXTHISTORY_SAMPLES/CURRENT/EuronextIndices-Intraday-20160104.csv.zip cache/index.parquet

cache/bbo.parquet: scripts/parse_bbo.py cache/reference.parquet
	python3 scripts/parse_bbo.py DER_EU_ENXT_ALL_BBO_20160104.csv.zip cache/reference.parquet cache/bbo.parquet

cache/bbo_aex.parquet cache/bbo_pairs_aex.parquet: scripts/select_aex_bbo.py cache/bbo.parquet cache/trade.parquet
	python3 scripts/select_aex_bbo.py cache/bbo.parquet cache/trade.parquet cache/bbo_aex.parquet cache/bbo_pairs_aex.parquet

cache/bbo_corr.parquet: scripts/correction.py cache/bbo_aex.parquet
	python3 scripts/correction.py cache/bbo_aex.parquet cache/bbo_corr.parquet

cache/index_aex.parquet: scripts/select_aex_index.py cache/index.parquet
	python3 scripts/select_aex_index.py cache/index.parquet cache/index_aex.parquet

cache/aligned_bbo_unc.parquet cache/aligned_bbo_pairs.parquet cache/aligned_bbo.parquet: scripts/align_bbo.py scripts/align_settings.py cache/bbo_aex.parquet cache/bbo_pairs_aex.parquet cache/bbo_corr.parquet
	python3 scripts/align_bbo.py cache/bbo_aex.parquet cache/bbo_pairs_aex.parquet cache/bbo_corr.parquet cache/aligned_bbo_unc.parquet cache/aligned_bbo_pairs.parquet cache/aligned_bbo.parquet

cache/aligned_index.parquet: scripts/align_index.py scripts/align_settings.py cache/index_aex.parquet
	python3 scripts/align_index.py cache/index_aex.parquet cache/aligned_index.parquet

cache/discount_tseries.parquet cache/discount_curve.parquet: scripts/build_discount.py cache/aligned_bbo_pairs.parquet cache/aligned_index.parquet
	python3 scripts/build_discount.py cache/aligned_bbo_pairs.parquet cache/aligned_index.parquet cache/discount_tseries.parquet cache/discount_curve.parquet

cache/ivs.parquet: scripts/build_vol_surface.py cache/aligned_bbo_unc.parquet cache/discount_curve.parquet cache/aligned_index.parquet
	python3 scripts/build_vol_surface.py 2016-01-04 cache/aligned_bbo_unc.parquet cache/discount_curve.parquet cache/aligned_index.parquet cache/ivs.parquet

cache/heston_params.parquet: scripts/calibrate_heston.py cache/aligned_bbo.parquet cache/ivs.parquet cache/discount_curve.parquet cache/aligned_index.parquet
	python3 scripts/calibrate_heston.py 2016-01-04 cache/aligned_bbo.parquet cache/ivs.parquet cache/discount_curve.parquet cache/aligned_index.parquet cache/heston_params.parquet

cache/heston_vols.parquet: scripts/calibrate_vol.py cache/aligned_bbo.parquet cache/ivs.parquet cache/discount_curve.parquet cache/aligned_index.parquet cache/heston_params.parquet
	python3 scripts/calibrate_vol.py 2016-01-04 cache/aligned_bbo.parquet cache/ivs.parquet cache/discount_curve.parquet cache/aligned_index.parquet cache/heston_params.parquet cache/heston_vols.parquet

cache/reg_greeks.parquet: scripts/regression.py cache/aligned_bbo.parquet cache/aligned_index.parquet cache/heston_vols.parquet
	python3 scripts/regression.py cache/aligned_bbo.parquet cache/aligned_index.parquet cache/heston_vols.parquet cache/reg_greeks.parquet

cache/heston_greeks.parquet: scripts/heston_greeks.py cache/aligned_bbo.parquet cache/aligned_index.parquet cache/discount_curve.parquet cache/heston_params.parquet cache/heston_vols.parquet
	python3 scripts/heston_greeks.py 2016-01-04 cache/aligned_bbo.parquet cache/aligned_index.parquet cache/discount_curve.parquet cache/heston_params.parquet cache/heston_vols.parquet cache/heston_greeks.parquet


results/aex_index.png: scripts/plot_aex_index.py cache/index.parquet
	python3 scripts/plot_aex_index.py cache/index.parquet results/aex_index.png

results/sel_calls.tex results/sel_puts.tex: scripts/table_option_selection.py cache/aligned_bbo.parquet
	python3 scripts/table_option_selection.py cache/aligned_bbo.parquet results/sel_calls.tex results/sel_puts.tex

results/discount_tseries.png results/discount_curve.png: scripts/plot_discount.py cache/discount_tseries.parquet cache/discount_curve.parquet
	python3 scripts/plot_discount.py cache/discount_tseries.parquet cache/discount_curve.parquet results/discount_tseries.png results/discount_curve.png

results/heston_params.tex: scripts/table_heston_fit.py cache/heston_params.parquet
	python3 scripts/table_heston_fit.py cache/heston_params.parquet results/heston_params.tex

results/heston_fit.png: scripts/plot_heston_fit.py cache/aligned_index.parquet cache/ivs.parquet cache/heston_params.parquet
	python3 scripts/plot_heston_fit.py 2016-01-04 cache/aligned_index.parquet cache/ivs.parquet cache/heston_params.parquet results/heston_fit.png

results/heston_vols.png: scripts/plot_heston_vols.py cache/heston_vols.parquet
	python3 scripts/plot_heston_vols.py cache/heston_vols.parquet results/heston_vols.png

results/compare_deltas_call.png results/compare_deltas_put.png results/compare_vegas_call.png results/compare_vegas_put.png: scripts/plot_compare_greeks.py cache/reg_greeks.parquet cache/heston_greeks.parquet
	ipython3 scripts/plot_compare_greeks.py cache/reg_greeks.parquet cache/heston_greeks.parquet results/compare_deltas_call.png results/compare_deltas_put.png results/compare_vegas_call.png results/compare_vegas_put.png
