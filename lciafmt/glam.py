# glam.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
This module contains functions needed to compile LCIA methods from GLAM
"""

import pandas as pd
import os
import zipfile

import lciafmt
import lciafmt.cache as cache
import lciafmt.df as dfutil
from lciafmt.util import log


# https://www.lifecycleinitiative.org/activities/life-cycle-assessment-data-and-methods/global-guidance-for-life-cycle-impact-assessment-indicators-and-methods-glam/


def get(method) -> pd.DataFrame:
    """Generate a method for GLAM in standard format.

    :return: DataFrame of method in standard format
    """
    log.info("getting method GLAM")
    method_meta = method.get_metadata()
    _get_file(method_meta)
    df = pd.DataFrame()
    for xls_file in method_meta.get('file'):
        df1 = _read(cache.get_path(xls_file), 'lciamethods_CF_GLAM')
        df = pd.concat([df, df1], ignore_index=True)

    return df

def _get_file(method_meta, url=None):
    if url is None:
        url = method_meta['url']
    fname = os.path.basename(url)
    f = cache.get_or_download(fname, url)
    path = cache.get_folder()

    try:
        with zipfile.ZipFile(f, 'r') as zipf:
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
        raise FileNotFoundError(f"Error: ZIP file '{f}' not found.")


def _read(xls_file, sheet: str) -> pd.DataFrame:
    """Read the data from Excel with given path into a DataFrame."""
    df0 = pd.read_excel(xls_file, sheet_name=sheet)

    df = (df0
          # .query('FLOW_class2.isna()') # Drops scenarios
          # .query('LCIAMethod_mathematicalApproach == "Average"')
          .query('~LCIAMethod_location.str.startswith("x")')
          )

    records = []
    for index, row in df.iterrows():
        ind_unit, unit = row['Unit'].split('/')
        location = ("" if row["LCIAMethod_location"] == "GLO"
                    else row['LCIAMethod_location_name'])
        cas = (row['FLOW_casnumber'].lstrip('0') if isinstance(row['FLOW_casnumber'], str)
               else '')
        dfutil.record(records,
                      method='GLAM',
                      indicator=row['LCIAMethod_name'],
                      indicator_unit=ind_unit,
                      flow=row['FLOW_name'],
                      flow_category=row['FLOW_class2'],
                      flow_unit=unit,
                      cas_number=cas,
                      location=location,
                      factor=row['CF'])

    output_df = dfutil.data_frame(records)
    output_df = output_df.dropna(subset=['Flowable', 'Characterization Factor']).fillna('')

    return output_df


if __name__ == "__main__":
    from lciafmt.util import store_method, save_json
    method = lciafmt.Method.GLAM
    df = get(method)
    mapping = method.get_metadata()['mapping']
    #%%
    mapped_df = lciafmt.map_flows(df, system=mapping)
    store_method(mapped_df, method)
    # save_json(method, mapped_df)
