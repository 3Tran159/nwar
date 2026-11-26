"""Compare the supplied quasi-steady force model with the final GLHF record."""
import zipfile

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

from analysis import mean_segment
from common import DATA, period, sha, write


POLAR = DATA/'glhf_imports'/'NACA66_XFOIL_full_polars_raw_20261106.zip'
POLAR_FILES = ('polar_negative.txt', 'polar_positive.txt')


def read_polar(path):
    rows = {}
    with zipfile.ZipFile(path) as archive:
        for name in POLAR_FILES:
            for line in archive.read(name).decode('ascii').splitlines():
                fields = line.split()
                if len(fields) != 7:
                    continue
                try:
                    alpha, cl, cd, *_ = map(float, fields)
                except ValueError:
                    continue
                rows[alpha] = (cl, cd)
    angles = np.array(sorted(rows))
    cl, cd = np.array([rows[a] for a in angles]).T
    return np.radians(angles), cl, cd


def compare(out, reference, manifest, t, force, gt, eta, start, end):
    if not POLAR.is_file():
        return None
    # Original C01's 18 m/s, 1000 kg/m³ and 0.0238 m² normalization.
    # The M13 chord runs from x=0 to 1.19 m at z≈0 and mean water level is z=2 m.
    speed, depth, water_depth = 18., 2., 24.
    scale = reference['coefficient_denominator_N']
    angles, cl, cd = read_polar(POLAR)
    lift_polar, drag_polar = CubicSpline(angles, cl), CubicSpline(angles, cd)
    alpha0 = brentq(lambda a: lift_polar(a)-reference['CL'], angles[0], angles[-1])
    baseline_lift, baseline_drag = scale*lift_polar(alpha0), scale*drag_polar(alpha0)
    components = manifest['components']
    wavelengths = np.array([c['lambda_m'] for c in components])
    nominal_amplitudes = np.array([c['H_m']/2 for c in components])
    k = 2*np.pi/wavelengths
    intrinsic = np.sqrt(9.81*k*np.tanh(k*water_depth))
    encounter = -2*np.pi/np.array([period(l) for l in wavelengths])
    horizontal = intrinsic*np.cosh(k*(water_depth-depth))/np.sinh(k*water_depth)
    vertical = intrinsic*np.sinh(k*(water_depth-depth))/np.sinh(k*water_depth)
    probe_window = (gt>=start)&(gt<=end)
    observed = eta[probe_window]
    probe_phase = (gt[probe_window,None]-start)*encounter
    basis = np.column_stack((np.ones(len(observed)), np.cos(probe_phase), np.sin(probe_phase)))
    coefficients = np.linalg.lstsq(basis,observed,rcond=None)[0]
    amplitudes = coefficients[1:3]-1j*coefficients[3:5]
    observed_fit = basis@coefficients
    variance = np.sum((observed-observed.mean())**2)
    fit_r2 = 1-np.sum((observed-observed_fit)**2)/variance if variance else 0.
    rotating = np.exp(1j*(t[:,None]-start)*encounter)
    mean = lambda values: float(mean_segment(t, values, start, end, .0013))
    cfd_lift = force['CL_hydrodynamic']*scale-reference['L_N']
    cfd_drag = force['CD_total']*scale-reference['D_N']
    cfd = dict(delta_L_N=mean(cfd_lift),delta_D_N=mean(cfd_drag))

    def forces(complex_amplitudes):
        waves = rotating*complex_amplitudes
        # Same head-wave convention and force rotation as the supplied model.
        ua = speed+waves.real@horizontal
        w = waves.imag@vertical
        epsilon = np.arctan2(w,ua)
        effective_alpha = alpha0+epsilon
        selected = (t>=start)&(t<=end)
        if effective_alpha[selected].min()<angles[0] or effective_alpha[selected].max()>angles[-1]:
            raise ValueError('W08bi quasi-steady incidence lies outside the available XFOIL polar.')
        q_area = scale*(ua**2+w**2)/speed**2
        lift = q_area*lift_polar(effective_alpha)
        drag = q_area*drag_polar(effective_alpha)
        tilt = -lift*np.sin(epsilon)
        polar_drag = drag*np.cos(epsilon)-baseline_drag
        delta_lift = drag*np.sin(epsilon)+lift*np.cos(epsilon)-baseline_lift
        delta_drag = tilt+polar_drag
        stats = dict(delta_L_N=mean(delta_lift),delta_D_N=mean(delta_drag),
                     tilt_D_N=mean(tilt),polar_D_N=mean(polar_drag))
        stats.update(residual_L_N=cfd['delta_L_N']-stats['delta_L_N'],
                     residual_D_N=cfd['delta_D_N']-stats['delta_D_N'])
        return stats, delta_lift, delta_drag

    nominal, _, _ = forces(nominal_amplitudes*np.exp(1j*np.angle(amplitudes)))
    probe, lift, drag = forces(amplitudes)
    result = dict(cfd=cfd, nominal=nominal, probe=probe, mean_window_s=[start,end],
                  U_m_s=speed, depth_m=depth, water_depth_m=water_depth, area_m2=.0238, chord_m=1.19,
                  alpha_trim_deg=float(np.degrees(alpha0)), polar_calm_D_N=float(baseline_drag),
                  measured_component_heights_m=(2*np.abs(amplitudes)).tolist(), probe_fit_r2=float(fit_r2),
                  polar_members=list(POLAR_FILES), polar_archive_sha256=sha(POLAR),
                  run_id=manifest['job_id'], fitted_to_CFD_forces=False)
    write(out/'W08bi_quasi_steady.json',result)

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10.5,6.2), layout='constrained')
    for ax, actual, predicted, name, key in zip(axes,(cfd_lift,cfd_drag),(lift,drag),('Vertical force','Horizontal force'),('delta_L_N','delta_D_N')):
        ax.plot(t,actual,label=f"CFD, mean {cfd[key]:+.2f} N",lw=1.2,color='#087f8c')
        ax.plot(t,predicted,label=f"Quasi-steady, mean {probe[key]:+.2f} N",lw=1.15,color='#a35e18')
        ax.axhline(0,color='#526674',ls=':',lw=.8)
        ax.set_ylabel(f'{name} change [N]')
        ax.legend(loc='upper right')
    axes[-1].set(xlim=(start,end),xlabel='Physical time [s]')
    fig.suptitle('W08bi · CFD and quasi-steady model with probe-based wave input')
    for suffix in ('png','svg'):
        fig.savefig(out/f'W08bi_quasi_steady.{suffix}')
    plt.close(fig)
    return result
