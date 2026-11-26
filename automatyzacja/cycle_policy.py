"""Global measured-wave policy: record five; evaluate cycles 2 through 5.

Cycle 1 is excluded by position, never selected by its force values. Raw history
and all numerical-health checks still include that cycle, including on resumes.
"""
POLICY_ID = 'five_measured_cycles_discard_first_20261103'
TOTAL_CYCLES = 5
DISCARD_CYCLES = 1
ANALYSIS_CYCLES = 4


def selection(complete):
    selected = complete[DISCARD_CYCLES:TOTAL_CYCLES]
    return dict(cycle_policy_id=POLICY_ID, required_total_cycles=TOTAL_CYCLES,
                discarded_cycle_numbers=[c['number'] for c in complete[:DISCARD_CYCLES]],
                analyzed_cycle_numbers=[c['number'] for c in selected],
                analyzed_count=len(selected), analyzed_cycles=selected,
                discarded_reason='First complete measured cycle: fixed startup exclusion')


def accepted_cycles(cycles):
    return (cycles.get('cycle_policy_id') == POLICY_ID
            and cycles.get('count', 0) >= TOTAL_CYCLES
            and cycles.get('analyzed_count') == ANALYSIS_CYCLES
            and cycles.get('discarded_cycle_numbers') == [1]
            and cycles.get('analyzed_cycle_numbers') == [2, 3, 4, 5]
            and cycles.get('repeatable') is True)
