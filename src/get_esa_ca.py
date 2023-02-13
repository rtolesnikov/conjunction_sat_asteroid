#!/usr/bin/env python
# coding: utf-8

# In[39]:


import requests
import re

_esa_url_base = 'https://neo.ssa.esa.int/'

_url_map = {'upcoming' : _esa_url_base + 'PSDB-portlet/download?file=esa_upcoming_close_app',
            'recent':    _esa_url_base + 'PSDB-portlet/download?file=esa_recent_close_app',
            'impacted' : _esa_url_base + 'PSDB-portlet/download?file=past_impactors_list'}

def get_esa_data(data_type, ca_threshold):
    
    if data_type not in ('upcoming', 'recent', 'impacted'):
        raise ValueError("Invalid data type request: {}".format(data_type))

    r = requests.get(_url_map[data_type])
    r.raise_for_status()

    ca_list = []
    line_no = 0
    if data_type in ('upcoming', 'recent'):
        for line in r.iter_lines():
            line_no += 1
            line = line.decode(r.encoding)
            ca_tuple = line.split('|')
            num_desig = ca_tuple[0][0:10].strip()
            if line_no > 4:
                ca_miss_km = int(ca_tuple[2].strip())
                if ca_miss_km < ca_threshold:
                    ca_date = ca_tuple[1].strip()
                    ca_list.append((num_desig, ca_date, ca_miss_km))
    elif data_type == 'impacted':
        for line in r.iter_lines():
            line_no += 1
            line = line.decode(r.encoding)
            ca_tuple = line.split('|')
            num_desig = ca_tuple[0].strip()
            if line_no > 2:
                ca_miss_km = 0
                ca_date = ca_tuple[2].strip()
                ca_list.append((num_desig, ca_date, ca_miss_km))
    return ca_list

def normalize_esa_name(esa_name):
    '''Given ESA name without a space, return Horizons name (with space)
       e.g. 2023BU -> 2023 BU
            
    '''
    r = re.compile("(\d{4})([a-zA-Z]{2}.*)")
    try:
        g = r.match(esa_name)
    except:
        return esa_name
    if g is not None:
        return g.group(1) + ' ' + g.group(2)
    else:
        return esa_name
 

if __name__ == '__main__':
    Rgeo = 42_164 * 1.1 # km

    assert normalize_esa_name('2023BU') == '2023 BU'
    assert normalize_esa_name('2023BU23') == '2023 BU23'
    assert normalize_esa_name('1') == '1'
    assert normalize_esa_name('12') == '12'
    assert normalize_esa_name('123') == '123'
    assert normalize_esa_name('12345') == '12345'
    assert normalize_esa_name('123456') == '123456'
    assert normalize_esa_name('1234567') == '1234567'
    
    try:
        t = get_esa_data('test error',Rgeo)
    except ValueError as e:
        assert str(e) == "Invalid data type request: {}".format('test error')
    else:
        raise AssertionError("Failed exception check")
    print(get_esa_data('upcoming',Rgeo))
    print(get_esa_data('recent',Rgeo))
    print(get_esa_data('impacted',Rgeo))


# In[ ]:




