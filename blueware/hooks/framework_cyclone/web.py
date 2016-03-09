import sys
import itertools
import logging

from blueware.agent import (wrap_function_wrapper,
    FunctionTrace, callable_name, wrap_function_trace)

from . import (retrieve_request_transaction, initiate_request_monitoring,
    suspend_request_monitoring, resume_request_monitoring,
    finalize_request_monitoring, record_exception, request_finished,
    retrieve_current_transaction)

_logger = logging.getLogger(__name__)

def _bw_wrapper_Application___call__wsgi_(wrapped, instance, args, kwargs):

    transaction = retrieve_current_transaction()

    with FunctionTrace(transaction, name='Request/Process',
            group='Python/Cyclone'):
        return wrapped(*args, **kwargs)

def _bw_wrapper_Application___call__no_body_(wrapped, instance, args, kwargs):
    # This variant of the Application.__call__() wrapper is used when it
    # is believed that we are being called for a HTTP request where
    # there is no request content. There should be no transaction
    # associated with the Cyclone request object and also no current
    # active transaction. Create the transaction but if it is None then
    # it means recording of transactions is not enabled then do not need
    # to do anything.

    def _params(request, *args, **kwargs):
        return request

    request = _params(*args, **kwargs)

    transaction = initiate_request_monitoring(request)

    if transaction is None:
        return wrapped(*args, **kwargs)

    # Call the original method in a trace object to give better context
    # in transaction traces. It should return the RequestHandler instance
    # which the request was passed off to. It should only every return
    # an exception in situation where application was being shutdown so
    # finalize the transaction on any error.

    try:
        with FunctionTrace(transaction, name='Request/Process',
                group='Python/Cyclone'):
            handler = wrapped(*args, **kwargs)

    except:  # Catch all
        finalize_request_monitoring(request, *sys.exc_info())
        raise

    else:
        # In the case of the response completing immediately or an
        # exception occuring, then finish() should have been called on
        # the request already. We can't just exit the transaction in the
        # finish() call however as will need to still pop back up
        # through the above function trace. So if it has been flagged
        # that it is finished, which Cyclone does by setting the request
        # object in the connection to None, then we exit the transaction
        # here. Otherwise we setup a function trace to track wait time
        # for deferred and suspend monitoring.

        if not request_finished(request):
            suspend_request_monitoring(request, name='Callback/Wait')
        else:
            finalize_request_monitoring(request)

        return handler

def _bw_wrapper_Application___call__body_(wrapped, instance, args, kwargs):
    # This variant of the Application.__call__() wrapper is used when it
    # is believed that we are being called for a HTTP request where
    # there is request content. There should already be a transaction
    # associated with the Cyclone request object and also a current
    # active transaction.

    transaction = retrieve_current_transaction()

    with FunctionTrace(transaction, name='Request/Process',
            group='Python/Cyclone'):
        return wrapped(*args, **kwargs)

def _bw_wrapper_Application___call___(wrapped, instance, args, kwargs):

    def _params(request, *args, **kwargs):
        return request

    request = _params(*args, **kwargs)

    # Check first for the case where we are called via a WSGI adapter.
    # The presumption here is that there can be no ASYNC callbacks.

    transaction = retrieve_request_transaction(request)

    if transaction is None and retrieve_current_transaction():
        return _bw_wrapper_Application___call__wsgi_(wrapped, instance,
                args, kwargs)

    # Now check for where we are being called on a HTTP request where
    # there is no request content.

    if transaction is None:
        return _bw_wrapper_Application___call__no_body_(wrapped, instance,
                args, kwargs)

    # Finally have case where being called on a HTTP request where there
    # is request content.

    return _bw_wrapper_Application___call__body_(wrapped, instance,
            args, kwargs)

