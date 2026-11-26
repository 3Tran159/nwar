"""Preserve a failed zero-step PRE W04 setup before a corrected start."""
from common import *
from pre_w04 import PRE,CALM_RUN
from worker import native
assert not native(),'Native solver still active'
assert CALM_RUN.resolve().parent==PRE.resolve() and PRE.resolve().is_relative_to(DATA.resolve())
assert read(CALM_RUN/'stage_result.json').get('exit_code')!=0
assert not (CALM_RUN/'history.csv').exists(),'Calculation history exists; do not restart automatically'
target=PRE/('calm_setup_failed_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
assert target.resolve().parent==PRE.resolve() and not target.exists()
CALM_RUN.rename(target)
print('Failed zero-step setup preserved at '+str(target))
