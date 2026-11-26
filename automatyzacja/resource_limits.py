"""NWAR-only resource policy; shared CPU experiment runtime is unchanged."""
from common import HERE,ROOT,read
import shutil

def minimum_free_ram_gib():
    value=read(HERE/'resource_limits.json').get('minimum_free_RAM_GiB',16)
    if not isinstance(value,(int,float)) or not 8<=value<=64:
        raise ValueError('Invalid reviewed NWAR free-memory reserve.')
    return value

def memory_reason(free_memory):
    limit=minimum_free_ram_gib()
    return 'RAM_below'+format(limit,'g')+'GiB' if free_memory()<limit*2**30 else None

def owned_resource_problem(original,free_memory):
    reason=original()
    if reason not in (None,'RAM_below16GiB'):
        return reason
    memory=memory_reason(free_memory)
    if memory:return memory
    if shutil.disk_usage('C:/').free<15*2**30 or shutil.disk_usage(ROOT).free<25*2**30:
        return 'disk_guard'
    return None
