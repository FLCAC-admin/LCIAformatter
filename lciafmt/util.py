# util.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
This module contains common functions for processing LCIA methods
"""

import sys

import lciafmt
import logging as log
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from esupy.location import assign_state_abbrev, read_iso_3166
from esupy.processed_data_mgmt import Paths, FileMeta, load_preprocessed_output,\
    write_df_to_file, write_metadata_to_file, download_from_remote, \
    mkdir_if_missing
from esupy.util import get_git_hash
from fedelemflowlist.globals import flow_list_specs


# set version number of package, needs to be updated with setup.py
pkg_version_number = '1.3.0'
MODULEPATH = Path(__file__).resolve().parent
datapath = MODULEPATH / 'data'

log.basicConfig(level=log.INFO, format='%(asctime)s %(levelname)-8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S', stream=sys.stdout)

# Common declaration of write format for package data products
write_format = "parquet"

paths = Paths()
paths.local_path = paths.local_path / 'lciafmt'
OUTPUTPATH = paths.local_path

GIT_HASH = get_git_hash()

method_metadata = {
    'Name': '',
    'Version': '',
    'Source': '',
    'SourceType': '',
    'Citation': '',
    }


def set_lcia_method_meta(method_id):
    lcia_method_meta = FileMeta()
    if isinstance(method_id, lciafmt.Method):
        lcia_method_meta.name_data = method_id.get_filename()
        lcia_method_meta.category = method_id.get_path()
    elif method_id is None:
        lcia_method_meta.name_data = ""
        lcia_method_meta.category = ""
    else:
        lcia_method_meta.name_data = method_id
    lcia_method_meta.tool = "lciafmt"
    lcia_method_meta.tool_version = pkg_version_number
    lcia_method_meta.ext = write_format
    lcia_method_meta.git_hash = GIT_HASH
    lcia_method_meta.date_created = pd.to_datetime('today').strftime('%Y-%m-%d %H:%M:%S')
    return lcia_method_meta


def is_non_empty_str(s: str) -> bool:
    """Tests if the given parameter is a non-empty string."""
    if not isinstance(s, str):
        return False
    return s.strip() != ""


def format_cas(cas) -> str:
    """In LCIA method sheets CAS numbers are often saved as numbers. This
    function formats such numbers to strings that matches the general
    format of a CAS numner. It also handles other cases like None values.
    """
    if cas is None:
        return ""
    if cas == "x" or cas == "-":
        return ""
    if isinstance(cas, (int, float)):
        cas = str(int(cas))
        if len(cas) > 4:
            cas = cas[:-3] + "-" + cas[-3:-1] + "-" + cas[-1]
        return cas
    return str(cas)


def aggregate_factors_for_primary_contexts(df) -> pd.DataFrame:
    """
    When factors don't exist for flow categories with only a primary context, like "air", but do
    exist for 1 or more categories where secondary contexts are present, like "air/urban", then this
    function creates factors for that primary context as an average of the factors from flows
    with the same secondary context. NOTE this will overwrite factors if they already exist
    :param df: a pandas dataframe for an LCIA method
    :return: a pandas dataframe for an LCIA method
    """
    # Ignore the following impact categories for generating averages
    ignored_categories = ['Land transformation', 'Land occupation',
                          'Water consumption', 'Mineral resource scarcity',
                          'Fossil resource scarcity']
    indices = df['Context'].str.find('/')
    ignored_list = df['Indicator'].isin(ignored_categories)
    i = 0
    for k in ignored_list.items():
        if k[1]:
            indices.update(pd.Series([-1], index=[i]))
        i = i + 1

    primary_context = []
    i = 0
    for c in df['Context']:
        if indices[i] > 0:
            sub = c[0:indices[i]]+"/unspecified"
        else:
            sub = None
        i = i + 1
        primary_context.append(sub)

    df['Primary Context'] = primary_context
    # Subset the df to only include the rows were a primary context was added
    df_secondary_context_only = df[df['Primary Context'].notnull()]

    # Determine fields to aggregate over. Do not use flow UUID or old context
    agg_fields = list(set(df.columns) - {'Context', 'Flow UUID',
                                         'Characterization Factor'})

    # drop primary context field from df
    df = df.drop(columns=['Primary Context'])

    df_secondary_agg = df_secondary_context_only.groupby(agg_fields, as_index=False).agg(
        {'Characterization Factor': np.average})
    df_secondary_agg = df_secondary_agg.rename(columns={"Primary Context": "Context"})

    df = pd.concat([df, df_secondary_agg], ignore_index=True, sort=False)
    return df


def get_modification(source, name) -> pd.DataFrame:
    """Return a dataframe of modified CFs based on csv."""
    modified_factors = pd.read_csv(datapath / f'{source}_{name}.csv')
    return modified_factors


def collapse_indicators(df) -> pd.DataFrame:
    """Collapse instances of duplicate flows per indicator.

    For a given flow for an indicator, only one characterization factor
    should be present. In some cases, due to lack of detail in target flow list,
    this assumption is invalid. This function collapses those instances and
    returns an average characterization factor.
    """
    cols = ['Method', 'Indicator', 'Indicator unit', 'Flow UUID']
    duplicates = df[df.duplicated(subset=cols, keep=False)]
    cols_to_keep = [c for c in df.columns.values.tolist() if 
                    c not in ('Characterization Factor', 'CAS No')]
    df2 = (df.groupby(cols_to_keep, as_index=False)
             .agg({'Characterization Factor': 'mean',
                   'CAS No': 'first'}))
    log.info(f'{len(duplicates)} duplicate factors consolidated to '
             f'{(len(duplicates)-(len(df)-len(df2)))}')

    return df2


def check_as_class(method_id):
    if not isinstance(method_id, lciafmt.Method):
        method_id = lciafmt.Method.get_class(method_id)
    return method_id


def generate_method_description(name: str,
                                indicator: str='',
                                source_indicator: str=''
                                ) -> str:
    with open(datapath / "description.yaml") as f:
        generic = yaml.safe_load(f)
    desc = generic['base']
    method = check_as_class(name)
    if type(method) is str:
        method_meta = {}
        method_meta['name'] = name
        method_meta['url'] = ''
        method_meta['citation'] = ''
    else:
        method_meta = method.get_metadata()
        desc += generic['description']
    if 'mapping' in method_meta:
        desc += generic['mapping']
    if 'detail_note' in method_meta:
        desc += method_meta['detail_note']
    if 'methods' in method_meta:
        try:
            detailed_meta = '\n\n' + method_meta['methods'][name]
            desc += detailed_meta
        except KeyError:
            log.debug(f'{name} not found in methods.json')
    if indicator:
        desc = generic['indicator']
    if source_indicator:
        desc = generic['source_indicator'] 

    # Replace tagged fields
    if 'version' in method_meta:
        version = ' (v' + method_meta['version'] + ')'
    else:
        version = ''
    desc = (desc
            .replace('[LCIAfmt_version]', pkg_version_number)
            .replace('[FEDEFL_version]', flow_list_specs['list_version'])
            .replace('[fedelemflowlist_version]', flow_list_specs['tool_version'])
            .replace('[Method]', method_meta['name'])
            .replace('[version]', version)
            .replace('[citation]', method_meta['citation'])
            .replace('[url]', method_meta['url'])
            .replace('[Indicator]', indicator)
            .replace('[source_indicator]', source_indicator)
            )

    return desc


def compile_metadata(method_id):
    """Compile metadata for a method."""
    metadata = dict(method_metadata)
    method_meta = {}
    if method_id is not None:
        method_meta = method_id.get_metadata()
    match_dict = {'Name': 'name',
                  'Version': 'version',
                  'Source': 'url',
                  'SourceType': 'source_type',
                  'Citation': 'citation',
                  }
    for k, v in match_dict.items():
        if v in method_meta:
            metadata[k] = method_meta[v]
    return metadata


def store_method(df, method_id, name=''):
    """Save the method as a dataframe to parquet file."""
    meta = set_lcia_method_meta(method_id)
    method_path = OUTPUTPATH / meta.category
    if name != '':
        meta.name_data = name
    elif meta.name_data == '':
        meta.name_data = df['Method'][0]
    meta.tool_meta = compile_metadata(method_id)
    try:
        log.info(f'saving {meta.name_data} to {method_path}')
        write_df_to_file(df, paths, meta)
        write_metadata_to_file(paths, meta)
    except:
        log.error('Failed to save method')


def read_method(method_id):
    """Return the method stored in output."""
    meta = set_lcia_method_meta(method_id)
    method = load_preprocessed_output(meta, paths)
    method_path = OUTPUTPATH / meta.category
    if method is None:
        log.info(f'{meta.name_data} not found in {method_path}')
    else:
        log.info(f'loaded {meta.name_data} from {method_path}')
    return method


def download_method(method_id):
    """Downloads the method from data commons."""
    meta = set_lcia_method_meta(method_id)
    download_from_remote(meta, paths)


def save_json(method_id, mapped_data, method=None, name='',
              write_flows=False, **kwargs):
    """Save a method as json file in the outputpath.

    :param method_id: class Method
    :param mapped_data: df of mapped method to save
    :param method: str, name of method to subset the passed mapped_data
    :param name: str, optional method name when method_id does not exist
    :param write_flows: bool
    """
    meta = set_lcia_method_meta(method_id)
    if name == '':
        filename = meta.name_data
    else:
        filename = name
    if method is not None:
        filename = method.replace('/', '_')
        mapped_data = mapped_data.query('Method == @method').reset_index(drop=True)
    path = OUTPUTPATH / meta.category
    mkdir_if_missing(OUTPUTPATH)
    json_pack = path / f'{filename}_json_v{meta.tool_version}.zip'
    json_pack.unlink(missing_ok=True)
    lciafmt.to_jsonld(mapped_data, json_pack, write_flows=write_flows,
                      **kwargs)


def compare_to_remote(local_df, method_id):
    """Compares a impact method dataframe to that same method on remote.

    Differences in characterization factors are stored to local/lciafmt/diff."""
    meta = set_lcia_method_meta(method_id)
    status = download_from_remote(meta, paths)
    if not status:
        log.warning('Error accessing remote')
        return
    remote_df = load_preprocessed_output(meta, paths)
    merge_cols = ['Method', 'Indicator', 'Flowable', 'Flow UUID',
                  'Context']
    cols = merge_cols + ['Characterization Factor']
    df = pd.merge(local_df[cols], remote_df[cols],
                  how='outer', on=merge_cols, suffixes=('','_remote'))
    df_diff = df.query('`Characterization Factor` '
                       '!= `Characterization Factor_remote`')
    if len(df_diff) > 0:
        path = paths.local_path / 'diff'
        mkdir_if_missing(path)
        log.info(f'Saving differences found in {method_id.name} '
                 f'versus remote to {path}')
        df_diff.to_csv(f'{path}/{method_id.name}_diff.csv', index=False)
    else:
        log.info(f'No differences found comparing {method_id.name} '
                 'to remote')


def drop_county_data_and_assign_names(df):
    """Assigns state abbreviations to FIPS codes and names to countries.
    All data not assigned (i.e., counties) are dropped."""
    # Assigns codes to states e.g., "US-AL", leaves counties as FIPS
    df['Location'] = df['Location'].replace('United States of America', '00000')
    state_df = assign_state_abbrev(df)

    # Convert country names to ISO Country codes, not all will map
    country_codes = (read_iso_3166()
                     .filter(['Name', 'ISO-2d'])
                     .set_index('Name')['ISO-2d'].to_dict())
    # prevents dropping of the factors without locations
    country_codes[''] = ''
    all_df = state_df.copy()
    all_df['Location'] = (all_df['Location']
                          .map(country_codes)
                          .fillna(all_df['Location']))
    all_df = (all_df.query('Location.isin(@country_codes.values()) |'
                           'Location == "US" |'
                           'Location.str.startswith("US-")')
              .reset_index(drop=True))
    return all_df


def drop_county_data(df):
    """Assigns state abbreviations to FIPS codes then drops all numeric
    locations."""
    # Assigns codes to states e.g., "US-AL", leaves counties as FIPS
    state_df = assign_state_abbrev(df)
    all_df = state_df[~state_df.Location.str.contains(r'[0-9]')]
    return all_df.reset_index(drop=True)
