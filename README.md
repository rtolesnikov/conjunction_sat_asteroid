# conjunction_sat_asterroid
Analyse conjunctions between asteroids during close flyby and artificial earth satellites

## Prerequisites:
- pip3 install httpx sgp4 astropy numpy matplotlib poliastro

## Notes
- src/conjunction_sat_asteroid.ipynb: Jupiter notebook is currently setup to analyse 2023 BU close flyby on 2023-01-27. The initial parameters of the flyby are setup at the top.
- To analyse historical flybys, the code is relying on a private TLE archive.

## TODO
- load historical element sets from space-track.org.

## Algorithm
- Use JPL Horizons to obtain state vectors around the closest approach using coarse time step. This time is set manually.
- Limit the time span to when the asteroid is within the GEO disposal orbit.
- Use fine time step to refine the ephemeris.
- Load complete element set from the archive that represents the catalog one day after the flyby close approach
- Remove those satellites whose apogee is less than the closest approach. This reduces object count from ~24k to ~4.5k
- Propagate each satellite for the duration of the flyby
- Determine the closest range, report 20 closest active and debris objects (separately), and plot

# Output for 2023 BU Flyby
```
No     NORAD INTER      Satellite Name            Miss (km)  Time of Closest Approach (UTC)
 1     16993 86075A     COSMOS 1783                     757  2023-01-27 00:44:00.000
 2       829 64038A     ELEKTRON 3                      791  2023-01-27 00:50:00.000
 3      2610 66111A     OV1-9                          1162  2023-01-27 00:27:00.000
 4     13011 81122B     CAT 4                          1309  2023-01-27 01:58:00.000
 5     32708 08011A     AMC-14                         1539  2023-01-26 22:21:00.000
 6     16103 85088A     COSMOS 1687                    1835  2023-01-27 00:12:00.000
 7     38774 12050A     BEIDOU 14                      2119  2023-01-26 23:16:00.000
 8     28114 03056C     COSMOS 2403 (GLONASS)          2329  2023-01-26 23:22:00.000
 9     53105 22080A     LARES-2                        3003  2023-01-27 00:37:00.000
10     38745 12044B     EXPRESS MD2                    3190  2023-01-27 00:20:00.000
11     44344 19036F     DSX                            3278  2023-01-26 23:47:00.000
12     44115 19020D     O3B FM18                       3323  2023-01-26 23:53:00.000
13       271 62010A     MIDAS 5 (STRONGBACK)           3359  2023-01-27 00:46:00.000
14       340 62029A     TELSTAR 1                      3423  2023-01-27 00:39:00.000
15     28113 03056B     COSMOS 2402 (GLONASS)          3742  2023-01-27 01:32:00.000
16      1002 65008C     LES 1                          3816  2023-01-27 00:46:00.000
17     39188 13031A     O3B FM5                        3873  2023-01-27 00:00:00.000
18     43058 17079D     GALILEO 22 (2C8)               3970  2023-01-27 01:55:00.000
19     20959 90103A     NAVSTAR 22 (USA 66)            3971  2023-01-26 23:07:00.000
20     40081 14038C     O3B FM6                        4039  2023-01-27 00:00:00.000

No     NORAD INTER      Satellite Name (debris)   Miss (km)  Time of Closest Approach (UTC)
 1     38549 68014C     OGO 5 DEB                       458  2023-01-27 00:36:00.000
 2     47332 11037NP    FREGAT DEB                      633  2023-01-27 00:21:00.000
 3     36959 06006CR    BREEZE-M DEB                    681  2023-01-27 00:04:00.000
 4     34229 06006AU    BREEZE-M DEB                    742  2023-01-27 00:35:00.000
 5     33537 88081M     ARIANE 3 DEB                    796  2023-01-26 23:48:00.000
 6      8546 75123D     SL-12 R/B(AUX MOTOR)            914  2023-01-27 00:54:00.000
 7     15266 84095H     SL-12 R/B(AUX MOTOR)            934  2023-01-27 00:33:00.000
 8     47330 11037NM    FREGAT DEB                     1015  2023-01-27 00:37:00.000
 9     46015 11037HS    FREGAT DEB                     1102  2023-01-27 00:37:00.000
10     45823 11037BH    FREGAT DEB                     1108  2023-01-27 00:38:00.000
11     45631 11037X     FREGAT DEB                     1164  2023-01-27 00:23:00.000
12     20127 88063E     ARIANE 3 DEB                   1219  2023-01-27 01:13:00.000
13      5702 63014CU    WESTFORD NEEDLES               1248  2023-01-27 00:15:00.000
14     37476 99025EJW   FENGYUN 1C DEB                 1251  2023-01-27 00:26:00.000
15     84236            TBA - TO BE ASSIGNED           1262  2023-01-26 23:48:00.000
16     26785 84035C     CZ-3 DEB                       1366  2023-01-27 01:03:00.000
17     84188            TBA - TO BE ASSIGNED           1380  2023-01-27 00:15:00.000
18     39345 10057K     CZ-3C DEB                      1426  2023-01-27 00:03:00.000
19     43982 14055AM    ATLAS 5 CENTAUR DEB            1429  2023-01-27 01:17:00.000
20     18603 62010G     MIDAS 5 DEB                    1461  2023-01-27 00:39:00.000
```

## Miss distance 2023 BU
![Miss distance 2023 BU](https://github.com/rtolesnikov/conjunction_sat_asterroid/blob/main/2023%20BU/Miss%20distance%202023%20BU.png)
## 2023 BU Flyby Configuration
![2023 BU Flyby Configuration](https://github.com/rtolesnikov/conjunction_sat_asterroid/blob/main/2023%20BU/Flyby%202023%20BU.png)
