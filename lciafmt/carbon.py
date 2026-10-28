"""Gross biogenic carbon accounting on an existing FEDEFL stock mapping.

The stock mapping file stays the 0/0 biogenic policy. Gross accounting (+1/-1)
is applied in memory with fedelemflowlist's CARBON_GHG_POLICY, then the chosen
indicators are mapped a second time and suffixed.
"""
import pandas as pd

GROSS_SUFFIX = ' Gross Biogenic'


def gross_biogenic_mapping(mapping_name: str) -> pd.DataFrame:
    """Return ``mapping_name`` with gross biogenic carbon rows substituted.

    ``mapping_name`` must be a stock FEDEFL mapping whose method is listed in
    ``CO2_SOURCE_BY_METHOD`` (for example ``IPCC``, ``TRACI2.1``, ``TRACI2.2``).
    """
    import fedelemflowlist
    from fedelemflowlist.globals import add_uuid_to_mapping
    from fedelemflowlist.lcia_mapping import (
        CARBON_GHG_POLICY, apply_carbon_ghg_policy)

    mapping = fedelemflowlist.get_flowmapping(source=mapping_name)
    updated = apply_carbon_ghg_policy(
        mapping, mapping_name, policy=CARBON_GHG_POLICY)
    missing = updated['TargetFlowUUID'].isna()
    if not missing.any():
        return updated
    filled = add_uuid_to_mapping(
        updated.loc[missing].drop(columns=['TargetFlowUUID']))
    keep = updated.loc[~missing]
    return pd.concat([keep, filled], ignore_index=True)


def map_with_gross_biogenic(df: pd.DataFrame, mapping_name: str,
                            indicators=None) -> pd.DataFrame:
    """Map ``df`` and append gross-biogenic copies of the selected indicators.

    :param mapping_name: stock FEDEFL mapping (SourceListName), such as
        ``IPCC`` or ``TRACI2.1``
    :param indicators: indicator name or names to publish again with gross
        biogenic accounting. None publishes every indicator in ``df``.
    """
    import lciafmt
    from lciafmt.util import log

    stock = lciafmt.map_flows(df, system=mapping_name)
    if indicators is None:
        selected = df
        label = 'all indicators'
    else:
        names = [indicators] if isinstance(indicators, str) else list(indicators)
        selected = df[df['Indicator'].isin(names)]
        label = ', '.join(names)
    if selected.empty:
        log.warning("no rows for %s; gross biogenic indicators skipped", label)
        return stock
    gross = lciafmt.map_flows(
        selected, system=mapping_name,
        mapping=gross_biogenic_mapping(mapping_name))
    gross = gross.copy()
    gross['Indicator'] = gross['Indicator'] + GROSS_SUFFIX
    log.info("appended gross biogenic indicators for %s (%i factors)",
             label, len(gross))
    return pd.concat([stock, gross], ignore_index=True)
