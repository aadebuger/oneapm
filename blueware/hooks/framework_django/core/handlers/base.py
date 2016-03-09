from blueware.agent import (wrap_post_function, callable_name, current_transaction, 
                    WSGIApplicationWrapper, FunctionTrace, FunctionWrapper, insert_html_snippet)
from blueware.packages import six
import threading
from blueware.hooks.framework_django import django_settings, _logger

middleware_instrumentation_lock = threading.Lock()

def browser_timing_middleware(request, response):

    # Don't do anything if receive a streaming response which
    # was introduced in Django 1.5. Need to avoid this as there
    # will be no 'content' attribute. Alternatively there may be
    # a 'content' attribute which flattens the stream, which if
    # we access, will break the streaming and/or buffer what is
    # potentially a very large response in memory contrary to
    # what user wanted by explicitly using a streaming response
    # object in the first place. To preserve streaming but still
    # do RUM insertion, need to move to a WSGI middleware and
    # deal with how to update the content length.

    if hasattr(response, 'streaming_content'):
        return response

    # Need to be running within a valid web transaction.

    transaction = current_transaction()

    if not transaction:
        return response

    # Only insert RUM JavaScript headers and footers if enabled
    # in configuration and not already likely inserted.

    if not transaction.settings.browser_monitoring.enabled:
        return response

    if transaction.autorum_disabled:
        return response

    if not django_settings.browser_monitoring.transform:
        return response

    if transaction.rum_header_generated:
        return response

    # Only possible if the content type is one of the allowed
    # values. Normally this is just text/html, but optionally
    # could be defined to be list of further types. For example
    # a user may want to also perform insertion for
    # 'application/xhtml+xml'.

    ctype = response.get('Content-Type', '').lower().split(';')[0]

    if ctype not in transaction.settings.browser_monitoring.content_type:
        return response

    # Don't risk it if content encoding already set.

    if response.has_header('Content-Encoding'):
        return response

    # Don't risk it if content is actually within an attachment.

    cdisposition = response.get('Content-Disposition', '').lower()

    if cdisposition.split(';')[0].strip().lower() == 'attachment':
        return response

    # No point continuing if header is empty. This can occur if
    # RUM is not enabled within the UI. It is assumed at this
    # point that if header is not empty, then footer will not be
    # empty. We don't want to generate the footer just yet as
    # want to do that as late as possible so that application
    # server time in footer is as accurate as possible. In
    # particular, if the response content is generated on demand
    # then the flattening of the response could take some time
    # and we want to track that. We thus generate footer below
    # at point of insertion.

    header = transaction.browser_timing_header()

    if not header:
        return response

    def html_to_be_inserted():
        return six.b(header) + six.b(transaction.browser_timing_footer())

    # Make sure we flatten any content first as it could be
    # stored as a list of strings in the response object. We
    # assign it back to the response object to avoid having
    # multiple copies of the string in memory at the same time
    # as we progress through steps below.

    result = insert_html_snippet(response.content, html_to_be_inserted)

    if result is not None:
        if transaction.settings.debug.log_autorum_middleware:
            _logger.debug('RUM insertion from Django middleware '
                    'triggered. Bytes added was %r.',
                    len(result) - len(response.content))

        response.content = result

        if response.get('Content-Length', None):
            response['Content-Length'] = str(len(response.content))

    return response

def register_browser_timing_middleware(middleware):

    # Inserts our middleware for inserting the RUM header and
    # footer into the list of middleware. Must check for certain
    # types of middleware which modify content as must always
    # come before them. Otherwise is added last so that comes
    # after any caching middleware. If don't do that then the
    # inserted header and footer will end up being cached and
    # then when served up from cache we would add a second
    # header and footer, something we don't want.

    content_type_modifying_middleware = [
        'django.middleware.gzip:GZipMiddleware.process_response'
    ]

    for i in range(len(middleware)):
        function = middleware[i]
        name = callable_name(function)
        if name in content_type_modifying_middleware:
            middleware.insert(i, browser_timing_middleware)
            break
    else:
        middleware.append(browser_timing_middleware)

