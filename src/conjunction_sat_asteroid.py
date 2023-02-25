#!/usr/bin/env python
# coding: utf-8

import io, os, re, glob, json
from sys import stdout

from itertools import islice
from pprint import pprint
from warnings import warn
import time, datetime

import numpy as np
import matplotlib.pyplot as plt

from astropy import units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import CartesianRepresentation, CartesianDifferential
from astropy.coordinates import TEME, GCRS

from poliastro.ephem import Ephem
from poliastro.frames import Planes
from poliastro.util import norm, time_range
from poliastro.bodies import Earth
from poliastro.plotting import OrbitPlotter3D

from sgp4.api import Satrec, SatrecArray

from astroquery.jplhorizons import Horizons

import get_esa_ca

# Radius of geosynchronous orbit + 10%
Rgeo = 42_164 * 1.1 # km,  From https://en.wikipedia.org/wiki/Geosynchronous_orbit
# Directory where output docs are stored
base_dir = '../docs'

def print_sat(sat, name):
    """Prints Satrec object in convenient form."""
    print(json.dumps(exporter.export_omm(sat, name), indent=2))

def from_horizons_rt(
        cls,
        name,
        epochs,
        *,
        attractor=None,
        plane=Planes.EARTH_EQUATOR,
        id_type=None,
    ):
        """
        This code is adopted by Roman Tolesnikov from the poliastro routine in Ephem class.
        It uses a different method to invoke Horizons taht does not pass the list of jd and this enables queries limited only by Horizons.
        
        Adopted from: https://github.com/poliastro/poliastro/blob/main/src/poliastro/ephem.py
        
        Return `Ephem` for an object using JPLHorizons module of Astroquery.
        Parameters
        ----------
        name : str
            Name of the body to query for.
        epochs : ~astropy.time.Time
            Epochs to sample the body positions.
        attractor : ~poliastro.bodies.SolarSystemPlanet, optional
            Body to use as central location,
            if not given the Solar System Barycenter will be used.
        plane : ~poliastro.frames.Planes, optional
            Fundamental plane of the frame, default to Earth Equator.
        id_type : NoneType or str, optional
            Use "smallbody" for Asteroids and Comets and None (default) to first
            search for Planets and Satellites.
        """
        if epochs.isscalar:
            epochs = epochs.reshape(1)

        refplanes_dict = {
            Planes.EARTH_EQUATOR: "earth",
            Planes.EARTH_ECLIPTIC: "ecliptic",
        }
        refplane = refplanes_dict[plane]

        if attractor is not None:
            bodies_dict = {
                "sun": 10,
                "mercury": 199,
                "venus": 299,
                "earth": 399,
                "mars": 499,
                "jupiter": 599,
                "saturn": 699,
                "uranus": 799,
                "neptune": 899,
            }
            location = f"500@{bodies_dict[attractor.name.lower()]}"
        else:
            location = "@ssb"

        # This uses unit-less method to invoke Horizons, per https://ssd-api.jpl.nasa.gov/doc/horizons.html#stepping
        # It's the only way to have resolutions < 1 minute and not exceed URL length limits for longer requets. The time step still has to be > 0.5 sec (Not enforced in this code)
                        
        obj = Horizons(
            id=name,
            location=location,
            epochs={'start': epochs[0].isot,
                    'stop' : epochs[-1].isot,
                    'step' : str(len(epochs)-1)},
            id_type=id_type
        ).vectors(refplane=refplane)
        

        x = obj["x"]
        y = obj["y"]
        z = obj["z"]
        d_x = obj["vx"]
        d_y = obj["vy"]
        d_z = obj["vz"]

        coordinates = CartesianRepresentation(
            x, y, z, differentials=CartesianDifferential(d_x, d_y, d_z)
        )
        return cls(coordinates, epochs, plane), obj

