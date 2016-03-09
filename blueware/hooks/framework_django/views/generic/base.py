from blueware.agent import (callable_name, current_transaction, 
                    FunctionTrace, FunctionWrapper)


def wrap_view_dispatch(wrapped):

    # Wrapper to be applied to dispatcher for class based views.

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        def _args(request, *args, **kwargs):
            return request

        view = instance
        request = _args(*args, **kwargs)

        # We can't intercept the delegated view handler when it
        # is looked up by the dispatch() method so we need to
        # duplicate the lookup mechanism.

        if request.method.lower() in view.http_method_names:
            handler = getattr(view, request.method.lower(),
                    view.http_method_not_allowed)
        else:
            handler = view.http_method_not_allowed

        name = callable_name(handler)

        # The priority to be used when naming the transaction is
        # bit tricky. If the transaction name is already that of
        # the class based view, but not the method, then we want
        # the name of the method to override. This can occur
        # where the class based view was registered directly in
        # urls.py as the view handler. In this case we use the
        # priority of 5, matching what would be used by the view
        # handler so that it can override the transaction name.
        #
        # If however the transaction name is unrelated, we
        # preferably don't want it overridden. This can happen
        # where the class based view was invoked explicitly
        # within an existing view handler. In this case we use
        # the priority of 4 so it will not override the view
        # handler name where used as the transaction name.

        priority = 4

        if transaction.group == 'Function':
            if transaction.name == callable_name(view):
                priority = 5

        transaction.set_transaction_name(name, priority=priority)

        with FunctionTrace(transaction, name=name):
            return wrapped(*args, **kwargs)

    return FunctionWrapper(wrapped, wrapper)

def instrument_django_views_generic_base(module):
    module.View.dispatch = wrap_view_dispatch(module.View.dispatch)
