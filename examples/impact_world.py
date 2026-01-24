import lciafmt
from lciafmt.util import store_method, collapse_indicators, save_json
import esupy.location

method = lciafmt.Method.ImpactWorld
regions = ['states', 'countries']

def main():

    data = lciafmt.get_method(method)

    # map the flows to the Fed.LCA commons flows
    # set preserve_unmapped=True if you want to keep unmapped
    # flows in the resulting data frame
    mapping = method.get_metadata()['mapping']
    mapped_data = lciafmt.map_flows(data, system=mapping)

    mapped_data = collapse_indicators(mapped_data)

    # Drop select indicators for incompatability with FEDEFL
    drop_list = [
        'Thermally polluted water',
        'Land transformation, biodiversity',
        'Fisheries impact',
        'Plastics physical effects on biota',
        ]
    mapped_data = mapped_data.query('Indicator not in @drop_list')

    # write the result to parquet
    store_method(mapped_data, method)

    # Convert country names to ISO Country codes, not all will map
    country_codes = (esupy.location.read_iso_3166()
                     .filter(['Name', 'ISO-2d'])
                     .set_index('Name')['ISO-2d'].to_dict())
    # prevents dropping of the factors without locations
    country_codes[''] = ''
    all_df = mapped_data.copy()
    all_df['Location'] = (all_df['Location']
                          .map(country_codes)
                          .fillna(all_df['Location']))
    all_df = (all_df.query('Location.isin(@country_codes.values()) |'
                           'Location == "US" |'
                           'Location.str.startswith("US-")')
              .reset_index(drop=True))

    # write the result to JSON-LD
    for m in all_df['Method'].unique():
        save_json(method, all_df, m, regions=regions, write_flows=True)


if __name__ == "__main__":
    main()
    mapped_data = lciafmt.get_mapped_method(method)
