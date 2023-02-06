#!/usr/bin/env python
# coding: utf-8

# In[1]:


# From https://github.com/poliastro/poliastro/blob/main/contrib/satgpio.py
"""
Author: Roman Tolesnikov

Read 3LE data from archives.
These archives are previously saved by TLERetriever from celestrack.org

  $ pip install sgp4

Usage:
    (name_map, sat_list) = load_gp_from_archive(epoch, [tol])
Input:
    epoch datetiem object with the desired epoch of the 3le set
    tol: optional, tolerace. If the archive for the date directly corrresponding to epoch is not found, search around that day for tol days
Outputs:
    Tuple of (name_map, sat_list)
    name_map: a dict mapping sattlite number to its name
    sat_list: a list of sgp4 SatRec objects

Notes:
    Location of the archive is in the _base_dir_tle_archive strgin, encoded as the template for string substitution
"""

import os, datetime, glob

from itertools import chain
import zipfile

from sgp4.api import Satrec


# In[2]:


_base_dir_tle_archive = "X:\\files\\roman\\My TLEs"
_tle_template = _base_dir_tle_archive + "\\{year:04d}\\Full Catalog\\Full Catalog-{year:04d}{month:02d}{day:02d}T*.zip"

def _get_archive_path(epoch, tol=4):
    '''Return the location of the historical 3le zip file from the archive
    '''
    # Get sequence in the form of : [0, -1, 1, -2, 2, -3, 3, -4, 4, -5]
    for i in chain.from_iterable(zip(range(tol+1),range(-1,-tol-1,-1))):
        target_date = epoch + datetime.timedelta(days = i)
        path = _tle_template.format(**{'year':  target_date.year, 'month': target_date.month, 'day':   target_date.day})
        for file in glob.glob(path):
            if os.path.isfile(file):
                return file
  
    raise ValueError(f"Cannot find archival file within {tol} days of {epoch.isoformat()} using template {_tle_template}")


# In[4]:


def load_gp_from_archive(epoch):
    map_norad_to_name = {}
    sat_list = []
    with zipfile.ZipFile(_get_archive_path(epoch)) as za:
        with za.open(za.namelist()[0]) as tle_file:
            for line in tle_file:
                line_trimmed = line.decode('utf-8').strip()
                if line_trimmed[0] == '0':
                    name = line_trimmed[2:]
                elif line_trimmed[0] == '1':
                    t1 = line_trimmed
                elif line_trimmed[0] == '2':
                    t2 = line_trimmed
                    sat = Satrec.twoline2rv(t1, t2)
                    map_norad_to_name[sat.satnum] = name
                    sat_list.append(sat)
    return (map_norad_to_name, sat_list)


# In[13]:


if __name__ == '__main__':
        t = _get_archive_path(datetime.date.fromisoformat('2023-01-02'))
        print(t)
        assert t == _base_dir_tle_archive + '\\2023\\Full Catalog\\Full Catalog-20230102T0700.zip'

        t = _get_archive_path(datetime.date.fromisoformat('2020-11-13'))
        print(t)
        assert t == _base_dir_tle_archive + '\\2020\\Full Catalog\\Full Catalog-20201113T1200.zip'

        # Only passes if tolerance band is increased
        try:
            t = _get_archive_path(datetime.date.fromisoformat('2019-10-31'))
        except ValueError as msg:
            t = "Cannot find archival file within 4 days of 2019-10-31 using template " + _base_dir_tle_archive + r'\{year:04d}\Full Catalog\Full Catalog-{year:04d}{month:02d}{day:02d}T*.zip'
            assert str(msg) == t
        else:
            raise AssertionError("Expected value exception")

        t = _get_archive_path(datetime.date.fromisoformat('2019-10-31'), tol=6)
        print(t)
        assert t == _base_dir_tle_archive + '\\2019\\Full Catalog\\Full Catalog-20191104T0700.zip'
        
        e = datetime.date.fromisoformat('2023-01-29')
        map_norad_to_name, sat_list = load_gp_from_archive(e)
        assert len(sat_list) == 24474
        print("PASS!")

# In[ ]:




