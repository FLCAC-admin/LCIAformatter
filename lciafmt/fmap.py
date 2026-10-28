# fmap.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
Functions to support flow mapping for lcia methods
"""

from typing import List

import pandas as pd
import fedelemflowlist as flowlist
from esupy.util import make_uuid

import lciafmt.df as dfutil
from .util import log


def supported_mapping_systems() -> list:
    fmap = flowlist.get_flowmapping()  # type: pd.DataFrame
    systems = set()
    for i in range(0, len(fmap.index)):
        systems.add(fmap.iat[i, 0])
    return list(systems)


def norm_category(category_path: str) -> str:
    if category_path is None:
        return ""
    parts = [p.strip(" -").lower() for p in category_path.split("/")]

    norm = []
    for part in parts:

        # ignore words with no relevance
        if part in ("elementary flows"):
            continue

        term = part

        # separate qualifiers
        qualifiers = None
        if "," in part:
            pp = [p.strip() for p in part.split(",")]
            term = pp[0]
            qualifiers = pp[1:]

        # remove prefixes
        if term.startswith("emission to "):
            term = term[12:].strip()
        if term.startswith("in ") or term.startswith("to "):
            term = term[3:].strip()

        # replace words
        if term == "high population density":
            term = "urban"
        if term == "low population density":
            term = "rural"

        if len(norm) > 0:
            # if term(i) == term(i - 1)
            if norm[-1] == term:
                if qualifiers is None:
                    continue
                norm.append(", ".join(qualifiers))
                continue
            # if term(i) ends with term(i - 1)
            if term.endswith(norm[-1]):
                term = term[0:-(len(norm[-1]))].strip(" -")

        # append qualifiers
        if qualifiers is not None:
            term = ", ".join([term] + qualifiers)

        norm.append(term)

    return "/".join(norm)


def _is_empty(val: str) -> bool:
    if val is None or val == "":
        return True
    if isinstance(val, str):
        return val.strip() == ""
    return False


def _is_strv(val) -> bool:
    if not isinstance(val, str):
        return False
    return not _is_empty(val)


class _FlowInfo(object):

    def __init__(self, uuid="", name="", category="", unit="",
                 conversionfactor="1.0"):
        self.name = name
        self.category = category
        self.unit = "kg" if not _is_strv(unit) else unit
        self.conversionfactor = str(conversionfactor)
        if not _is_strv(uuid):
            self.uuid = make_uuid(self.name, self.category, self.unit)
        else:
            self.uuid = uuid


class Mapper(object):

    def __init__(self, df: pd.DataFrame, system=None, mapping=None,
                 preserve_unmapped=False, case_insensitive=False):
        self.__df = df
        self.__system = system
        self.__case_insensitive = case_insensitive
        if mapping is None:
            if system is None:
                log.warning("pass dataframe as mapping or identify system")
            else:
                log.info(f"loading flow mapping {system} from fedelemflowlist")
                mapping = flowlist.get_flowmapping(source=system)
                if self.__case_insensitive:
                    mapping['SourceFlowName'] = mapping['SourceFlowName'].str.lower()
        self.__mapping = mapping  # type: pd.DataFrame
        self.__preserve_unmapped = preserve_unmapped

    def run(self) -> pd.DataFrame:
        if self.__mapping is None:
            log.warning("No mapping applied")
            return self.__df
        map_idx = self._build_map_index()
        log.info("applying flow mapping...")
        mapped = 0
        preserved = 0
        df = self.__df
        records = []
        for row in range(0, self.__df.shape[0]):
            key = Mapper._flow_key(
                uuid=df.iat[row, 6],
                name=df.iat[row, 5],
                category=df.iat[row, 7],
                unit=df.iat[row, 8],
            )
            targets = map_idx.get(key)  # type: List[_FlowInfo]

            if targets is None:
                log.debug("could not map flow %s", key)
                if self.__preserve_unmapped:
                    records.append(dfutil.as_list(df, row=row))
                    preserved += 1
                continue

            rec = dfutil.as_list(df, row=row)
            for target in targets:
                r = rec.copy()
                r[5] = target.name
                r[6] = target.uuid
                r[7] = target.category
                r[8] = target.unit
                # ConversionFactor is a divisor (unit / stock scaling). A factor
                # of 0 means the mapped characterization factor should be 0;
                # dividing would yield inf/NaN.
                conv = float(target.conversionfactor)
                if conv == 0.0:
                    r[12] = 0.0
                else:
                    r[12] = r[12] / conv
                records.append(r)
                mapped += 1
        log.info("created %i factors for mapped flows; " +
                 "preserved %i factors for unmapped flows",
                 mapped, preserved)
        return dfutil.data_frame(records)

    def _build_map_index(self) -> dict:
        log.debug("index flows")
        map_idx = {}
        for _, row in self.__mapping.iterrows():
            sys = row["SourceListName"]
            if self.__system is not None and sys != self.__system:
                continue
            key = Mapper._flow_key(
                uuid=row["SourceFlowUUID"],
                name=row["SourceFlowName"],
                category=row["SourceFlowContext"],
                unit=row["SourceUnit"],
            )
            targets = map_idx.get(key)
            if targets is None:
                targets = []
                map_idx[key] = targets
            targets.append(_FlowInfo(
                uuid=row["TargetFlowUUID"],
                name=row["TargetFlowName"],
                category=row["TargetFlowContext"],
                unit=row["TargetUnit"],
                conversionfactor=row["ConversionFactor"]
            ))

        log.info("indexed %i mappings for %i flows",
                 self.__mapping.shape[0], len(map_idx))
        return map_idx

    @staticmethod
    def _flow_key(uuid="", name="", category="", unit="") -> str:
        if _is_strv(uuid) and uuid != "":
            return uuid
        parts = [name]
        if _is_strv(category):
            parts.append(norm_category(category))
        if _is_strv(unit):
            parts.append(unit)
        else:
            parts.append("kg")
        parts = [p.strip().lower() for p in parts]
        return "/".join(parts)
