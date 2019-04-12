from argparse import ArgumentParser

import pandas as pd


def _date_parser(d, t):
    return pd.to_datetime(''.join([d, t]), format='%Y%m%d%H%M%S%f')


def _augment(trade, reference):
    trade.index = pd.MultiIndex.from_arrays(
        reference.loc[trade['InstrumentId']].T.values, names=reference.columns)

    trade.set_index('Time', append=True, inplace=True)
    del trade['InstrumentId']

    return trade


def parse(src_filename, reference):
    all_names = ['RecordType', 'MarketPlace', 'AssetClass', 'AssetGroup',
                 'InstrumentId', 'CodeInstBDM', 'TradingEventNumber',
                 'MatchedTradeId', 'TradeForClearingId', 'CrossTradeType',
                 'WholesaleTradeType', 'TradePrice', 'TradeVolume',
                 'TradeValueEuro', 'TradeDate', 'TradeTime', 'SessionId',
                 'TradingDay', 'TradeCancellationFlag',
                 'TradeCancellationTime']
    usecols_names = ['InstrumentId', 'TradePrice', 'TradeVolume', 'TradeDate',
                     'TradeTime']
    usecols = [all_names.index(col) for col in usecols_names]

    mapper = {'TradePrice': 'Price',
              'TradeVolume': 'Volume'}
    names = [mapper.get(name, name) for name in usecols_names]
    parse_dates = {'Time': [names.index(name)
                            for name in ['TradeDate', 'TradeTime']]}

    trade = pd.read_csv(src_filename, sep=';', skiprows=2, skipfooter=1,
                        parse_dates=parse_dates, engine='python',
                        date_parser=_date_parser, names=names, usecols=usecols)

    trade = _augment(trade, reference)
    trade.sort_index(inplace=True)

    return trade


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('ref_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    reference = pd.read_parquet(args.ref_filename)
    parse(args.src_filename, reference).to_parquet(args.dest_filename,
                                                   coerce_timestamps='us')