def wrap_leading_middleware(middleware):

    # Wrapper to be applied to middleware executed prior to the
    # view handler being executed. Records the time spent in the
    # middleware as separate function node and also attempts to
    # name the web transaction after the name of the middleware
    # with success being determined by the priority.

    def wrapper(wrapped):
        # The middleware if a class method would already be
        # bound at this point, so is safe to determine the name
        # when it is being wrapped rather than on each
        # invocation.

        name = callable_name(wrapped)

        def wrapper(wrapped, instance, args, kwargs):
            transaction = current_transaction()

            if transaction is None:
                return wrapped(*args, **kwargs)

            before = (transaction.name, transaction.group)

            with FunctionTrace(transaction, name=name):
                try:
                    return wrapped(*args, **kwargs)

                finally:
                    # We want to name the transaction after this
                    # middleware but only if the transaction wasn't
                    # named from within the middleware itself explicity.

                    after = (transaction.name, transaction.group)
                    if before == after:
                        transaction.set_transaction_name(name, priority=2)

        return FunctionWrapper(wrapped, wrapper)

    for wrapped in middleware:
        yield wrapper(wrapped)

def wrap_trailing_middleware(middleware):

    # Wrapper to be applied to trailing middleware executed
    # after the view handler. Records the time spent in the
    # middleware as separate function node. Transaction is never
    # named after these middleware.

    def wrapper(wrapped):
        # The middleware if a class method would already be
        # bound at this point, so is safe to determine the name
        # when it is being wrapped rather than on each
        # invocation.

        name = callable_name(wrapped)

        def wrapper(wrapped, instance, args, kwargs):
            transaction = current_transaction()

            if transaction is None:
                return wrapped(*args, **kwargs)

            with FunctionTrace(transaction, name=name):
                return wrapped(*args, **kwargs)

        return FunctionWrapper(wrapped, wrapper)

    for wrapped in middleware:
        yield wrapper(wrapped)

def insert_and_wrap_middleware(handler, *args, **kwargs):

    # Use lock to control access by single thread but also as
    # flag to indicate if done the initialisation. Lock will be
    # None if have already done this.

    global middleware_instrumentation_lock

    if not middleware_instrumentation_lock:
        return

    lock = middleware_instrumentation_lock

    lock.acquire()

    # Check again in case two threads grab lock at same time.

    if not middleware_instrumentation_lock:
        lock.release()
        return

    # Set lock to None so we know have done the initialisation.

    middleware_instrumentation_lock = None

    try:
        # For response middleware, need to add in middleware for
        # automatically inserting RUM header and footer. This is
        # done first which means it gets wrapped and timed as
        # well. Will therefore show in traces however that may
        # be beneficial as highlights we are doing some magic
        # and can see if it is taking too long on large
        # responses.

        if hasattr(handler, '_response_middleware'):
            register_browser_timing_middleware(handler._response_middleware)

        # Now wrap the middleware to undertake timing and name
        # the web transaction. The naming is done as lower
        # priority than that for view handler so view handler
        # name always takes precedence.

        if hasattr(handler, '_request_middleware'):
            handler._request_middleware = list(
                    wrap_leading_middleware(
                    handler._request_middleware))

        if hasattr(handler, '_view_middleware'):
            handler._view_middleware = list(
                    wrap_leading_middleware(
                    handler._view_middleware))

        if hasattr(handler, '_template_response_middleware'):
            handler._template_response_middleware = list(
                  wrap_trailing_middleware(
                  handler._template_response_middleware))

        if hasattr(handler, '_response_middleware'):
            handler._response_middleware = list(
                    wrap_trailing_middleware(
                    handler._response_middleware))

        if hasattr(handler, '_exception_middleware'):
            handler._exception_middleware = list(
                    wrap_trailing_middleware(
                    handler._exception_middleware))

    finally:
        lock.release()

def instrument_django_core_handlers_base(module):

    # Attach a post function to load_middleware() method of
    # BaseHandler to trigger insertion of browser timing
    # middleware and wrapping of middleware for timing etc.

    wrap_post_function(module, 'BaseHandler.load_middleware',
            insert_and_wrap_middleware)
