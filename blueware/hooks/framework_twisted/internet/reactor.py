from blueware.agent import wrap_function_trace

def instrument_twisted_internet_reactor(module):
    if hasattr(module, 'doIteration'):
        wrap_function_trace(module, 'doIteration')
