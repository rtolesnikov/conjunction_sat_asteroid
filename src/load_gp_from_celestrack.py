"""
Author: Juan Luis Cano Rodríguez

Modified by Roman Tolesnikov 2021-02-04


Code to read GP data from Celestrak using the HTTP API and python-sgp4.

Requires some extra dependencies:

  $ pip install httpx sgp4

This is similar to https://gitlab.com/librespacefoundation/python-satellitetle,
but uses the XML API instead and returns a `Satrec` object from sgp4 directly.

"""

import io
import xml.etree.ElementTree as ET

import httpx

from sgp4 import omm
from sgp4.api import Satrec

def _generate_url(catalog_number, international_designator, name, group):
    params = {
        "CATNR": catalog_number,
        "INTDES": international_designator,
        "NAME": name,
        "GROUP": group,
    }
    param_names = [
        param_name
        for param_name, param_value in params.items()
        if param_value is not None
    ]
    if len(param_names) != 1:
        raise ValueError(
            "Specify exactly one of catalog_number, international_designator, or name"
        )
    param_name = param_names[0]
    param_value = params[param_name]
    url = (
        "https://celestrak.org/NORAD/elements/gp.php?"
        f"{param_name}={param_value}"
        "&FORMAT=XML"
    )
    return url


def _segments_from_query(url):
    response = httpx.get(url)
    response.raise_for_status()

    if response.text == "No GP data found":
        raise ValueError(
            f"Query '{url}' did not return any results, try a different one"
        )
    #tree = ET.parse(io.StringIO(response.text))
    #root = tree.getroot()
    yield from omm.parse_xml(io.StringIO(response.text))

def load_gp_from_celestrak(
    *, catalog_number=None, international_designator=None, name=None, group=None, name_map
):
    """Load general perturbations orbital data from Celestrak.

    Returns
    -------
    Satrec
        Orbital data from specified object.

    Notes
    -----
    This uses the OMM XML format from Celestrak as described in [1]_.

    References
    ----------
    .. [1] Kelso, T.S. "A New Way to Obtain GP Data (aka TLEs)"
       https://celestrak.org/NORAD/documentation/gp-data-formats.php

    """
    # Assemble query, raise an error if malformed
    url = _generate_url(catalog_number, international_designator, name, group)

    #global map_norad_to_name
    # Make API call, raise an error if data is malformed
    for segment in _segments_from_query(url):
        # print(segment)
        # Initialize and return Satrec object
        sat = Satrec()
        omm.initialize(sat, segment)
        name_map[sat.satnum] = segment['OBJECT_NAME'].strip()

        yield sat
