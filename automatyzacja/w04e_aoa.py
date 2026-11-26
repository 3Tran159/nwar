"""Read saved W04e section fields and compare local inflow angle with forces."""
import os

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from common import DATA, Path, job, now, read, sha, write
from analysis import analyze, gauge_series, numeric_rows
from project_results import c01_force_reference
from response_plots import response_profile
import csv
import h5py
import numpy as np
from scipy.spatial import cKDTree
from matplotlib.path import Path as PolygonPath


RUN_ID = '449524f35ca14e94'
OUT = DATA/'analyses/W04e_aoa_20261107'
PART = 'Parts/Derived/NWAR midspan wake/OutputPiece  0::NWAR wake recording box'
PROBES = [('upstream', -.9, 0.), ('middle', -.6, 0.), ('near', -.3, 0.),
          ('upstream_below', -.9, -.1), ('upstream_above', -.9, .1)]
BUOYANCY = 22.718189111947265


def foil_geometry(mesh):
    with h5py.File(mesh, 'r') as file:
        zone = file['Base/fluid']
        xyz = np.column_stack([zone['GridCoordinates/Coordinate'+axis+'/ data'][:] for axis in 'XYZ'])
        indices = np.unique(zone['HF_012_wall/ElementConnectivity/ data'][:]-1)
        wall = xyz[indices]
        wall = wall[np.isclose(wall[:, 1], .01)]
    leading = wall[np.isclose(wall[:, 0], wall[:, 0].min(), atol=1e-10)].mean(axis=0)
    trailing = wall[np.isclose(wall[:, 0], wall[:, 0].max(), atol=1e-10)].mean(axis=0)
    angle = np.degrees(np.arctan2(trailing[2]-leading[2], trailing[0]-leading[0]))
    return dict(leading_edge_m=leading.tolist(), trailing_edge_m=trailing.tolist(),
                chord_angle_deg=float(angle), chord_m=float(np.linalg.norm(trailing-leading)),
                definition='Leadingmost mesh wall point to trailingmost mesh wall point, projected in x-z.'), wall


