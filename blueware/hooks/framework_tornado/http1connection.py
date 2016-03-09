import sys

from blueware.agent import wrap_function_wrapper

from . import (retrieve_request_transaction, resume_request_monitoring,
               finish_request_monitoring, finalize_request_monitoring,
               request_finished, retrieve_current_transaction)


def _bw_wrapper_HTTP1Connection__finish_request(wrapped, instance, args, kwargs):

    # Normally called when the request is all complete meaning that we
    # have to finalize our own transaction. We may actually enter here
    # with the transaction already being the current one.

    connection = instance

    # For Tornado 4.0+
    request = getattr(connection, '_bw_request', None)
    connection._bw_request = None

    # print('request in finish_request: %r' % request)

    if request is None:
        return wrapped(*args, **kwargs)

    transaction = retrieve_request_transaction(request)

    # The wrapped function could be called more than once. If it is then
    # the transaction should already have been completed. In this case
    # the transaction should be None. To be safe also check whether the
    # request itself was already flagged as finished. If transaction was
    # the same as the current transaction the following check would have
    # just marked it as finished again, but this first check will cover
    # where the current transaction is for some reason different.

    if transaction is None:
        return wrapped(*args, **kwargs)

    if request_finished(request):
        return wrapped(*args, **kwargs)

    # Deal now with the possibility that the transaction is already the
    # current active transaction.

    if transaction == retrieve_current_transaction():
        finish_request_monitoring(request)

        return wrapped(*args, **kwargs)

    # If we enter here with an active transaction and it isn't the one
    # we expect, then not sure what we should be doing, so simply
    # return. This should hopefully never occur.

    if retrieve_current_transaction() is not None:
        return wrapped(*args, **kwargs)

    # Not the current active transaction and so we need to try and
    # resume the transaction associated with the request.

    transaction = resume_request_monitoring(request)

    if transaction is None:
        return wrapped(*args, **kwargs)

    finish_request_monitoring(request)

    try:
        result = wrapped(*args, **kwargs)

    except:  # Catch all
        # There should never be an error from wrapped function but
        # in case there is, try finalizing transaction.

        finalize_request_monitoring(request, *sys.exc_info())
        raise

    finalize_request_monitoring(request)

    return result


def instrument_tornado_http1connection(module):
    if hasattr(module, 'HTTP1Connection'):
        # The HTTP1Connection class only existed in Tornado 4.0+.

        wrap_function_wrapper(module, 'HTTP1Connection._finish_request',
                              _bw_wrapper_HTTP1Connection__finish_request)
