# usetox.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
This module contains functions needed to compile LCIA methods from USETox
"""

import pandas as pd
import os
import zipfile

import lciafmt
import lciafmt.cache as cache
from lciafmt.df import lciafmt_cols
from lciafmt.util import log, aggregate_factors_for_primary_contexts


def get(method) -> pd.DataFrame:
    """Generate a method for USEtox in standard format.

    :param add_factors_for_missing_contexts: bool, if True generates average
        factors for unspecified contexts
    :param file: str, alternate filepath for method, defaults to file stored
        in cache
    :param url: str, alternate url for method, defaults to url in method config
    :return: DataFrame of method in standard format
    """
    log.info("getting method USEtox")
    method_meta = method.get_metadata()
    _get_file(method_meta)
    df = pd.DataFrame()
    for xls_file in method_meta.get('file'):
        df1 = _read(cache.get_path(xls_file), 'Human tox CF')
        df2 = _read(cache.get_path(xls_file), 'Ecotox CF')
        df = pd.concat([df, df1, df2], ignore_index=True)
    
    df = aggregate_factors_for_primary_contexts(df)
    df['Method'] = method_meta.get('name')

    return df

def _get_file(method_meta, url=None):
    if url is None:
        url = method_meta['url']
    fname = os.path.basename(url)
    file = cache.get_path(fname)
    path = cache.get_folder()
    if os.path.isfile(file):
        log.info(f"take {fname} from cache")
    else:
        raise FileNotFoundError(
            f"{fname} not found. Create a free account to download from "
            f"{url} and save to {path}")

    try:
        with zipfile.ZipFile(file, 'r') as zipf:
            files = zipf.namelist()
            for filename in method_meta['file']:
                if any(filename in string for string in files):
                    z = [string for string in files if string.endswith(filename)][0]
                    zipf.extract(z, path)
                    extracted_path = os.path.join(path, z)
                    new_path = os.path.join(path, os.path.basename(z))
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(extracted_path, new_path)
                    print(f"Extracted '{filename}' to '{path}'")
                else:
                    print(f"'{filename}' not found in the ZIP archive.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: ZIP file '{file}' not found.")


def _read(xls_file, sheet: str) -> pd.DataFrame:
    """Read the data from Excel with given path into a DataFrame."""
    if sheet == "Ecotox CF":
        usecols = "B:K, T:U" # Midpoint
        i_unit = 'CTUe' # Comparative toxic units
    elif sheet == "Human tox CF":
        usecols = "B:AD, BF:BI" # Midpoint
        i_unit = 'CTUh' # Comparative toxic units
    df = pd.read_excel(xls_file, sheet_name=sheet, skiprows=3, usecols=usecols)
    headers = pd.read_excel(xls_file, sheet_name=sheet, nrows=2, skiprows=1, usecols=usecols).values
    headers = pd.DataFrame(headers).ffill(axis=1)
    ## TODO: fix future warning
    headers = headers.drop(headers.columns[:2], axis=1)
    header = headers.apply(lambda x: f"{x[0]}: {x[1]}")
    df.columns = pd.concat([pd.Series(['CAS', 'Name']), header])
    flag_cols = list(header[header.str.contains('indicative')])
    df_melt = pd.melt(df, id_vars=(['CAS', 'Name'] + flag_cols), var_name='header')
    df_melt[['compartment', 'indicator']] = df_melt['header'].str.split(": ", expand=True)
    df_melt[flag_cols] = df_melt[flag_cols].fillna('')
    
    indicator_dict = {'cancer': 'Human health cancer',
                      'non-canc.': 'Human health noncancer',
                      'freshwater': 'Ecotoxicity'}
    flag_dict = {'cancer': '(F=indicative; n/a=not available): carcinogenic',
                 'non-canc.': '(F=indicative; n/a=not available): non-carcinogenic',
                 'freshwater': '(F=indicative; n/a=not available): Ecotox'}
    compartment_dict = {
        ## Human Health
        'Emission to household indoor air': 'air/indoor',
        'Emission to industrial indoor air': 'air/industrial',
        'Emission to urban air': 'air/urban',
        'Emission to cont. rural air': 'air/rural',
        'Emission to cont. freshwater': 'water/freshwater',
        'Emission to cont. sea water': 'water/sea water',
        'Emission to cont. natural soil': 'soil/natural',
        'Emission to cont. agric. soil': 'soil/agricultural',
        # 'Application to wheat': ''

        ## Ecotox
        'Em.hom.airI': 'air/indoor',
        'Em.ind.airI': 'air/industrial',
        'Em.airU': 'air/urban',
        'Em.airC': 'air/rural',
        'Em.fr.waterC': 'water/freshwater',
        'Em.sea waterC': 'water/sea water',
        'Em.nat.soilC': 'soil/natural',
        'Em.agr.soilC': 'soil/agricultural',
        }
    
    df_melt = (df_melt
               .assign(Indicator = lambda x: x['indicator'].map(indicator_dict))
               .assign(Context = lambda x: x['compartment'].map(compartment_dict))
               .dropna(subset=['Indicator', 'value', 'Context'])
               .assign(i_unit = i_unit)
               .assign(Unit = 'kg')
               .rename(columns={'value': 'Characterization Factor',
                                'CAS': 'CAS No',
                                'i_unit': 'Indicator unit',
                                'Name': 'Flowable'})
               .assign(col = lambda x: x['indicator'].map(flag_dict))
               .assign(Flag = lambda x: x.apply(lambda row: row[row['col']], axis=1))
               ## ^^ pull in the appropriate flag column
               .drop(columns=['header', 'compartment', 'indicator', 'col'] + flag_cols)
               .fillna('')
               )

    # Duplicate indicators with and without Interim CFs
    df_combined = pd.concat([
        (df_melt
         .assign(Indicator = lambda x: x['Indicator'] + ' (Recommended and Interim)')),
        (df_melt
         .query('Flag != "F"')
         .assign(Indicator = lambda x: x['Indicator'] + ' (Recommended)'))]
        ).reindex(columns=lciafmt_cols).fillna('')

    return df_combined


if __name__ == "__main__":
    from lciafmt.util import store_method, save_json
    method = lciafmt.Method.USETOX
    df = get(method)
    mapping = method.get_metadata()['mapping']
    #%%
    mapped_df = lciafmt.map_flows(df, system=mapping)
    store_method(mapped_df, method)
    save_json(method, mapped_df)