def extract_fields(history, chord):
    rows = []
    with h5py.File(history, 'r') as file:
        names = sorted(file['States'], key=lambda name: int(name.split()[-1]))
        first = file['States/'+names[0]+'/'+PART]
        coord = first['Coord'][:]
        lengths = first['VertexList/VertexList_lengths'][:].astype(np.int64)
        offsets = np.r_[0, np.cumsum(lengths)]
        connectivity = first['VertexList/VertexList'][:].astype(np.int64)
        centers = np.add.reduceat(coord[connectivity][:, [0, 2]], offsets[:-1])/lengths[:, None]
        tree = cKDTree(centers)
        point_cells = []
        stencil = []
        for label, x, z in PROBES:
            distance, candidates = tree.query([x, z], k=64)
            contained = [int(index) for index in candidates if PolygonPath(
                coord[connectivity[offsets[index]:offsets[index+1]]][:, [0, 2]]).contains_point((x, z))]
            if not contained:
                raise ValueError('No recorded fluid polygon contains probe '+label)
            index = min(contained, key=lambda index: np.linalg.norm(centers[index]-[x, z]))
            point_cells.append(index)
            polygon = coord[connectivity[offsets[index]:offsets[index+1]]]
            stencil.append(dict(name=label, x_m=x, y_m=.02, z_m=z, face_index=index,
                                cell_center_xz_m=centers[index].tolist(),
                                cell_width_xz_m=np.ptp(polygon[:, [0, 2]], axis=0).tolist()))
        distance, smooth = tree.query([PROBES[0][1], PROBES[0][2]], k=4)
        weights = 1/np.maximum(distance, 1e-12)**2
        weights /= weights.sum()
        face_indices = np.unique(np.r_[point_cells, smooth]).astype(np.int64)
        local_indices = np.searchsorted(face_indices, point_cells)
        smooth_indices = np.searchsorted(face_indices, smooth)
        positions = np.concatenate([np.arange(offsets[i], offsets[i+1]) for i in face_indices])
        vertices = np.unique(connectivity[positions])
        for n, name in enumerate(names):
            state = file['States/'+name]
            part = state[PART]
            if (part['Coord'].shape != coord.shape
                    or not np.array_equal(part['VertexList/VertexList_lengths'][face_indices], lengths[face_indices])
                    or not np.array_equal(part['VertexList/VertexList'][positions], connectivity[positions])
                    or not np.allclose(part['Coord'][vertices], coord[vertices], rtol=0, atol=1e-11)):
                raise ValueError('The recorded local probe geometry changes in '+name)
            velocity = part['FaceData/VelocityFieldFunction'][face_indices]
            water = part['FaceData/VolumeFractionwaterFieldFunction'][face_indices]
            pressure = part['FaceData/PressureFieldFunction'][face_indices]
            time = float(state.attrs['PhysicalTime'][0])
            for k, (label, x, z) in enumerate(PROBES):
                i = local_indices[k]
                ux, uy, uz = velocity[i]
                beta = np.degrees(np.arctan2(uz, ux))
                if not np.isfinite(velocity[i]).all() or ux <= 0 or water[i] < .999:
                    raise ValueError('Invalid or non-water upstream velocity sample')
                rows.append(dict(time_s=time, probe=label, x_m=x, y_m=.02, z_m=z,
                                 ux_m_s=float(ux), uy_m_s=float(uy), uz_m_s=float(uz),
                                 speed_m_s=float(np.linalg.norm(velocity[i])), flow_angle_deg=float(beta),
                                 aoa_deg=float(beta-chord['chord_angle_deg']),
                                 water_fraction=float(water[i]), pressure_Pa=float(pressure[i])))
            interpolated = weights@velocity[smooth_indices]
            beta = np.degrees(np.arctan2(interpolated[2], interpolated[0]))
            rows.append(dict(time_s=time, probe='upstream_idw4', x_m=-.9, y_m=.02, z_m=0.,
                             ux_m_s=float(interpolated[0]), uy_m_s=float(interpolated[1]), uz_m_s=float(interpolated[2]),
                             speed_m_s=float(np.linalg.norm(interpolated)), flow_angle_deg=float(beta),
                             aoa_deg=float(beta-chord['chord_angle_deg']),
                             water_fraction=float(weights@water[smooth_indices]), pressure_Pa=float(weights@pressure[smooth_indices])))
            if n % 50 == 0:
                print('Read native field state', n+1, 'of', len(names), flush=True)
    return rows, stencil


def save_rows(path, rows):
    with path.open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entry = job(RUN_ID)
    folder = Path(entry['folder'])
    history = folder/'native_solve/wake.simh'
    mesh = DATA/'mesh_W04_20261102/geometry/mesh.CGNS'
    before = history.stat()
    chord, wall = foil_geometry(mesh)
    rows, stencil = extract_fields(history, chord)
    save_rows(OUT/'W04e_upstream_velocity_aoa.csv', rows)
    result, data, _ = analyze(dict(entry['spec'], id='W04e'), [folder])
    reference = c01_force_reference()
    phase = response_profile(data, gauge_series([folder], 0.), 1.5, 15., x=0.,
                             origin=result['wave_origin_s'], probe_distance=result['probe_distance_m']+.5,
                             force_reference=reference)
    assert phase['cycle_numbers'] == [2, 3, 4, 5]
    evidence = dict(at=now(), run_id=RUN_ID, history_file=str(history), history_sha256=sha(history),
                    mesh_file=str(mesh), mesh_sha256=sha(mesh), chord=chord, probes=stencil,
                    field_sampling='Containing recorded polygon value; optional four-cell inverse-distance check.',
                    aoa_definition='atan2(Uz,Ux) minus the LE-to-TE chord-line angle; positive upward incident flow.',
                    plane_y_m=.02, source_states=len(rows)//6, phase=phase,
                    raw_history_sha256=sha(folder/'history.csv'), gauge_history_sha256=sha(folder/'gauges.csv'))
    after = history.stat()
    assert before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns
    write(OUT/'W04e_aoa_evidence.json', evidence)
    np.savez(OUT/'W04e_foil_outline.npz', wall=wall[:, [0, 2]])
    for probe in ['upstream', 'middle', 'near']:
        values = np.array([r['aoa_deg'] for r in rows if r['probe'] == probe])
        print(probe, 'AoA range', values.min(), values.max(), flush=True)
    print('Phase windows', phase['windows_s'], flush=True)


