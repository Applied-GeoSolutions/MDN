'''
Old version of SOLID from:
"Robust algorithm for estimating total suspended solids (TSS) in inland and nearshore coastal waters". S.V. Balasubramanian, et al. (2020).
'''

from ...utils import get_required, optimize, has_band, closest_wavelength, find_wavelength, to_rrs
from .MDN_old.product_estimation import image_estimates
from pathlib import Path
import numpy as np

params = {
	'MSI'   : ([443, 490, 560, 665, 705], 740),
	'OLI'   : ([443, 482, 561, 655], 865),
	'VI'    : ([410, 443, 486, 551, 671], 745),
	'MOD'   : ([412, 443, 488, 555, 667, 678], 748),
	'OLCI'  : ([411, 442, 490, 510, 560, 619, 664, 673, 681], 754),
}

aw  = get_required([0.3785, 0.4264, 2.72, 4.6], [655, 665, 740, 865])
bbw = get_required([0.00046, 0.00043, 0.0002625, 0.00014], [655, 665, 740, 865])

def _QAA_estimate(Rrs, band=660):
	# Gordon
	g0 = 0.0949
	g1 = 0.0794

	# Lee
	g0 = 0.084
	g1 = 0.17

	# QAA
	g0 = 0.08945
	g1 = 0.1247  

	u660 = (-g0 + (g0**2 + 4 * g1 * to_rrs(Rrs(band))) ** 0.5) / (2 * g1)
	a660 = 0.39 * (Rrs(band) / (Rrs(443) + Rrs(485))) ** 1.14 + aw(band).flatten()[0]
	b660 = (u660 * a660) / (1 - u660) - bbw(band).flatten()[0]
	return b660


# Define any optimizable parameters
@optimize(['a', 'b', 'c', 'd', 'e', 'f'])
def model(Rrs, wavelengths, sensor, *args, **kwargs):
	sensor = sensor.replace('S2B','MSI').replace('MODA', 'MOD')
	required, upper_band = params[sensor]

	tol = kwargs.get('tol', 10) # allowable difference from the required wavelengths
	Rrs = get_required(Rrs, wavelengths, required, tol) # get values as a function: Rrs(443)

	# Set default values for these parameters
	a = kwargs.get('a', 53.736) # Eq. 6
	b = kwargs.get('b', 0.8559) # Eq. 6
	c = kwargs.get('c', 224.43 if sensor == 'OLI' else 207.57) # Eq. 7 & 8
	d = kwargs.get('d', 12.575 if sensor == 'OLI' else 46.78)  # Eq. 7 & 8
	e = kwargs.get('e', 0.5 if sensor == 'OLI' else 1.65)      # a_nap
	f = kwargs.get('f', 0.105) # f/Q

	type1 = (Rrs(485) > Rrs(560)).flatten()
	type2 = (Rrs(560) > Rrs(660)).flatten()
	type3 = (Rrs(660) > Rrs(485)).flatten()

	estimate = np.empty(type1.shape)
	estimate.fill(np.nan)

	if has_band(upper_band, wavelengths, tol):
		bbp_NIR = (Rrs(upper_band)*(aw(upper_band) + e + bbw(upper_band)) - bbw(upper_band)*f) / (f-Rrs(upper_band))
		estimate[type3] = (c * bbp_NIR - d).flatten()[type3]

	bbp = image_estimates(*Rrs(required).T, sensor=sensor)
	bbp_665 = bbp[find_wavelength(660, required)[0]]
	estimate[type2] = (a * bbp_665 ** b).flatten()[type2]

	bbp_665 = _QAA_estimate(Rrs, closest_wavelength(660, wavelengths))
	estimate[type1] = (a * bbp_665 ** b).flatten()[type1]

	return estimate