def _bw_wrapper_RequestHandler__execute_(wrapped, instance, args, kwargs):

    handler = instance
    request = handler.request

    # Check to see if we are being called within the context of any sort
    # of transaction. If we aren't, then we don't bother doing anything and
    # just call the wrapped function.

    transaction = retrieve_current_transaction()

    if transaction is None:
        return wrapped(*args, **kwargs)

    # If the method isn't one of the supported ones, then we expect the
    # wrapped method to raise an exception for HTTPError(405). Name the
    # transaction after the wrapped method first so it is used if that
    # occurs.

    name = callable_name(wrapped)
    transaction.set_transaction_name(name)

    if request.method not in handler.SUPPORTED_METHODS:
        return wrapped(*args, **kwargs)

    # Otherwise we name the transaction after the handler function that
    # should end up being executed for the request. We don't create a
    # function trace node at this point as that is handled by the fact
    # that we wrapped the exposed methods from the wrapper for the
    # constructor of the request handler.

    name = callable_name(getattr(handler, request.method.lower()))
    transaction.set_transaction_name(name)

    # Call the original RequestHandler._execute(). So long as the
    # prepare() method is not a coroutine which doesn't complete
    # straight away, then the actual handler function handler should
    # also be called at this point.

    return wrapped(*args, **kwargs)

def _bw_wrapper_RequestHandler__execute_handler_(wrapped, instance,
        args, kwargs):

    return wrapped(*args, **kwargs)


def _bw_wrapper_RequestHandler__handle_request_exception_(wrapped,
        instance, args, kwargs):

    # The RequestHandler._handle_request_exception() method is called
    # with the details of any unhandled exception. It is believed to
    # always be called in the context of an except block and so we can
    # safely use sys.exc_info() to get the actual details.

    transaction = retrieve_current_transaction()

    if transaction is not None:
        record_exception(transaction, sys.exc_info())

    return wrapped(*args, **kwargs)

def _bw_wrapper_RequestHandler_finish_(wrapped, instance, args, kwargs):
    # The RequestHandler.finish() method will either be called explicitly
    # by the user, but called also be called automatically by Cyclone.
    # It is possible that it can be called twice so it is necessary to
    # protect against that.

    handler = instance
    request = handler.request

    # Bail out out if we think the request as a whole has been completed.

    if request_finished(request):
        return wrapped(*args, **kwargs)

    # Call wrapped method straight away if request object it is being
    # called on is not even associated with a transaction. If we were in
    # a running transaction we still want to record the call though.
    # This will occur when calling finish on another request, but the
    # target request wasn't monitored.

    transaction = retrieve_request_transaction(request)

    active_transaction = retrieve_current_transaction()

    if transaction is None:
        if active_transaction is not None:
            name = callable_name(wrapped)

            with FunctionTrace(active_transaction, name):
                return wrapped(*args, **kwargs)

        else:
            return wrapped(*args, **kwargs)

    # If we have an active transaction, we we need to consider two
    # possiblities. The first is where the current running transaction
    # doesn't match that bound to the request. For this case it would be
    # where from within one transaction there is an attempt to call
    # finish() on a distinct web request which was being monitored. The
    # second is where finish() is being called for the current request.

    if active_transaction is not None:
        if transaction != active_transaction:
            # For this case we need to suspend the current running
            # transaction and call ourselves again. When it returns
            # we need to restore things back the way they were.
            # We still trace the call in the running transaction
            # though so the fact that it called finish on another
            # request is apparent.

            name = callable_name(wrapped)

            with FunctionTrace(active_transaction, name):
                try:
                    active_transaction.drop_transaction()

                    return _bw_wrapper_RequestHandler_finish_(
                            wrapped, instance, args, kwargs)

                finally:
                    active_transaction.save_transaction()

        else:
            # For this case we just trace the call.

            name = callable_name(wrapped)

            with FunctionTrace(active_transaction, name):
                return wrapped(*args, **kwargs)

    # Attempt to resume the transaction, calling the wrapped method
    # straight away if there isn't one. Otherwise trace the call.

    transaction = resume_request_monitoring(request)

    if transaction is None:
        return wrapped(*args, **kwargs)

    try:
        name = callable_name(wrapped)

        with FunctionTrace(transaction, name):
            result = wrapped(*args, **kwargs)

    except:  # Catch all
        finalize_request_monitoring(request, *sys.exc_info())
        raise

    else:
        if request.connection._request_finished:
            finalize_request_monitoring(request)

        else:
            suspend_request_monitoring(request, name='Request/Output')

        return result

