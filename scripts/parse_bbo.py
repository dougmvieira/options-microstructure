from argparse import ArgumentParser

import pandas as pd

from utils import is_consecutive_unique


_CHUNKSIZE = 100000


def _date_parser(s):
    return pd.to_datetime(s, format='%Y%m%d%H%M%S%f')


def _augment(bbo, reference):
    bbo.index = pd.MultiIndex.from_arrays(
        reference.loc[bbo['InstrumentId']].T.values, names=reference.columns)

    bbo.set_index('Time', append=True, inplace=True)
    del bbo['InstrumentId']

    return bbo


def _log_chunk(chunk, n_chunk):
    print(f'Line {_CHUNKSIZE*n_chunk}', end='\r', flush=True)
    return chunk


def parse(filename, reference):
    all_names = ['RecordType', 'MarketPlace', 'AssetClass', 'AssetGroup',
                 'InstrumentId', 'BDMInstrumentCode', 'TradingEventNumber',
                 'BBOTimestamp', 'BBOType', 'BestBid', 'BestBidQty',
                 'BestOffer', 'BestOfferQty']
    usecols_names = ['InstrumentId', 'BBOTimestamp', 'BBOType', 'BestBid',
                     'BestOffer']
    usecols = [all_names.index(col) for col in usecols_names]
    mapper = {'BBOTimestamp': 'Time',
              'BestBid': 'Bid',
              'BestOffer': 'Ask'}
    names = [mapper.get(name, name) for name in usecols_names]

    bbo_chunks = pd.read_csv(filename, sep=';', names=names, usecols=usecols,
                             date_parser=_date_parser, parse_dates=[1],
                             index_col=2, skiprows=2, chunksize=_CHUNKSIZE)
    bbo_chunks = (_log_chunk(bbo, n + 1) for n, bbo in enumerate(bbo_chunks))
    bbo_chunks = (bbo.loc[bbo.index.values == 'B'] for bbo in bbo_chunks)
    bbo_chunks = (bbo[is_consecutive_unique(bbo[['Bid', 'Ask']])]
                  for bbo in bbo_chunks)
    bbo_chunks = (_augment(bbo, reference) for bbo in bbo_chunks)

    return pd.concat(list(bbo_chunks))


if __name__ == '__main__':
    cli = ArgumentParser()
    cli.add_argument('src_filename')
    cli.add_argument('ref_filename')
    cli.add_argument('dest_filename')
    args = cli.parse_args()

    reference = pd.read_parquet(args.ref_filename)
    parse(args.src_filename, reference).to_parquet(args.dest_filename,
                                                   coerce_timestamps='us')
