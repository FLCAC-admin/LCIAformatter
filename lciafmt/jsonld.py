# jsonld.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
Functions to support generating JSONLD files for lciafmt
"""

from typing import Optional
import pandas as pd
try:
    import olca_schema as o
    import olca_schema.units as units
    import olca_schema.zipio as zipio
except ImportError:
    raise ImportError("lciafmt now requires olca-schema to align with "
                      "openLCA v2.0. Use pip install olca-schema")

from esupy.util import make_uuid
from esupy.bibtex import generate_sources
from esupy.location import extract_coordinates, olca_location_meta
import fedelemflowlist
from .util import is_non_empty_str, generate_method_description,\
    log, pkg_version_number, datapath, check_as_class


def indicator_direction(contexts) -> Optional[str]:
    """Return ``INPUT``, ``OUTPUT``, or ``None`` for an impact category.

    Resource contexts are inputs and other contexts are outputs. openLCA
    negates a characterization factor when the flow direction differs from
    the category direction, so a category that contains both must leave
    direction unset and keep the stored signs.
    """
    flags = (pd.Series(list(contexts)).fillna('')
             .astype(str).str.startswith('resource'))
    if flags.empty:
        return None
    if bool(flags.all()):
        return 'INPUT'
    if not bool(flags.any()):
        return 'OUTPUT'
    return None


class Writer(object):

    def __init__(self, zip_file: str):
        log.debug(f"create JSON-LD writer on {zip_file}")
        self.__writer = zipio.ZipWriter(zip_file)
        self.__methods = {}
        self.__indicators = {}
        self.__directions = {}
        self.__flows = {}
        self.__coordinates = {}
        self.__locations = {}
        self.__location_meta = olca_location_meta().fillna('')
        self.__sources = {}
        self.__sources_to_write = {}
        self.__bibids = {}
        self.__bibpath = datapath / 'lcia.bib'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__writer.close()

    def write(self, df: pd.DataFrame,
              write_flows=False,
              preferred_only=False,
              regions=None # list, options include: 'states', 'countries'
              ):
        if any(df['Location'] != '') and regions is not None:
            coord = [extract_coordinates(group=r) for r in regions]
            self.__coordinates = {k: v for d in coord for k, v in d.items()}
        if 'source_method' not in df:
            df['source_method'] = df['Method']
        if 'source_indicator' not in df:
            df['source_indicator'] = ''
        if 'category' not in df:
            df['category'] = df['Method']

        methods = pd.unique(
                df[['Method', 'source_method']].values.ravel('K'))
        indicators = pd.unique(
                df[['Indicator', 'source_indicator']].values.ravel('K'))
        self.__directions = self._directions(df)

        # identify all relevant bib_ids and sources
        for method in methods:
            m = check_as_class(method)
            if isinstance(m, str):
                # not a recognized method, so no bib_id
                continue
            bib = m.get_metadata().get('bib_id')
            if bib:
                if isinstance(bib, str):
                    self.__bibids[bib] = m.value
                elif isinstance(bib, dict):
                    for k,v in bib.items():
                        self.__bibids[v] = f'{m.value} {k}'
        for i in generate_sources(self.__bibpath, self.__bibids):
            self.__sources[i.id] = i

        for _, row in df.iterrows():
            indicator = self.__indicator(row)
            factor = o.ImpactFactor()
            unit = row['Unit']
            factor.flow = self.__flow(row).to_ref()
            factor.flow_property = units.property_ref(unit)
            factor.unit = units.unit_ref(unit)
            factor.value = row['Characterization Factor']
            if self.__coordinates != {}:
                location = self.__location(row)
                factor.location = location.to_ref() if location else None
            indicator.impact_factors.append(factor)

        log.debug("write entities")
        dicts = [
            self.__indicators,
            self.__methods,
            self.__locations,
            self.__sources_to_write
        ]
        if write_flows:
            log.info("writing flows from the fedelemflowlist ...")
            flowlist = fedelemflowlist.get_flows(preferred_only)
            flow_dict = self.__flows
            flows = flowlist.query('`Flow UUID` in @flow_dict.keys()')
            if preferred_only:
                log.info("writing only preferred flows ...")
            elif len(flows) != len(flow_dict):
                log.warning("not all flows written...")
            fedelemflowlist.write_jsonld(flows, path=None,
                                         zw = self.__writer)
        for d in dicts:
            for v in d.values():
                self.__writer.write(v)

    def __indicator(self, row) -> o.ImpactCategory:
        uid = row['Indicator UUID']
        if not is_non_empty_str(uid):
            uid = make_uuid(row['category'], row['Indicator'])
        ind = self.__indicators.get(uid)
        if ind is not None:
            return ind
        log.info("writing %s indicator ...", row['Indicator'])
        ind = o.ImpactCategory()
        ind.id = uid
        ind.name = row['Indicator']
        ind.ref_unit = row['Indicator unit']
        ind.category = row['category']
        if 'Code' in row:
            ind.code = row['Code']
        direction = self.__directions.get(uid)
        if direction is None:
            log.info("%s has resource and emission factors; "
                     "impact direction left unspecified", row['Indicator'])
        else:
            ind.direction = o.Direction(direction)
        ind.description = generate_method_description(row['source_method'],
                                                      row['Indicator'],
                                                      row['source_indicator'])
        ind.impact_factors = []
        ind.version = pkg_version_number
        source = (self._return_source(row['source_method']) or
                  self._return_source(row['Method'] + ' ' +
                                      row['Indicator']) or
                  self._return_source(row['source_method'] + ' ' +
                                      row['source_indicator']))
        if source:
            ind.source = source.to_ref()
            self.__sources_to_write[source.id] = source
        self.__indicators[uid] = ind

        method = self.__method(row)
        method.impact_categories.append(ind.to_ref())
        return ind

    def _directions(self, df: pd.DataFrame) -> dict:
        """Map each indicator id to INPUT, OUTPUT, or None."""
        directions = {}
        grouped = {}
        for _, row in df.iterrows():
            uid = row['Indicator UUID']
            if not is_non_empty_str(uid):
                uid = make_uuid(row['category'], row['Indicator'])
            grouped.setdefault(uid, []).append(row['Context'])
        for uid, contexts in grouped.items():
            directions[uid] = indicator_direction(contexts)
        return directions

    def __method(self, row) -> o.ImpactMethod:
        uid = row['Method UUID']
        if not is_non_empty_str(uid):
            uid = make_uuid(row['Method'])
        m = self.__methods.get(uid)
        if m is not None:
            return m
        log.info("writing %s method ...", row['Method'])
        m = o.ImpactMethod()
        m.id = uid
        m.name = row['Method']
        m.version = pkg_version_number
        source = self._return_source(row['Method'])
        if source:
            m.source = source.to_ref()
            self.__sources_to_write[source.id] = source
        m.impact_categories = []
        m.description = generate_method_description(row['Method'])
        self.__methods[uid] = m
        return m

    def __flow(self, row):
        uid = row['Flow UUID']
        if not is_non_empty_str(uid):
            uid = make_uuid(row['Flowable'], row['Context'], row['Unit'])

        flow = self.__flows.get(uid)
        if flow is not None:
            return flow
        flow = o.Flow()
        flow.id = uid
        flow.name = row['Flowable']
        flow.category = 'Elementary flows/' + row['Context']
        flow.cas = row['CAS No']
        flow.flow_type = o.FlowType.ELEMENTARY_FLOW

        # flow property
        prop_ref = units.property_ref(row['Unit'])
        if prop_ref is None:
            log.error("could not infer flow property for unit %s", row['Unit'])
        if prop_ref is not None:
            prop_fac = o.FlowPropertyFactor()
            prop_fac.conversion_factor = 1.0
            prop_fac.is_ref_flow_property = True
            prop_fac.flow_property = prop_ref
            flow.flow_properties = [prop_fac]

        # category
        flow.category=row.Context

        self.__flows[uid] = flow
        return flow

    def __location(self, row):
        if row['Location'] == '':
            # no location specified
            return None
        meta = (self.__location_meta.loc[
            self.__location_meta['Code'] == row['Location']].squeeze())
        if len(meta) == 0:
            # not an available location
            return None
        location = self.__locations.get(meta.ID)
        if location is not None:
            # location found, no need to regenerate
            return location
        location = o.Location(
            id=meta.ID,
            name=meta.Name,
            description=meta.Description,
            category=meta.Category,
            code=meta.Code,
            geometry=self.__coordinates.get(row['Location'], {}).get('geometry'),
            latitude=meta.Latitude,
            longitude=meta.Longitude)
        self.__locations[meta.ID] = location
        return location

    def _return_source(self, name):
        for uid, s in self.__sources.items():
            if s.name == name or name.startswith(s.name):
                return s
        return None