def _bw_wrapper_RequestHandler__generate_headers_(wrapped, instance,
        args, kwargs):

    # The RequestHandler._generate_headers() method is where the
    # response headers are injected into the response being written back
    # to the client. We process the response headers before being sent
    # to capture any details from them, but we also inject our own
    # additional headers for support cross process transactions etc.

    transaction = retrieve_current_transaction()

    if transaction is None:
        return wrapped(*args, **kwargs)

    # Thread utilization doesn't make sense in the context of Cyclone
    # so we need to stop anything being generated for it.

    transaction._thread_utilization_start = None

    if hasattr(instance, 'get_status'):
        status = '%d ???' % instance.get_status()
    else:
        status = '%d ???' % instance._status_code

    try:
        response_headers = instance._headers.get_all()

    except AttributeError:
        try:
            response_headers = itertools.chain(
                    instance._headers.items(),
                    instance._list_headers)

        except AttributeError:
            response_headers = itertools.chain(
                    instance._headers.items(),
                    instance._headers)

    additional_headers = transaction.process_response(
            status, response_headers, *args)

    for name, value in additional_headers:
        instance.add_header(name, value)

    return wrapped(*args, **kwargs)

def _bw_wrapper_RequestHandler_on_connection_close(wrapped, instance,
        args, kwargs):

    # The RequestHandler.on_connection_close() method is called when the
    # client closes the connection prematurely before the request had
    # been completed. The callback itself wasn't registered at a point
    # where there was any request tracking so there shouldn't be any
    # active transaction when this is called. We track the call of the
    # wrapped method and then finalize the whole transaction.

    transaction = retrieve_current_transaction()

    if transaction:
        return wrapped(*args, **kwargs)

    handler = instance
    request = handler.request

    transaction = resume_request_monitoring(request)

    if transaction is None:
        return wrapped(*args, **kwargs)

    name = callable_name(wrapped)

    try:
        with FunctionTrace(transaction, name):
            result = wrapped(*args, **kwargs)

    except:  # Catch all
        finalize_request_monitoring(request, *sys.exc_info())
        raise

    else:
        finalize_request_monitoring(request)

        return result

def _bw_wrapper_RequestHandler___init___(wrapped, instance, args, kwargs):
    # In this case we are actually wrapping the instance method on an
    # actual instance of a handler class rather than the class itself.
    # This is so we can wrap any derived version of this method when
    # it has been overridden in a handler class.

    wrap_function_wrapper(instance, 'on_connection_close',
            _bw_wrapper_RequestHandler_on_connection_close)

    wrap_function_trace(instance, 'prepare')

    if hasattr(instance, 'on_finish'):
        wrap_function_trace(instance, 'on_finish')

    handler = instance

    for name in handler.SUPPORTED_METHODS:
        name = name.lower()
        if hasattr(handler, name):
            wrap_function_trace(instance, name)

    return wrapped(*args, **kwargs)

def instrument_cyclone_web(module):
    wrap_function_wrapper(module, 'Application.__call__',
            _bw_wrapper_Application___call___)

    wrap_function_wrapper(module, 'RequestHandler._handle_request_exception',
            _bw_wrapper_RequestHandler__handle_request_exception_)

    wrap_function_wrapper(module, 'RequestHandler._execute',
             _bw_wrapper_RequestHandler__execute_)

    if hasattr(module.RequestHandler, '_execute_handler'):
        wrap_function_wrapper(module, 'RequestHandler._execute_handler',
                _bw_wrapper_RequestHandler__execute_handler_)

    wrap_function_wrapper(module, 'RequestHandler.finish',
            _bw_wrapper_RequestHandler_finish_)

    if hasattr(module.RequestHandler, '_generate_headers'):

        wrap_function_wrapper(module, 'RequestHandler._generate_headers',
                _bw_wrapper_RequestHandler__generate_headers_)

    wrap_function_wrapper(module, 'RequestHandler.__init__',
            _bw_wrapper_RequestHandler___init___)
