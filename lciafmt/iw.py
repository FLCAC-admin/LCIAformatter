# iw.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
This module contains functions needed to compile LCIA methods from ImpactWorld+
"""

import pandas as pd
import numpy as np
import re
import lciafmt
import lciafmt.cache as cache
import lciafmt.df as dfutil
from lciafmt.util import log, format_cas


def get(file=None, url=None, region=None) -> pd.DataFrame:
    """Generate a method for ImpactWorld+ in standard format.

    :param file: str, alternate filepath for method, defaults to file stored
        in cache
    :param url: str, alternate url for method, defaults to url in method config
    :param region: str, 3-digit code for Region; if not specified uses Global values
    :return: DataFrame of method in standard format
    """
    log.info("get method ImpactWorld+")

    method_meta = lciafmt.Method.ImpactWorld.get_metadata()
    f = file
    if f is None:
        f = _get_file(method_meta, url)
    df = _read(f, region)

    # Identify midpoint and endpoint records and differentiate in data frame.
    df = (df
          .assign(Method = lambda x: np.where(x['MP or Damage'] == "Midpoint",
                                              "ImpactWorld+ - Midpoint",
                                              "ImpactWorld+ - Endpoint"))
          .drop(columns=['MP or Damage', 'Scale'])
          )
    df = df.reindex(columns=dfutil.lciafmt_cols)
    df = df.fillna('')

    return df

def _get_file(method_meta, url=None):
    fname = method_meta['file']
    if url is None:
        url = method_meta['url']
    f = cache.get_or_download(fname, url)
    return f

def _read(file: str, region) -> pd.DataFrame:
    """Read the file into DataFrame."""
    log.info(f"read ImpactWorld+ from file {file}")

    df = pd.read_excel(file)
    df = (df
          .drop(df.columns[[0]], axis=1)
          .rename(columns={'Impact category': 'Indicator',
                           'CF unit': 'Indicator unit',
                           'CF value': 'Characterization Factor',
                           'Elem flow unit': 'Unit',
                           'CAS number': 'CAS No',
                           'Native geographical resolution scale': 'Scale',
                           })
          .assign(Context = lambda x: x['Compartment'].str.cat(x['Sub-compartment'], sep="/"))
          )
    generic_cols =  ["Global", "Not regionalized", "Global and continental",
                     "Global and continental + population density and indoor archetypes"]
    # extract location from flow name by looking for final comma.
    # Note there is no guaranteed way to parse locations here becuase the comma
    # is not unique to locations, and some locations have an internal comma e.g.,
    # "Canada, without Quebec"
    df = (df
          .assign(Location = lambda x: np.where(x['Scale'].isin(generic_cols),
              "",
              x['Elem flow name'].apply(lambda z: z.split(',')[-1].strip())))
          .assign(Flowable = lambda x: np.where(x['Scale'].isin(generic_cols),
              x['Elem flow name'],
              x['Elem flow name'].apply(lambda z: ','.join(z.split(',')[:-1]).strip())))
          # remove ", GLO" from the end of applicable elementary flow names. Global designation is retained in 'Scale' field
          .assign(Flowable = lambda x: x['Flowable'].apply(
              lambda z: z.replace(', GLO', '') if ', GLO' in z else z))
          )
    
    # list of location fragments not dealt with in preceding step. 
    locations = [', IAI Area',
                 ', IAI Area, Asia',
                 ', Europe',
                 ', Australia',
                 ', France',
                 ', IAI Area, North America',
                 ', Québec']

    # Create a regex pattern to match any of the location fragments at the end of the string
    pattern = '(' + '|'.join(map(re.escape, locations)) + ')$'
    df['matched_code'] = df['Flowable'].str.extract(pattern)
    df['matched_code'] = df['matched_code'].str.lstrip(',').str.strip()
    df['Flowable'] = df['Flowable'].str.replace(pattern, '', regex=True).str.rstrip()

    # Update Location column: if existing location is not empty, prepend matched_code
    mask = (df['matched_code'].notna()) | (df['matched_code'] != "")
    df.loc[mask, 'Location2'] = (
        df['matched_code'][mask] + ', ' + df.loc[mask, 'Location'].fillna('').str.strip()
    ).str.strip(', ')
    df['Location'] = df['Location2'].fillna(df['Location'])

    # Review locations and flows
    flows = pd.Series(df.query('Scale in @generic_cols')['Elem flow name'].unique())
    df2 = df.query('Flowable not in @flows')
    flow_context = df[['Flowable', 'Context']].drop_duplicates()

    df = (df
          .drop(columns=['Elem flow name', 'Compartment', 'Sub-compartment',
                         'matched_code', 'Location2'])
          )

    return df


if __name__ == "__main__":
    method = lciafmt.Method.ImpactWorld
    data = lciafmt.get_method(method)
    mapped_data = lciafmt.map_flows(data, system=method.get_metadata()['mapping'])