def process_asteroid(target_name, TCA, time_position = 'mid'):
    '''
    Target Name: minor body designation in the form '2023 BU'. Space is required. Numbered objects are accepted as well. MPC packed designators are not supported
    TCA: Time of Close Approach: astropy.Time() object that defines the time of close approach. Designed to be obtained from a pre-computed ephemeris, like that from ESA CNEOS
    '''
    
    search_range = TimeDelta(2 *u.day)
    if time_position == 'mid':
        # Use this for a fly-by close approach
        #time_start = '2023-01-26T00:00:00'
        #time_end   = '2023-01-28T00:00:00'

        time_start = TCA - search_range
        time_end   = TCA + search_range
    elif time_position == 'end':
        # use this for an impacted asteroid which does not have a closest appraoch
        time_start = TCA - 2 * search_range
        time_end   = TCA
    else:
        raise ValueError("time_position can be either 'mid' (default) or 'end'")
            
    time_step = 1 << u.minute
    fine_time_mult = 10
    time_step_coarse = time_step*fine_time_mult
    start_epoch = Time(time_start, scale = 'utc')
    end_epoch   = Time(time_end,   scale = 'utc')
    periods_coarse = int((end_epoch - start_epoch)/time_step_coarse)

    epochs_coarse = time_range(start_epoch, periods = periods_coarse, spacing = time_step_coarse)

    # Add semicolon to help Horizons figure out that this is a minor body request
    target, target_raw = from_horizons_rt(Ephem, target_name + ';', epochs_coarse, attractor = Earth)
    # ICA = Index of Close Approach
    ICA = np.argmin(target_raw['range'])
    earth_miss_distance = target_raw[ICA]['range']
    print("Coarse close approach:")
    print(target_raw[ICA]['datetime_str'],(target_raw[ICA]['range'] * u.au).to(u.km))

    # Find the index of the closest approach

    # Create  mask that includes the apraoches closer than GEO disposal orbit + 100 km + 10%
    idx_CA = target_raw['range'] < (Rgeo * u.km + 300 * u.km) * 1.10

    epochs_fine = time_range(target_raw[idx_CA]['datetime_jd'][0],
                             periods = len(target_raw[idx_CA]['datetime_jd'])*fine_time_mult,
                             spacing = time_step,
                             format = 'jd')

    # Get state vectors and ephemeris at finer resolution but likely of a shorter time span
    try:
        target_fine, target_raw_fine = from_horizons_rt(Ephem, target_name, epochs_fine, attractor = Earth)
    except ValueError as e:
        # catch errors of this kind, where ephemeris is slightly shorter prior to impact
        # Horizons Error: No ephemeris for target "(2019 MO)" after A.D. 2019-JUN-22 21:27:09.1844 TD
        # Round this time to the previous minute in UTC and use as the new end time, and re-compute
        r = re.compile("No ephemeris for target (.*) after A.D. (.*\d\d:\d\d):\d\d\.\d* TD$")
        m = r.search(str(e))
        if m is not None:
            start_epoch = Time(target_raw[idx_CA]['datetime_jd'][0], scale='utc', format='jd')
            end_epoch = Time.strptime(m.groups()[1], '%Y-%b-%d %H:%M', scale='tdb').utc
            periods_fine = int((end_epoch - start_epoch)/time_step)
            epochs_fine = time_range(start_epoch, periods = periods_fine, spacing = time_step)
            target_fine, target_raw_fine = from_horizons_rt(Ephem, target_name, epochs_fine, attractor = Earth)
        else:
            raise e

    #Refine ICA using fine-grained ephemeris
    ICA_fine = np.argmin(target_raw_fine['range'])
    print("Fine close approach:")
    print(target_raw_fine[ICA_fine]['datetime_str'],(target_raw_fine[ICA_fine]['range'] * u.au).to(u.km))

    # If the close approach is current (within 3 days), download current GP elemet from celestrack
    if abs(Time(target_raw_fine[ICA_fine]['datetime_jd'], format='jd') - Time.now()) < 3* u.day :
        import load_gp_from_spacetrack

        sat_list = []
        map_satnum_to_name = {}
        sat_list.extend(list(load_gp_from_spacetrack.load_gp_from_spacetrack(name_map = map_satnum_to_name)))
        print('Loaded from space-track.org')
    else:
        # If the approach is in the past, get the archival TLE
        import load_tle_from_archive

        # add one day to the TCA to get the elests tha thave been fit using obervation after the CA
        map_satnum_to_name, sat_list = load_tle_from_archive.load_gp_from_archive(
                      (Time(target_raw_fine[ICA_fine]['datetime_jd'], format='jd') + 1*u.day).to_datetime())
        print('Loaded from archive')
    print("{} element sets downloaded".format(len(sat_list)))
    # Limit list to those sats whose apogee is 10% lower than the close apprach distance

    apogee_threshold = target_raw_fine[ICA_fine]['range'] * 0.9 * u.au

    sat_list = [i for i in sat_list if (i.alta + 1) * i.radiusearthkm * u.km > apogee_threshold]

    print("{} element sets remaining after apogee vs miss distance filtering".format(len(sat_list)))

    start_time = time.time()
    # Generate ephemeris for the sattelites using accelelrated array
    temp = SatrecArray(sat_list)
    #a = SatrecArray([sat_list[0], sat_list[1]])

    sat_ephem_list2 = ephem_from_gp(temp, epochs_fine)
    end_time = time.time()

    print("Propagated {} elsets for {} epochs in {:.2f} sec: {:.3f} ms/el-epoch".format(
          len(sat_list), len(epochs_fine), end_time - start_time, (end_time - start_time)*1000/(len(sat_list)*len(epochs_fine))))


    # calculate Range between each sat and the asteroid target
    min_range_list = []
    for i_ephem, i_sat in zip(sat_ephem_list2, sat_list):
        t = norm(i_ephem.rv()[0] - target_fine.rv()[0], axis = 1)
        min_idx = np.argmin(t)
        min_range_list.append((i_sat, t[min_idx], epochs_fine[min_idx].iso))

    # Sort by range
    min_range_list.sort(key=lambda a: a[1])
    return (min_range_list, map_satnum_to_name, sat_ephem_list2, sat_list, epochs_fine, target_fine)
    
