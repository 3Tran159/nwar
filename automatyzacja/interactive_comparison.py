"""Offline, linked four-panel view of the same accepted phase-average arrays."""
import json
from pathlib import Path


def save_interactive(out, records):
    from comparison_plots import STYLES
    cases = []
    for r in records:
        p = r['force_wave_response']
        color, style = STYLES.get(r['case'], ('#333333', '-'))
        cases.append(dict(id=r.get('display_id', r['case']), H=r['H'], wavelength=r['L'],
                          color=color, dash=[] if style == '-' else list(style[1]),
                          phase=p['phase_deg'], eta=p['eta_prime_mean_m'],
                          vertical=p['lift_minus_C01_mean_N'], horizontal=p['drag_minus_C01_mean_N'],
                          crest=p['crest_phase_deg'], trough=p['trough_phase_deg']))
    payload = dict(cases=cases, C01=records[0]['force_wave_response']['C01'])
    template = Path(__file__).with_name('interactive_comparison.html').read_text(encoding='utf8')
    # JSON is inert text; escape HTML terminators even if a future label contains them.
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    target = Path(out)/'force_wave_comparison_interactive.html'
    target.write_text(template.replace('__NWAR_DATA__', data), encoding='utf8')
    return target.name
