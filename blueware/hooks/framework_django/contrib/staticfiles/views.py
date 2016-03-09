from blueware.agent import (callable_name, current_transaction, 
                    FunctionTrace, FunctionWrapper)
from blueware.hooks.framework_django import should_ignore


def wrap_view_handler(wrapped, priority=3):

    # Ensure we don't wrap the view handler more than once. This
    # looks like it may occur in cases where the resolver is
    # called recursively. We flag that view handler was wrapped
    # using the '_bw_django_view_handler' attribute.

    if hasattr(wrapped, '_bw_django_view_handler'):
        return wrapped

    name = callable_name(wrapped)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        transaction.set_transaction_name(name, priority=priority)

        with FunctionTrace(transaction, name=name):
            try:
                return wrapped(*args, **kwargs)

            except:  # Catch all
                transaction.record_exception(ignore_errors=should_ignore)
                raise

    result = FunctionWrapper(wrapped, wrapper)
    result._bw_django_view_handler = True

    return result

def instrument_django_contrib_staticfiles_views(module):
    if not hasattr(module.serve, '_bw_django_view_handler'):
        module.serve = wrap_view_handler(module.serve, priority=3)