def make_text_output(min_range_list,map_satnum_to_name):        
    # Report closest misses
    header_active = "{:>2s} {:>9s} {:10s} {:25s} {}  {}".format("No", "NORAD", "INTER", "Satellite Name", "Miss (km)", "Time of Closest Approach (UTC)")
    header_debris = "{:>2s} {:>9s} {:10s} {:25s} {}  {}".format("No", "NORAD", "INTER", "Satellite Name (debris)", "Miss (km)", "Time of Closest Approach (UTC)")
    deb_cnt = 0
    active_cnt = 0
    deb_list = []
    active_list = []
    for i_sat, miss_dist,TCA in min_range_list:
        name = map_satnum_to_name[i_sat.satnum]
        if (name.endswith('DEB') or name.endswith('AKM') or ' DEB ' in name or 'R/B' in name or 'PKM' in name or name.startswith('WESTFORD NEEDLES') or name == 'TBA - TO BE ASSIGNED'):
            deb_cnt += 1
            if deb_cnt <= 20:
                deb_list.append("{:2d} {:9d} {:10s} {:25s} {:9.0f}  {}".format(deb_cnt, i_sat.satnum, i_sat.intldesg, name, miss_dist.value, TCA))
        else:
            active_cnt += 1
            if active_cnt <= 20:
                active_list.append("{:2d} {:9d} {:10s} {:25s} {:9.0f}  {}".format(active_cnt, i_sat.satnum, i_sat.intldesg, name, miss_dist.value, TCA))
        if deb_cnt > 20 and active_cnt > 20:
            break

    print(header_active)
    print('\n'.join(active_list))

    print("\n" + header_debris)
    print('\n'.join(deb_list))
        
