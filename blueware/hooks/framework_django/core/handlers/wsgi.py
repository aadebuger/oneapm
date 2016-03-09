from blueware.agent import (callable_name, current_transaction, 
                    WSGIApplicationWrapper, FunctionTrace, FunctionWrapper)
import sys


def wrap_handle_uncaught_exception(middleware):

    # Wrapper to be applied to handler called when exceptions
    # propagate up to top level from middleware. Records the
    # time spent in the handler as separate function node. Names
    # the web transaction after the name of the handler if not
    # already named at higher priority and capture further
    # errors in the handler.

    name = callable_name(middleware)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        def _wrapped(request, resolver, exc_info):
            transaction.set_transaction_name(name, priority=1)
            transaction.record_exception(*exc_info)

            try:
                return wrapped(request, resolver, exc_info)

            except:  # Catch all
                transaction.record_exception(*sys.exc_info())
                raise

        with FunctionTrace(transaction, name=name):
            return _wrapped(*args, **kwargs)

    return FunctionWrapper(middleware, wrapper)

def instrument_django_core_handlers_wsgi(module):

    # Wrap the WSGI application entry point. If this is also
    # wrapped from the WSGI script file or by the WSGI hosting
    # mechanism then those will take precedence.

    import django

    framework = ('Django', django.get_version())

    module.WSGIHandler.__call__ = WSGIApplicationWrapper(
          module.WSGIHandler.__call__, framework=framework)

    # Wrap handle_uncaught_exception() of WSGIHandler so that
    # can capture exception details of any exception which
    # wasn't caught and dealt with by an exception middleware.
    # The handle_uncaught_exception() function produces a 500
    # error response page and otherwise suppresses the
    # exception, so last chance to do this as exception will not
    # propogate up to the WSGI application.

    module.WSGIHandler.handle_uncaught_exception = (
            wrap_handle_uncaught_exception(
            module.WSGIHandler.handle_uncaught_exception))
