"""Test generation of all available methods including as json."""

import pytest
import lciafmt
from lciafmt.util import store_method, MODULEPATH

skip_list = ['ImpactWorld', # requires pyodbc
             'TRACI2_2', # memory error
             'TRACI3_0', # files not fully available
             'USETOX', # files not available
             ]

@pytest.mark.generate_methods
def test_generate_methods():
    error_list = []
    for method_id in lciafmt.supported_methods():
        m = lciafmt.util.check_as_class(method_id.get('id'))
        if m.name in skip_list: continue
        df = None
        df = lciafmt.get_mapped_method(m, download_from_remote=False)
        lciafmt.util.compare_to_remote(df, m)
        if df is None:
            error_list.append(m.name)
            continue
        lciafmt.util.save_json(m, df, df['Method'].unique()[0])
        
    assert not error_list


def test_url_access():
    import lciafmt.iw as impactworld
    f = lciafmt.recipe._get_file(lciafmt.Method.RECIPE_2016.get_metadata())
    f = lciafmt.traci._get_file(lciafmt.Method.TRACI.get_metadata())
    f = impactworld._get_file(lciafmt.Method.ImpactWorld.get_metadata())

def test_endpoint_method():
    method = lciafmt.generate_endpoints('Weidema_valuation',
                                        name='Weidema Valuation',
                                        matching_fields=['Indicator unit'],
                                        download_from_remote=True)
    store_method(method, method_id=None)
    assert method is not None


def test_method_write_json():
    # Test TRACI2.1 Acidification
    method_id = lciafmt.Method.TRACI
    method = lciafmt.get_mapped_method(method_id = method_id,
                                       indicators=['Acidification'],
                                       download_from_remote=True)
    lciafmt.util.save_json(method_id = method_id,
                           name = 'test_TRACI',
                           mapped_data = method,
                           write_flows=True,
                           preferred_only=True)
    # Test FEDEFL Inventory
    method_id = lciafmt.Method.FEDEFL_INV
    method = lciafmt.get_mapped_method(method_id = method_id,
                                       download_from_remote=True)
    lciafmt.util.save_json(method_id = method_id,
                           mapped_data = method,
                           name = 'test_FEDEFL',
                           write_flows=True)

    # # Test TRACI2.2 Eutrophication
    # method_id = lciafmt.Method.TRACI2_2
    # method = lciafmt.get_mapped_method(method_id = method_id,
    #                                    indicators=['Eutrophication (Marine)'],
    #                                    download_from_remote=True)
    # method = esupy.location.assign_state_names(method)
    # ## ^ requires flowsa
    # method = method.query('~Location.str.isnumeric()').reset_index(drop=True)
    # lciafmt.util.save_json(method_id = method_id,
    #                        name = 'test_Eutro',
    #                        mapped_data = method,
    #                        write_flows=False)


def test_compilation_method():
    df = lciafmt.generate_lcia_compilation('compilation.yaml',
                                           filepath=MODULEPATH.parent / 'tests')
    name = df['Method'][0]
    lciafmt.util.store_method(df, method_id=None, name=name)
    lciafmt.util.save_json(method_id=None, mapped_data=df, name=name)


if __name__ == "__main__":
    # test_generate_methods()
    # test_method_write_json()
    # test_url_access()
    test_compilation_method()