def make_html_output(min_range_list,map_satnum_to_name,target_name,filename):
    # Report closest misses
    html_head = '<html>\n<head>\n<title>{} conjunctions</title>\n'.format(target_name)
    html_head +='  <link rel="stylesheet" href="styles.css">\n</head>'

    table_tag_active = "<table>\n<caption> Close Approaches with non-debris for {} </caption>\n".format(target_name)
    table_tag_debris = "<table>\n<caption> Close Approaches with debris for {} </caption>\n".format(target_name)
    header_row = "<tr> <th>{}</th> <th>{}</th> <th>{}</th> <th>{}</th> <th>{}</th>  <th>{}</th> </tr>\n".format("No", "NORAD", "INTER", "Satellite Name", "Miss (km)", "Time of Closest Approach (UTC)")
    deb_cnt = 0
    active_cnt = 0
    deb_list = []
    active_list = []
    for i_sat, miss_dist,TCA in min_range_list:
        name = map_satnum_to_name[i_sat.satnum]
        if (name.endswith('DEB') or name.endswith('AKM') or ' DEB ' in name or 'R/B' in name or 'PKM' in name or name.startswith('WESTFORD NEEDLES') or name == 'TBA - TO BE ASSIGNED'):
            deb_cnt += 1
            if deb_cnt <= 20:
                deb_list.append("<tr> <td>{:d}</td> <td>{:d}</td> <td>{}</td> <td>{}</td> <td>{:.0f}</td> <td>{}</td> </tr>".format(deb_cnt, i_sat.satnum, i_sat.intldesg, name, miss_dist.value, TCA))
        else:
            active_cnt += 1
            if active_cnt <= 20:
                active_list.append("<tr> <td>{:d}</td> <td>{:d}</td> <td>{}</td> <td>{}</td> <td>{:.0f}</td> <td>{}</td> </tr>".format(active_cnt, i_sat.satnum, i_sat.intldesg, name, miss_dist.value, TCA))
        if deb_cnt > 20 and active_cnt > 20:
            break

    with open(filename, "w") as f:
        f.write(html_head)
        f.write(table_tag_active)
        f.write(header_row)
        f.write('\n'.join(active_list))
        f.write('\n</table>\n')

        f.write(table_tag_debris)
        f.write(header_row)
        f.write('\n'.join(deb_list))
        f.write('\n</table>\n')
        f.write('<img src="{}.png"'.format(target_name))
        f.write('</html>\n')

def make_json_output(min_range_list,map_satnum_to_name,target_name,filename, flyby_type):
    t=[]
    t.append(target_name) # asteroid name
    t.append(map_satnum_to_name[min_range_list[0][0].satnum]) # CA sat name
    t.append('{:.0f}'.format(min_range_list[0][1].value)) # CA sat miss distance (km)
    t.append(min_range_list[0][2][:16]) # CA sat Time of close aproach
    t.append(flyby_type)
    
    with open(filename,"w") as f:
        f.write(json.dumps(t))

def make_index(base_dir):
    html_head = '<html>\n<head>\n<title>Asteroid-Satellite Conjunction Assessment</title>\n'
    html_head +='  <link rel="stylesheet" href="styles.css">\n</head>'

    ca_list = []
    for j in glob.glob(base_dir + "/*.json"):
        with open(j, 'r') as jf:
            ca_record = json.loads(jf.read())
            # Add hyperlink
            ca_record[0] = '<a href="{}.html">'.format(ca_record[0]) + ca_record[0] + '</a>'
            ca_list.append(ca_record)
    ca_list.sort(key = lambda a: a[3], reverse = True) # sort by CA date
    
    with open(base_dir + "/index.html",'w') as idxf:
        idxf.write(html_head)
        idxf.write("<body>\n<table>\n")
        idxf.write("<tr> <th>Minor Body</th> <th>Satellite</th> <th>Miss (km)</th> <th>Time of Closest Approach (UTC)</th> <th> Flyby Type </th> </tr>\n")
        for ca in ca_list:
            row = ''.join(['<td>{}</td>'.format(i) for i in ca])
            row = '<tr>' + row + '</tr>\n'
            idxf.write(row)
        idxf.write("</table>\n")
        idxf.write("<div>Last Updated: {} UTC</div>".format(datetime.datetime.utcnow().isoformat()))
        idxf.write("</body>\n")
        idxf.write("</html>\n")
            
