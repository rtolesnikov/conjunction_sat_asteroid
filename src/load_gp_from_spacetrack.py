"""
Author: Roman Tolesnikov

Read General Perturbation data from space-track.org using python spacetrack module

Requires some extra dependencies:

  $ pip install spcatrack

This is similar to https://gitlab.com/librespacefoundation/python-satellitetle,
but uses the XML API instead and returns a `Satrec` object from sgp4 directly.

"""
import sys, os, io

import configparser

import spacetrack.operators as op
from spacetrack import SpaceTrackClient

from sgp4 import omm
from sgp4.api import Satrec

def _segments_from_space_track():
    st = SpaceTrackClient(identity=configUsr, password=configPwd)
    data = st.gp(epoch='>now-30', format='xml')
    print("Got {} bytes of data".format(len(data)))
    with open('omm_latest.xml', 'w') as fp:
        fp.write(data)
    yield from omm.parse_xml(io.StringIO(data))

def _segments_from_local():
    with open('st_omm.xml', 'r') as fp:
        yield from omm.parse_xml(fp)

    
def load_gp_from_spacetrack(name_map):
    for segment in _segments_from_space_track():
        # print(segment)
        # Initialize and return Satrec object
        sat = Satrec()
        omm.initialize(sat, segment)
        name_map[sat.satnum] = segment['OBJECT_NAME'].strip()

        yield sat

try:
    # See if environment contains credentials. This is the case for github deployments
    configUsr = os.environ['SPACETRACK_USER']
    configPwd = os.environ['SPACETRACK_PASSWD']
    print("Got credentials from environment")
except:
    try:
        # See if the credentials file exists. This is the case for local repositories
        config = configparser.ConfigParser()
        config.read("space-track.ini")
        configUsr = config.get("configuration","username")
        configPwd = config.get("configuration","password")
    except:
        print("Unable to obtain space-track.org credentials")
        sys.exit(1)
       
if __name__ == '__main__':
    print(configUsr, configPwd)
    sat_list = []
    map_satnum_to_name = {}
    sat_list.extend(list(load_gp_from_spacetrack(name_map = map_satnum_to_name)))
    print('Loaded {} from space-track.org'.format(len(sat_list)))
