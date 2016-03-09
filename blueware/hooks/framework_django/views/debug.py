from blueware.agent import (callable_name, current_transaction, 
                    FunctionTrace, FunctionWrapper)
from blueware.hooks.framework_django import should_ignore, wrap_view_handler


def instrument_django_views_debug(module):

    # Wrap methods for handling errors when Django debug
    # enabled. For 404 we give this higher naming priority over
    # any prior middleware or view handler to give them
    # visibility. For a 500, which will be triggered for
    # unhandled exception, we leave any original name derived
    # from a middleware or view handler in place so error
    # details identify the correct transaction.

    module.technical_404_response = wrap_view_handler(
            module.technical_404_response, priority=3)
    module.technical_500_response = wrap_view_handler(
            module.technical_500_response, priority=1)