def make_plots(target_name, min_range_list, sat_ephem_list2, sat_list, epochs_fine, target_fine, filename):   
    # Plot separations between each sat and the target
    fig, ax = plt.subplots()

    # Label 5 sats that have closest misses
    sat_to_label = [i[0].satnum for i in islice(min_range_list,5)]

    for i_ephem, i_sat in zip(sat_ephem_list2, sat_list):
        if i_sat.satnum in sat_to_label:
            ax.plot(norm(i_ephem.rv()[0] - target_fine.rv()[0], axis = 1), label = map_satnum_to_name[i_sat.satnum])
        else:
            ax.plot(norm(i_ephem.rv()[0] - target_fine.rv()[0], axis = 1))
    # plot erth radius
    #ax.plot([0, len(epochs_fine)],[sat_list[0].radiusearthkm,sat_list[0].radiusearthkm], '--', label = 'Re', )

    # plot asteroid distance from earth center:
    #ax.plot(target_raw_fine['range'] << u.km, label = target_name + " range from Earth center" )

    ax.set_yscale('log')
    ax.set_xlabel('Time [UTC]')
    ax.set_ylabel('Miss Distance [km]')
    ax.set_title("Miss distance sat - {}".format(target_name))
    ax.set_xticks(range(0,len(epochs_fine),10),
                 labels = [epochs_fine.iso[i][0:16] for i in range(0,len(epochs_fine),10)], rotation = 90, minor = False)
    ax.legend(bbox_to_anchor=(1.05, 1),loc='upper left',)
    plt.savefig(filename, format='png', transparent = True, bbox_inches = 'tight')  

    if 0:
        plotter = OrbitPlotter3D()
        plotter.set_attractor(Earth)

        for i_ephem, i_sat in zip(sat_ephem_list2, sat_list):
            if i_sat.satnum in sat_to_label:
                plotter.plot_ephem(
                    i_ephem, color="#666", label=map_satnum_to_name[i_sat.satnum], trail=True
                )

        plotter.plot_ephem(target_fine, color = "#345", label = '2023 BU', trail = True)
        plotter.show()

def ephem_from_gp(sat, times):
    if isinstance(sat,SatrecArray):
        errors, rs, vs = sat.sgp4(times.jd1, times.jd2)
    else:
        errors, rs, vs = sat.sgp4_array(times.jd1, times.jd2)
    if not (errors == 0).all():
        warn(
            "{} objects could not be propagated, "
            "proceeding with the rest:".format(np.count_nonzero(errors)),
            stacklevel=2,
        )
        # np.savetxt('errors.csv', errors, delimiter=',',fmt='%1d')
        
        for i in range(errors.shape[0]):
            if not( errors[i] == 0).all():
                # this porpagation has an error. Print some details:
                print ("Error idx = ", i)
                
    cart_teme = CartesianRepresentation(
        rs << u.km,
        xyz_axis=-1,
        differentials=CartesianDifferential(
            vs << (u.km / u.s),
            xyz_axis=-1,
        ),
    )
    cart_gcrs = (
        TEME(cart_teme, obstime=times)
        .transform_to(GCRS(obstime=times))
        .cartesian
    )
    if isinstance(sat,SatrecArray):
        return [Ephem(t, times, plane=Planes.EARTH_EQUATOR) for t in cart_gcrs]
    else:
        return Ephem(cart_gcrs, times, plane=Planes.EARTH_EQUATOR)

try:
    for data_type in ('upcoming', 'recent', 'impacted'):
        t = get_esa_ca.get_esa_data(data_type, Rgeo)
        for (name, TCA, miss_dist) in t:
            try:
                norm_name = get_esa_ca.normalize_esa_name(name)
                out_fn = base_dir + '/{}.html'.format(norm_name)
                if os.path.exists(out_fn) and data_type != 'upcoming':
                    # future close approaches are always recamputed
                    print("Skipped previously computed " + norm_name)
                elif data_type == 'upcoming' and Time(TCA) - Time.now() > TimeDelta(7 * u.day):
                    print("Skipped flyby that's too far in the future " + norm_name)
                else:
                    print("Processing " + norm_name)
                    if data_type == 'impacted':
                        time_position = 'end'
                    else:
                        time_position = 'mid'
                    (min_range_list, map_satnum_to_name, sat_ephem_list2, sat_list, epochs_fine, target_fine) = process_asteroid(norm_name, Time(TCA), time_position = time_position)
                    make_text_output(min_range_list, map_satnum_to_name)
                    make_html_output(min_range_list, map_satnum_to_name,norm_name,out_fn)
                    make_json_output(min_range_list,map_satnum_to_name,norm_name,base_dir + '/{}.json'.format(norm_name), data_type)
                    make_plots(norm_name, min_range_list, sat_ephem_list2, sat_list, epochs_fine, target_fine,  base_dir + '/{}.png'.format(norm_name))
                    print("Completed " + norm_name)
            except ValueError as e:
                print(e)
finally:
    make_index(base_dir)
    