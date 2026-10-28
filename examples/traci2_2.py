import pandas as pd
import lciafmt
from lciafmt.util import store_method, save_json, log
import esupy.location


method = lciafmt.Method.TRACI2_2
regions = ['states', 'countries']

def main():

    df = lciafmt.get_method(method)
    mapping = method.get_metadata()['mapping']
    mapped_df = lciafmt.map_with_gross_biogenic(
        df, mapping, indicators='Global warming')

    # write the result to parquet, includes states and counties as FIPS,
    # and all countries
    store_method(mapped_df, method)

    # Assigns codes to states e.g., "US-AL", leaves counties as FIPS
    state_df = esupy.location.assign_state_abbrev(mapped_df)

    # Convert country names to ISO Country codes, not all will map
    country_codes = (esupy.location.read_iso_3166()
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

    save_json(method, all_df, regions=regions)

if __name__ == "__main__":
    main()
    mapped_df = lciafmt.get_mapped_method(method)
