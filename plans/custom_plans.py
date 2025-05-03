from bluesky.plan_stubs import *

def count_w_time(detectors, num, delay, exposure_time, *, md=None):
    # Assume all detectors have one exposure time component called
    # 'exposure_time' that fully specifies its exposure.
    for detector in detectors:
        yield from mv(detector.exposure_time, exposure_time)
    yield from count(detectors, num, delay, md=md)

def scan_w_delay(*args, delay=0, **kwargs):
    "Accepts all the normal 'scan' parameters, plus an optional delay."

    def one_nd_step_with_delay(detectors, step, pos_cache):
        "This is a copy of bluesky.plan_stubs.one_nd_step with a sleep added."
        motors = step.keys()
        yield from move_per_step(step, pos_cache)
        yield from sleep(delay)
        yield from trigger_and_read(list(detectors) + list(motors))

    kwargs.setdefault('per_step', one_nd_step_with_delay)
    yield from scan(*args, **kwargs)

def rel_scan_w_delay(*args, delay=0, **kwargs):
    "Accepts all the normal 'scan' parameters, plus an optional delay."

    def one_nd_step_with_delay(detectors, step, pos_cache):
        "This is a copy of bluesky.plan_stubs.one_nd_step with a sleep added."
        motors = step.keys()
        yield from move_per_step(step, pos_cache)
        yield from sleep(delay)
        yield from trigger_and_read(list(detectors) + list(motors))

    kwargs.setdefault('per_step', one_nd_step_with_delay)
    yield from rel_scan(*args, **kwargs)