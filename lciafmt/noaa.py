# noaa.py (lciafmt)
# !/usr/bin/env python3
# coding=utf-8
"""
This module contains functions needed to compile LCIA methods from the
Annex to the World Meteorological Organizations Scientific Asssessment of Ozone Depletion 2022
Document Title: ANNEX: Summary of Abundances, Lifetimes, ODPs, REs, GWPs, and GTPs.
Available at: https://csl.noaa.gov/assessments/ozone/2022/downloads/Annex_2022OzoneAssessment.pdf
"""
"""
Key Assumptions: 
     # compounds with ODP or GWP == 0 are excluded from the respective method.
     # Table A-5 footnote GWP/GTP Footnote:
        #"GWP and GTP values that are less then 0.1 are reported as “<<1” in the table. GWP and GTP values that are between 0.1 and 1
        are reported as “<1” in the table."
     # Table A-5 footnote O11 states that values with < symbol are the upper limit of identified values
     # compounds with a GWP and ODP labeled '<x' are set equal to 1*x
     # compounds with a GWP labeled '<<x' are set equal to 0.1*x
     # compounds with a ODP labeled '>' are set equal to 1*x. No guidance was identified to inform selection of a higher number. 
     # compounds with a GWP labeled '~' are set equal to x.

     # The original file contains no context information. All flowables are assigned the context 'Elementary flows/emission/air'. 

"""
import pandas as pd
from lciafmt.util import datapath, log
import lciafmt.df as dfutil



'''
# The Annex file mentioned in the script header was converted to a csv format by the developers and provided to ERG. 
# The csv source file is located in the data folder associated with this package. 
import codecs
df = pd.read_excel(datapath / 'Annex.Formatted.xlsx', sheet_name='Sheet1')
# Write to a CSV file 
with codecs.open(datapath / 'odp_factors.csv', 'w', 'utf-8-sig') as f: #codex includes BOM label in generated csv file to tell Excel how to decode accurately.
    df.to_csv(f, index=False)  # Set index=False to exclude row numbers
'''

def get() -> pd.DataFrame:
    log.info("read ODP factors from file")
    #initialize blank list to record LCIA data using dfutil.records
    records = []
    skippedrows = [['row number', 'ODP', 'GWP100']]  # to examine compounds with multirow entries.
    not_number = [ ] # check for special characters to deal with.

    #order of special characters matters. If '<' is before '<<' it will create separate rows for each factor containing '<<'.
    special_characters = {
        '~': 1,
        '<<': 0.1,
        '<': 1,
        '>': 1
    }
    df = pd.read_csv(datapath / 'odp_factors.csv')
    for index, row in df.iterrows():
        # These cas numbers are being encoded as dates when written to Excel. Don't appear to be an issue within python. 
        # if row['Industrial Designation or Chemical Name'] in ['HCFC-234cb', 'HCFC-241ac', 'HCFC-242ac', 'HCFC-242bc', 'HCFC-243ab']:
        #     print(row['CAS RN'])
        #Check that rows with missing chemical name do not contain valuable information.
        #If you examine the dataframe generated above, you will see that multirow entries (i.e. merged in excel) for a single chemical get parsed to multiple rows in the dataframe.
        #Rows other than the first row do not contain a chemical name and based on visual inspection are not known to contain GWP or ODP data that we are looking to extract.
        #This if test creates a list of blank rows and extracts the potentially useful data is not missed. If Identified, it will be dealt with. 
        if row['Industrial Designation or Chemical Name'] in [None, '']:
            skippedrows.append([index, row['ODP'], row['GWP 100-yr']])
        # Build list in standard format for conversion to a dataframe.
        # check if the ODP factor is a non-zero number. 
        else: 
            if row['ODP'] not in ['', 0, '–', None, 'xxx', '0']:
                if isinstance(row['ODP'], (int, float)):
                    odpCF = row['ODP']
                else:
                    not_number.append(row['ODP'])
                    #strip off special characters and multiply by defined factor for each special character.
                    if any(s in row['ODP'] for s in special_characters.keys()):
                        for item in special_characters:
                            if item in row['ODP']:
                                odpCF = float(row['ODP'].replace(item, ''))*float(special_characters[item])
                                break
                    else:
                        try:
                            odpCF = float(row['ODP'])
                        except ValueError:
                            log.warning(f'Error in {row["Industrial Designation or Chemical Name"]}')
                dfutil.record(records,
                            method='NOAA',
                            indicator='Ozone Depletion Potential', 
                            indicator_unit='kg CFC-11 equivalent',
                            flow=row['Industrial Designation or Chemical Name'],
                            flow_category='air',
                            flow_unit='kg', 
                            cas_number=row['CAS RN'],
                            location='',
                            factor=odpCF)
            # check if the GWP factor is a non-zero number. 
            if row['GWP 100-yr'] not in ['', 0, '–', None, 'xxx', '0']:
                if isinstance(row['GWP 100-yr'], (int, float)):
                    gwpCF = row['GWP 100-yr']
                else:
                    not_number.append(row['GWP 100-yr'])
                    #strip off special characters and multiply by defined factor for each special character.
                    if any(s in row['GWP 100-yr'] for s in special_characters.keys()):
                        for item in special_characters:
                            if item in row['GWP 100-yr']:
                                gwpCF = float(row['GWP 100-yr'].replace(item, ''))*float(special_characters[item])
                                break 
                    else:
                        gwpCF = float(row['GWP 100-yr'])
                dfutil.record(records,
                            method='NOAA',
                            indicator='Climate Change Potential', 
                            indicator_unit='kg CO2 equivalent',
                            flow=row['Industrial Designation or Chemical Name'],
                            flow_category='air',
                            flow_unit='kg', 
                            cas_number=row['CAS RN'],
                            location='',
                            factor=gwpCF)   

    output_df = dfutil.data_frame(records)
    output_df['CAS No'] = output_df['CAS No'].astype(str)
    output_df['Flowable'] = output_df['Flowable'].str.strip()
    output_df = output_df.dropna(subset=['Flowable', 'Characterization Factor'])

    # # Write output dataframe to a CSV file 
    # # Purpose of this file is for visualizing the dataframe and QC.
    # with codecs.open('noaa_records.csv', 'w', 'utf-8-sig') as f: 
    #     output_df.to_csv(f, index=False)  # Set index=False to exclude row numbers

    # # create csv to examine skipped rows
    # skipped_df = pd.DataFrame(skippedrows)
    # with codecs.open('skipped_records.csv', 'w', 'utf-8-sig') as f:
    #     skipped_df.to_csv(f, index=False)  # Set index=False to exclude row numbers

    # # create csv to examine non-numbers
    # number_df = pd.DataFrame(not_number)
    # with codecs.open('not_number.csv', 'w', 'utf-8-sig') as f:
    #     number_df.to_csv(f, index=False)  # Set index=False to exclude row numbers 

    return output_df

if __name__ == "__main__":
    import lciafmt
    method = lciafmt.Method.NOAA
    df = lciafmt.get_method(method)
    mapped_df = lciafmt.map_flows(df, system=method.get_metadata().get('mapping'))
    mapped_df2 = lciafmt.util.collapse_indicators(mapped_df)
    lciafmt.util.store_method(mapped_df2, method)
    lciafmt.util.save_json(method, mapped_df2)