def phase_plots():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from analysis import mean_segment
    from common import CALM

    evidence = read(OUT/'W04e_aoa_evidence.json')
    phase = evidence['phase']
    reference = phase['C01']
    fields = list(csv.DictReader((OUT/'W04e_upstream_velocity_aoa.csv').open()))
    folder = Path(job(RUN_ID)['folder'])
    force = numeric_rows(folder/'history.csv')
    phi = np.array(phase['phase_deg'])
    windows = phase['windows_s']
    times = np.array([a+(b-a)*phi/360 for a,b in windows])
    curves = {key:np.interp(times, force['time_s'], force[key]) for key in
              ['Fx_N','Fz_N','Fx_pressure_N','Fx_viscous_N']}
    for probe in [p[0] for p in PROBES]+['upstream_idw4']:
        records = [r for r in fields if r['probe'] == probe]
        time = np.array([float(r['time_s']) for r in records])
        if times.min()<time.min() or times.max()>time.max():
            raise ValueError('Phase sampling would extrapolate outside the field history')
        if np.max(np.diff(time))>.010401:
            raise ValueError('Native field history has a missing time sample')
        for key in ['aoa_deg','flow_angle_deg','ux_m_s','uz_m_s']:
            curves[probe+'_'+key] = np.interp(times, time, [float(r[key]) for r in records])
    delta_fx = curves['Fx_N']-reference['D_N']
    beta = np.radians(curves['upstream_flow_angle_deg'])
    vertical = curves['Fz_N']-BUOYANCY
    parallel = curves['Fx_N']*np.cos(beta)+vertical*np.sin(beta)
    normal = -curves['Fx_N']*np.sin(beta)+vertical*np.cos(beta)
    parallel_x = parallel*np.cos(beta)-reference['D_N']
    normal_x = -normal*np.sin(beta)
    assert np.max(abs(parallel_x+normal_x-delta_fx))<1e-10
    calm = numeric_rows(CALM/'history.csv')
    end = read(CALM/'C01_final_acceptance_20261101.json')['physical_time_s']
    baseline = {key:mean_segment(calm['physical_time_s'],calm[key],end-.2,end,.0013)
                for key in ['pressure_drag_N','viscous_drag_N']}
    delta_pressure = curves['Fx_pressure_N']-baseline['pressure_drag_N']
    delta_viscous = curves['Fx_viscous_N']-baseline['viscous_drag_N']
    eta = np.array(phase['eta_prime_cycles'])
    speed_ratio = (curves['upstream_ux_m_s']**2+curves['upstream_uz_m_s']**2)/18**2
    mean = lambda x:np.mean(x,axis=0)

    plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,
                         'legend.fontsize':8.5,'svg.fonttype':'none'})
    colors = ['#6e4ca1','#16866f','#c17a19']
    def decorate(ax, label):
        ax.axvspan(100,270,color='#a0aeba',alpha=.13,zorder=0)
        ax.set(xlim=(0,360),xticks=[0,45,90,135,180,225,270,315,360],ylabel=label)
        ax.grid(alpha=.18)
    def band(ax, values, color, label):
        for row in values:ax.plot(phi,row,color=color,alpha=.16,lw=.7)
        ax.fill_between(phi,values.min(0),values.max(0),color=color,alpha=.12)
        ax.plot(phi,mean(values),color=color,lw=2,label=label)
    def save(fig, name):
        for suffix in ['png','svg']:fig.savefig(OUT/(name+'.'+suffix),dpi=190)
        plt.close(fig)

    fig,axes = plt.subplots(3,1,figsize=(11.5,9),sharex=True,layout='constrained',
                            gridspec_kw={'height_ratios':[.75,1,1.15]})
    band(axes[0],eta,'#087f8c','Measured wave at x = 0 m')
    decorate(axes[0],'Surface fluctuation [m]')
    axes[0].set_title('(a) Wave phase reference, upward level crossing at x = 0 m',loc='left')
    axes[0].legend(loc='upper right')
    for probe,color,label in zip(['upstream','middle','near'],colors,
                                  ['x = -0.9 m, main probe','x = -0.6 m','x = -0.3 m']):
        values = curves[probe+'_aoa_deg']
        if probe=='upstream':band(axes[1],values,color,label)
        else:axes[1].plot(phi,mean(values),color=color,lw=1.3,ls='--',label=label)
    decorate(axes[1],'Local inflow AoA [deg]')
    axes[1].set_title('(b) Measured velocity direction relative to the mesh chord',loc='left')
    axes[1].legend(loc='upper right',ncol=3)
    band(axes[2],delta_fx,'#176fa3','Horizontal force change from C01')
    axes[2].axhline(0,color='#526674',lw=.9,ls=':',label='C01')
    decorate(axes[2],r'$F_x-F_{x,\mathrm{C01}}$ [N]')
    axes[2].set_title('(c) CFD force along the fixed domain x axis',loc='left')
    axes[2].legend(loc='lower right')
    axes[2].set_xlabel('Wave phase at x = 0 [deg]')
    fig.suptitle('W04e | H = 1.5 m, wavelength = 15 m | measured cycles 2-5',fontsize=14)
    fig.supxlabel('Fields every 0.0104 s. Thin lines and bands show cycle spread. Shaded phase range = 100-270 deg.',fontsize=9)
    save(fig,'W04e_aoa_horizontal_force_phase')

    fig,axes = plt.subplots(2,2,figsize=(13,9),layout='constrained')
    a,b,c,d = axes.ravel()
    for values,color,label in [(delta_pressure,'#b05d12','Pressure'),(delta_viscous,'#16866f','Viscous'),
                               (delta_fx,'#176fa3','Total')]:
        a.plot(phi,mean(values),color=color,lw=1.8,label=label)
    decorate(a,'Force change from C01 [N]')
    a.set_title('(a) Independently recorded force components',loc='left')
    a.set_xlabel('Wave phase at x = 0 [deg]');a.legend()
    for values,color,label in [(parallel_x,'#b05d12',r'$F_\parallel\cos\beta-F_{x,\mathrm{C01}}$'),
                               (normal_x,'#6e4ca1',r'$-F_\perp\sin\beta$'),(delta_fx,'#176fa3','Measured sum')]:
        b.plot(phi,mean(values),color=color,lw=1.7,label=label)
    decorate(b,'Horizontal contribution [N]')
    b.set_title('(b) Kinematic projection using the measured inflow angle',loc='left')
    b.set_xlabel('Wave phase at x = 0 [deg]');b.legend()
    alpha = mean(curves['upstream_aoa_deg']);fx = mean(delta_fx)
    for aa,ff in zip(curves['upstream_aoa_deg'],delta_fx):c.plot(aa,ff,color='#6e4ca1',alpha=.18,lw=.8)
    xy=np.column_stack([alpha,fx]);segments=np.stack([xy[:-1],xy[1:]],axis=1)
    line=LineCollection(segments,cmap='viridis',norm=plt.Normalize(0,360),linewidth=2.5)
    line.set_array(phi[:-1]);c.add_collection(line);c.autoscale();c.grid(alpha=.18)
    for i in [0,30,60,90]:c.annotate('',xy=xy[i+3],xytext=xy[i],arrowprops=dict(arrowstyle='->',color='#354b58',lw=1))
    c.set(xlabel='AoA at x = -0.9 m [deg]',ylabel=r'$F_x-F_{x,\mathrm{C01}}$ [N]',title='(c) Force-AoA loop, arrows follow time')
    cb=fig.colorbar(line,ax=c,pad=.02);cb.set_label('Wave phase [deg]');cb.set_ticks([0,90,180,270,360])
    d.plot(phi,mean(curves['upstream_ux_m_s'])-18,color='#b05d12',lw=1.8,label=r'$U_x-18$')
    d.plot(phi,mean(curves['upstream_uz_m_s']),color='#6e4ca1',lw=1.8,label=r'$U_z$')
    decorate(d,'Local velocity [m/s]');d.set_xlabel('Wave phase at x = 0 [deg]')
    d.set_title('(d) Velocity measured before the foil',loc='left');d.legend()
    fig.suptitle('W04e | pressure, viscosity and local force-axis projection',fontsize=14)
    fig.supxlabel('Panel (b) is an exact rotation of measured forces, not an independent force model. Vertical force excludes buoyancy.',fontsize=9)
    save(fig,'W04e_aoa_force_mechanism')

    exported=[]
    for k,(a,b) in enumerate(windows):
        for i,angle in enumerate(phi):
            exported.append(dict(cycle=k+2,phase_deg=angle,time_s=times[k,i],
                eta_prime_m=eta[k,i],aoa_deg=curves['upstream_aoa_deg'][k,i],
                aoa_middle_deg=curves['middle_aoa_deg'][k,i],aoa_near_deg=curves['near_aoa_deg'][k,i],
                ux_m_s=curves['upstream_ux_m_s'][k,i],uz_m_s=curves['upstream_uz_m_s'][k,i],
                Fx_N=curves['Fx_N'][k,i],delta_Fx_N=delta_fx[k,i],
                delta_pressure_Fx_N=delta_pressure[k,i],delta_viscous_Fx_N=delta_viscous[k,i],
                parallel_horizontal_change_N=parallel_x[k,i],normal_horizontal_N=normal_x[k,i]))
    save_rows(OUT/'W04e_aoa_force_phase_cycles.csv',exported)
    sector_rows=[]
    derivative=np.gradient(mean(delta_fx),phi)
    for start,end in [(0,100),(100,270),(270,360)]:
        mask=(phi>start)&(phi<end);angles=np.r_[start,phi[mask],end]
        sample=lambda value:np.interp(angles,phi,mean(value))
        sector_rows.append(dict(start_deg=start,end_deg=end,
            aoa_mean_deg=float(np.trapezoid(sample(curves['upstream_aoa_deg']),angles)/(end-start)),
            delta_Fx_mean_N=float(np.trapezoid(sample(delta_fx),angles)/(end-start)),
            delta_Fx_range_N=float(np.ptp(sample(delta_fx))),
            slope_rms_N_per_deg=float(np.sqrt(np.mean(np.interp(angles,phi,derivative)**2))),
            pressure_range_N=float(np.ptp(sample(delta_pressure))),viscous_range_N=float(np.ptp(sample(delta_viscous)))))
    save_rows(OUT/'W04e_phase_sector_metrics.csv',sector_rows)
    metrics=dict(at=now(),phase_origin=phase['phase_origin'],phase_windows_s=windows,cycle_numbers=[2,3,4,5],
        main_probe=PROBES[0],chord=evidence['chord'],native_frames=evidence['source_states'],
        aoa_mean_curve_range_deg=[float(alpha.min()),float(alpha.max())],
        aoa_all_selected_cycles_range_deg=[float(curves['upstream_aoa_deg'].min()),float(curves['upstream_aoa_deg'].max())],
        pressure_peak_to_peak_N=float(np.ptp(mean(delta_pressure))),
        viscous_peak_to_peak_N=float(np.ptp(mean(delta_viscous))),
        total_peak_to_peak_N=float(np.ptp(mean(delta_fx))),
        main_probe_velocity_ratio_range=[float(mean(speed_ratio).min()),float(mean(speed_ratio).max())],
        stencil_check_aoa_rms_deg=float(np.sqrt(np.mean((curves['upstream_idw4_aoa_deg']-curves['upstream_aoa_deg'])**2))),
        projection_identity_error_N=float(np.max(abs(parallel_x+normal_x-delta_fx))),
        baseline_pressure_viscous_N=baseline,sectors=sector_rows,
        limitations=['The closest recorded upstream boundary is x = -1 m. The probe includes foil-induced flow.',
                     'Recorded data are from one midspan section.',
                     'Force-axis projection is a kinematic identity and does not independently establish causality.'])
    radians=np.radians(phi[:-1])
    basis=np.column_stack([np.ones(len(radians)),*[fn(n*radians) for n in [1,2,3]
                                                  for fn in [np.sin,np.cos]]])
    harmonics={}
    fig,axes=plt.subplots(2,1,figsize=(11,7.5),sharex=True,layout='constrained')
    for key,values,ax,label in [('aoa',alpha,axes[0],'Local inflow AoA [deg]'),
                                ('Fx',fx,axes[1],r'$F_x-F_{x,\mathrm{C01}}$ [N]')]:
        coefficients=np.linalg.lstsq(basis,values[:-1],rcond=None)[0]
        amplitudes=[float(np.hypot(*coefficients[i:i+2])) for i in [1,3,5]]
        harmonics[key]=dict(mean=float(coefficients[0]),amplitudes=amplitudes,
                            second_to_first=amplitudes[1]/amplitudes[0])
        full=np.column_stack([np.ones(len(phi)),*[fn(n*np.radians(phi)) for n in [1,2,3]
                                                 for fn in [np.sin,np.cos]]])
        ax.plot(phi,values,color='#176fa3',lw=2,label='Measured cycle mean')
        ax.plot(phi,full[:,:3]@coefficients[:3],color='#6c7680',ls='--',lw=1.5,label='Mean + fundamental')
        if key=='Fx':ax.plot(phi,full[:,:5]@coefficients[:5],color='#bf6b15',ls=':',lw=2,label='Mean + fundamental + second harmonic')
        decorate(ax,label);ax.legend(loc='best')
        ax.set_title(('(a) Inflow angle' if key=='aoa' else '(b) Horizontal force')+
                     f' | second / fundamental = {100*amplitudes[1]/amplitudes[0]:.1f}%',loc='left')
    axes[1].set_xlabel('Wave phase at x = 0 [deg]')
    fig.suptitle('W04e | harmonic shaping of the horizontal-force plateau',fontsize=14)
    fig.supxlabel('Fourier decomposition describes the measured response. It is not an independent causal model.',fontsize=9)
    save(fig,'W04e_aoa_force_harmonics')
    for key,values in [('pressure',mean(delta_pressure)),('viscous',mean(delta_viscous)),
                        ('parallel_horizontal',mean(parallel_x)),('normal_horizontal',mean(normal_x))]:
        coefficients=np.linalg.lstsq(basis,values[:-1],rcond=None)[0]
        harmonics[key]=dict(mean=float(coefficients[0]),amplitudes=[float(np.hypot(*coefficients[i:i+2])) for i in [1,3,5]])
    paired=[]
    for target in [1.5,2.]:
        for i in range(len(phi)-1):
            start,end=alpha[i:i+2]
            if (start-target)*(end-target)<0:
                fraction=(target-start)/(end-start)
                at=lambda values:float(values[i]+fraction*(values[i+1]-values[i]))
                paired.append(dict(aoa_deg=target,phase_deg=at(phi),delta_Fx_N=at(fx),
                                   ux_m_s=at(mean(curves['upstream_ux_m_s'])),
                                   uz_m_s=at(mean(curves['upstream_uz_m_s']))))
    save_rows(OUT/'W04e_same_aoa_different_force.csv',paired)
    metrics.update(harmonics=harmonics,same_aoa_comparison=paired)
    window_start,window_end=windows[0][0],windows[-1][1]
    average=lambda key:mean_segment(force['time_s'],force[key],window_start,window_end,.0013)
    metrics['exact_time_window_means']=dict(window_s=[window_start,window_end],
        delta_Fx_N=average('Fx_N')-reference['D_N'],
        delta_pressure_Fx_N=average('Fx_pressure_N')-baseline['pressure_drag_N'],
        delta_viscous_Fx_N=average('Fx_viscous_N')-baseline['viscous_drag_N'])
    write(OUT/'W04e_aoa_metrics.json',metrics)
    print(metrics,flush=True)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--plot-only',action='store_true')
    args=parser.parse_args()
    if not args.plot_only:main()
    phase_plots()
