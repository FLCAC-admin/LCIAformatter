"""Build IPCC GWP method with stock and gross biogenic indicator variants.

Drops AR4. Stock indicators keep AR5/AR6 names (FEDEFL IPCC mapping, 0/0).
Gross biogenic variants append ' Gross Biogenic' (+1/-1), applied in memory
from that same mapping. Writes parquet plus JSON-LD with and without flows.
"""
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


def main():
    data = lciafmt.get_method(method)
    data = data[~data['Indicator'].str.startswith('AR4')].reset_index(drop=True)

    mapped = lciafmt.map_with_gross_biogenic(data, 'IPCC')
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
