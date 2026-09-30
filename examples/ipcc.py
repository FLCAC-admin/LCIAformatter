"""Build IPCC GWP method with stock and net biogenic indicator variants.

Drops AR4. Stock indicators keep AR5/AR6 names (FEDEFL IPCC mapping, 0/0).
Net biogenic variants append ' Net Biogenic' (FEDEFL IPCC_net mapping, +1/-1).
Writes parquet plus JSON-LD with and without FEDEFL flows.
"""
import pandas as pd

import lciafmt
from lciafmt.util import (
    store_method,
    collapse_indicators,
    set_lcia_method_meta,
    OUTPUTPATH,
    mkdir_if_missing,
    pkg_version_number,
)


method = lciafmt.Method.IPCC
NET_SUFFIX = ' Net Biogenic'


def main():
    data = lciafmt.get_method(method)
    data = data[~data['Indicator'].str.startswith('AR4')].reset_index(drop=True)

    stock = lciafmt.map_flows(data, system='IPCC')
    net = lciafmt.map_flows(data, system='IPCC_net')
    net = net.copy()
    net['Indicator'] = net['Indicator'] + NET_SUFFIX

    mapped = pd.concat([stock, net], ignore_index=True)
    mapped = collapse_indicators(mapped)
    print('indicators:', sorted(mapped['Indicator'].unique()))
    print('rows', len(mapped))

    store_method(mapped, method)

    meta = set_lcia_method_meta(method)
    path = OUTPUTPATH / meta.category
    mkdir_if_missing(path)
    for suffix, write_flows in (('_noflows', False), ('_flows', True)):
        json_pack = path / f'IPCC_json_v{pkg_version_number}{suffix}.zip'
        json_pack.unlink(missing_ok=True)
        print('writing', json_pack.name, 'write_flows=', write_flows)
        lciafmt.to_jsonld(mapped, json_pack, write_flows=write_flows)


if __name__ == "__main__":
    main()
