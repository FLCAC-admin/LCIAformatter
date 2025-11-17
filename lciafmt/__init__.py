# __init__.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
Public API for lciafmt. Standardizes the format and flows of life cycle
impact assessment (LCIA) data and optionally applies flow mappings as defined
in the Federal LCA Commons Elementary Flow List.
"""

import json
from typing import Union

import pandas as pd

import lciafmt.cache as cache
import lciafmt.ced as ced
import lciafmt.fmap as fmap
import lciafmt.jsonld as jsonld
import lciafmt.traci as traci
import lciafmt.recipe as recipe
import lciafmt.ipcc as ipcc
import lciafmt.fedefl_inventory as fedefl_inventory
import lciafmt.util as util
import lciafmt.endpoint as ep
import lciafmt.custom as custom
from lciafmt.custom import generate_lcia_compilation


from enum import Enum


class Method(Enum):
    """LCIAFormatter Method object with available metadata."""

    TRACI = "TRACI 2.1"
    TRACI2_2 = "TRACI 2.2"
    RECIPE_2016 = "ReCiPe 2016"
    FEDEFL_INV = "FEDEFL Inventory"
    CED = "Cumulative Energy Demand"
    ImpactWorld = "ImpactWorld"
    IPCC = "IPCC"

    def get_metadata(cls):
        """Return the stored metadata."""
        metadata = supported_methods()
        for m in metadata:
            if 'case_insensitivity' in m:
                if m['case_insensitivity'] == 'True':
                    m['case_insensitivity'] = True
                else:
                    m['case_insensitivity'] = False
            if m['id'] == cls.name:
                return m

    def get_filename(cls) -> str:
        """Generate standard filename from method name."""
        filename = cls.get_metadata()['name'].replace(" ", "_")
        return filename

    def get_path(cls) -> str:
        """Return category folder name for local storage."""
        path = cls.get_metadata()['path']
        return path

    def get_class(name: str):
        """Parse method_id from passed string and returns method object."""
        for n, c in Method.__members__.items():
            m = c.get_metadata()
            mapping = None
            methods = {}
            if 'mapping' in m:
                mapping = m['mapping']
            if 'methods' in m:
                methods = m['methods']
            if n == name or c.value == name or mapping == name or name in methods.keys():
                return c
        util.log.warning(f'{name} is not a LCIAfmt Method')
        return name


def supported_methods() -> list:
    """Return a list of dictionaries of supported method meta data."""
    json_file = util.datapath / 'methods.json'
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_method(method_id, **kwargs) -> pd.DataFrame:
    """Generate the method from source in standard format.

    The IDs of supported methods can be obtained using `supported_methods` or
    directly use the constants defined in the Method enumeration type.
    :param method_id: class Method or str, based on id field of
        supported_methods
    :param kwargs:
      - add_factors_for_missing_contexts: bool, if True applies
        lciafmt.util.aggregate_factors_for_primary_contexts to generate average
        factors for unspecified contexts
      - endpoint: bool, pass-through for RECIPE_2016, if True generates
        endpoint indicators from midpoints
      - summary: bool, pass-through for RECIPE_2016, if True aggregates
        endpoint methods into summary indicators
      - subset: pass-through for FEDEFL_INV, a list of dictionary keys from
        available inventory methods in fedelemflowlist, if none provided all
        available methods will be generated
      - region: pass-through for IW+, use three digit alphanumeric code for a
        specific country (e.g. "USA"), None for global factors, or 'All' for all
        countries and global factors.
      - file: str, alternate filepath for method, defaults to file stored
        in cache
      - url: str, alternate url for method, defaults to url in method config
    :return: DataFrame of method in standard format
    """
    file = kwargs.get('file')
    url = kwargs.get('url')
    if not method_id:
        return custom.get_custom_method(file=file)
    else:
        method_id = util.check_as_class(method_id)
    if method_id == Method.TRACI or method_id == Method.TRACI2_2:
        return traci.get(method_id,
                         add_factors_for_missing_contexts=kwargs.get('add_factors_for_missing_contexts', True),
                         file=file, url=None)
    if method_id == Method.RECIPE_2016:
        return recipe.get(add_factors_for_missing_contexts=kwargs.get('add_factors_for_missing_contexts', True),
                          endpoint=kwargs.get('endpoint', True),
                          summary=kwargs.get('summary', False),
                          file=file, url=url)
    if method_id == Method.ImpactWorld:
        import lciafmt.iw as impactworld
        return impactworld.get(file=file, url=url, region=kwargs.get('region'))
    if method_id == Method.IPCC:
        return ipcc.get()
    if method_id == Method.FEDEFL_INV:
        return fedefl_inventory.get(subset=kwargs.get('subset'))
    if method_id == Method.CED:
        return ced.get()


def clear_cache():
    """Delete all stored methods in local temporary cache."""
    cache.clear()


def to_jsonld(df: pd.DataFrame, zip_file: str, write_flows=False, **kwargs):
    """Generate a JSONLD file of the methods passed as DataFrame."""
    util.log.info(f"write JSON-LD package to {zip_file}")
    with jsonld.Writer(zip_file) as w:
        w.write(df, write_flows=write_flows,
                preferred_only=kwargs.get('preferred_only', False),
                regions=kwargs.get('regions'),
                )


def map_flows(df: pd.DataFrame, system=None, mapping=None,
              preserve_unmapped=False, case_insensitive=False) -> pd.DataFrame:
    """Map the flows in a method using a mapping from fedelemflowlist.

    :param system: str, the named mapping file from fedelemflowlist
    :param mapping: df, alternate mapping that meets FEDEFL mapping file
        specifications
    :param preserve_unmapped: bool, if True unmapped flows remain in the method
    :param case_insensitive, bool, if True case is ignored for source flows
    :return: DataFrame of method with mapped flows.
    """
    mapper = fmap.Mapper(df, system=system, mapping=mapping,
                         preserve_unmapped=preserve_unmapped,
                         case_insensitive=case_insensitive)
    mapped = mapper.run()
    x = mapped[mapped[['Method', 'Indicator', 'Flowable', 'Flow UUID', 'Location']
                      ].duplicated(keep=False)]
    duplicates = list(set(zip(x.Indicator, x.Flowable)))
    if len(duplicates) > 0:
        util.log.warning(f'Identified duplicate factors for {len(duplicates)} '
                         f'flow/indicator combinations and {len(x)} factors.')
        util.log.debug(f'{duplicates}')
        util.log.warning('Use collapse_indicators() to drop these duplicates.')
    return mapped


def supported_mapping_systems() -> list:
    """Return supported mapping systems."""
    return fmap.supported_mapping_systems()


def get_mapped_method(method_id, indicators=None, methods=None,
                      download_from_remote=False) -> pd.DataFrame:
    """Return a mapped method stored as parquet.

    If a mapped method does not exist locally, it is generated.
    :param method_id: class Method or str, based on id field of
        supported_methods
    :param indicators: list, if not None, return only those indicators passed
    :param methods: list, if not None, return only the version of the methods
        passed. Applies only to methods with multiple versions.
    :param download_from_remote: bool, if True, download from remote before
        generating method locally.
    :return: DataFrame of mapped method
    """
    method_id = util.check_as_class(method_id)
    mapped_method = util.read_method(method_id)
    if mapped_method is None:
        if isinstance(method_id, str):
            raise FileNotFoundError
        elif download_from_remote:
            util.download_method(method_id)
            mapped_method = util.read_method(method_id)
        if mapped_method is None:
            util.log.info('generating ' + method_id.name)
            method = get_method(method_id)
            if 'mapping' in method_id.get_metadata():
                mapping_system = method_id.get_metadata()['mapping']
                case_insensitive = method_id.get_metadata()['case_insensitivity']
                if case_insensitive:
                    method['Flowable'] = method['Flowable'].str.lower()
                mapped_method = map_flows(method, system=mapping_system,
                                          case_insensitive=case_insensitive)
                mapped_method = util.collapse_indicators(mapped_method)
            else:
                mapped_method = method
        util.store_method(mapped_method, method_id)
    if indicators is not None:
        mapped_method = mapped_method[mapped_method['Indicator'].isin(indicators)]
        if len(mapped_method) == 0:
            util.log.error('indicator not found')
    if methods is not None:
        mapped_method = mapped_method[mapped_method['Method'].isin(methods)]
        if len(mapped_method) == 0:
            util.log.error('specified method not found')
    mapped_method.reset_index(drop=True, inplace=True)
    return mapped_method


def generate_endpoints(file: Union[str, pd.DataFrame],
                       name=None,
                       matching_fields=None,
                       download_from_remote=False) -> pd.DataFrame:
    """Generate an endpoint method for a supplied file based on specs.

    :param file: str name of file in data folder, without extension, containing
        endpoint data based on the format specs for endpoint files, or
        pd.DataFrame
    :param name: str, optional str for naming the generated method
    :param matching_fields: list of fields on which to apply unique endpoint
        conversions, if None
    :param download_from_remote: bool, if True, download from remote before
        generating method locally.
    :return: DataFrame of endpoint method
    """
    if isinstance(file, pd.DataFrame):
        endpoints = file
    else:
        endpoints = pd.read_csv(util.datapath / f'{file}.csv')
    if matching_fields is None:
        matching_fields = ['Indicator']
    method = ep.apply_endpoints(endpoints, matching_fields,
                                download_from_remote)
    if name is None:
        method['Method'] = file
    else:
        method['Method'] = name
    return method


def supported_indicators(method_id) -> list:
    """Return a list of indicators for the identified method_id."""
    method_id = util.check_as_class(method_id)
    method = util.read_method(method_id)
    if method is not None:
        indicators = set(list(method['Indicator']))
        return list(indicators)
    else:
        return None


def apply_lcia_method(df, method_id) -> pd.DataFrame:
    """Applies characterization factors to a dataframe.

    :param df: dataframe containing 'FlowAmount' and 'FlowUUID' columns
    :param method_id: class Method or str, based on id field of
        supported_methods
    :return: DataFrame with impact method applied as 'Impact' column
    """
    if 'FlowUUID' not in df.columns or 'FlowAmount' not in df.columns:
        raise TypeError ('DataFrame must containt "FlowUUID" and '
                         '"FlowAmount" columns')
    impact_method = (
        get_mapped_method(method_id)
        .drop(columns=['Flowable', 'Context', 'Location', 'Location UUID',
                       'CAS No', 'Method UUID','Indicator UUID','Unit'])
        .rename(columns={'Flow UUID':'FlowUUID'}))

    impacts = df.merge(impact_method, how = 'inner',
                       on = ['FlowUUID'])
    impacts['Impact'] = (impacts['FlowAmount'] *
                         impacts['Characterization Factor'])

    return impacts
