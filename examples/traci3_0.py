import pandas as pd
import lciafmt
from lciafmt.util import store_method, save_json, log, drop_county_data,\
    drop_county_data_and_assign_names, OUTPUTPATH


method = lciafmt.Method.TRACI3_0
regions = ['states', 'countries']
write_condensed_to_excel = True
write_flows_to_json = True

def main():

    # Generate and then store the method
    df = lciafmt.get_method(method)
    store_method(df, method)

    if write_condensed_to_excel:
        # writes a condensed version of the full method which excludes:
        # emissions for Ozone Formation beyond generic emission/air
        # state and country data only, no counties
        df_no_counties = drop_county_data(df)
        smog = df_no_counties.query('Indicator == "Ozone Formation"')
        final_df = pd.concat([
            df_no_counties.query('Indicator != "Ozone Formation"')
                          .assign(Location = lambda x: x['Location']
                                  .replace('US', 'United States of America')),
            smog.query('Context == "emission/air"')], ignore_index=True)
        (final_df
         .drop(columns='category')
         .to_csv(OUTPUTPATH / 'traci' / 'TRACI 3.0.csv', index=False)
         )
    #%% Write to json
    df = lciafmt.get_mapped_method(method)
    df_json = drop_county_data_and_assign_names(df)
    # df_json = df_json.query('Context == "emission/air"')
    save_json(method, df_json,
              regions=regions,
              write_flows=write_flows_to_json,
              )

if __name__ == "__main__":
    main()
    mapped_df = lciafmt.get_mapped_method(method)
