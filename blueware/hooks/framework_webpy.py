import sys

import blueware.packages.six as six

from blueware.agent import (current_transaction, wrap_function_trace,
                            wrap_in_function, wrap_out_function, wrap_pre_function,
                            callable_name, WSGIApplicationWrapper)

def transaction_name_delegate(*args, **kwargs):
    transaction = current_transaction()
    if transaction:
        if isinstance(args[1], six.string_types):
            f = args[1]
        else:
            f = callable_name(args[1])
        transaction.set_transaction_name(f)
    return (args, kwargs)

def wrap_handle_exception(self):
    transaction = current_transaction()
    if transaction:
        transaction.record_exception(*sys.exc_info())

def template_name(render_obj, name):
    return name

def instrument(module):

    if module.__name__ == 'web.application':
        wrap_out_function(module, 'application.wsgifunc', WSGIApplicationWrapper)
        wrap_in_function(module, 'application._delegate', transaction_name_delegate)
        wrap_pre_function(module, 'application.internalerror', wrap_handle_exception)

    elif module.__name__ == 'web.template':
        wrap_function_trace(module, 'render.__getattr__', template_name, 'Template/Render')
