from blueware.agent import (callable_name, current_transaction, 
                    FunctionTrace, FunctionWrapper,wrap_error_trace)
from blueware.hooks.framework_django import should_ignore, wrap_view_handler


def wrap_url_resolver(wrapped):

    # Wrap URL resolver. If resolver returns valid result then
    # wrap the view handler returned. The type of the result
    # changes across Django versions so need to check and adapt
    # as necessary. For a 404 then a user supplied 404 handler
    # or the default 404 handler should get later invoked and
    # transaction should be named after that.

    name = callable_name(wrapped)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        if hasattr(transaction, '_bw_django_url_resolver'):
            return wrapped(*args, **kwargs)

        # Tag the transaction so we know when we are in the top
        # level call to the URL resolver as don't want to show
        # the inner ones as would be one for each url pattern.

        transaction._bw_django_url_resolver = True

        def _wrapped(path):
            # XXX This can raise a Resolver404. If this is not dealt
            # with, is this the source of our unnamed 404 requests.

            with FunctionTrace(transaction, name=name, label=path):
                result = wrapped(path)

                if type(result) == type(()):
                    callback, callback_args, callback_kwargs = result
                    result = (wrap_view_handler(callback, priority=5),
                            callback_args, callback_kwargs)
                else:
                    result.func = wrap_view_handler(result.func, priority=5)

                return result

        try:
            return _wrapped(*args, **kwargs)

        finally:
            del transaction._bw_django_url_resolver

    return FunctionWrapper(wrapped, wrapper)


def wrap_url_resolver_nnn(wrapped, priority=1):

    # Wrapper to be applied to the URL resolver for errors.

    name = callable_name(wrapped)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        with FunctionTrace(transaction, name=name):
            callback, param_dict = wrapped(*args, **kwargs)
            return (wrap_view_handler(callback, priority=priority),
                    param_dict)

    return FunctionWrapper(wrapped, wrapper)

def wrap_url_reverse(wrapped):

    # Wrap the URL resolver reverse lookup. Where the view
    # handler is passed in we need to strip any instrumentation
    # wrapper to ensure that it doesn't interfere with the
    # lookup process. Technically this may now not be required
    # as we have improved the proxying in the object wrapper,
    # but do it just to avoid any potential for problems.

    def wrapper(wrapped, instance, args, kwargs):
        def execute(viewname, *args, **kwargs):
            if hasattr(viewname, '_bw_last_object'):
                viewname = viewname._bw_last_object
            return wrapped(viewname, *args, **kwargs)
        return execute(*args, **kwargs)

    return FunctionWrapper(wrapped, wrapper)

def instrument_django_core_urlresolvers(module):

    # Wrap method which maps a string version of a function
    # name as used in urls.py pattern so can capture any
    # exception which is raised during that process.
    # Normally Django captures import errors at this point
    # and then reraises a ViewDoesNotExist exception with
    # details of the original error and traceback being
    # lost. We thus intercept it here so can capture that
    # traceback which is otherwise lost. Although we ignore
    # a Http404 exception here, it probably is never the
    # case that one can be raised by get_callable().

    wrap_error_trace(module, 'get_callable', ignore_errors=should_ignore)

    # Wrap methods which resolves a request to a view handler.
    # This can be called against a resolver initialised against
    # a custom URL conf associated with a specific request, or a
    # resolver which uses the default URL conf.

    module.RegexURLResolver.resolve = wrap_url_resolver(
            module.RegexURLResolver.resolve)

    # Wrap methods which resolve error handlers. For 403 and 404
    # we give these higher naming priority over any prior
    # middleware or view handler to give them visibility. For a
    # 500, which will be triggered for unhandled exception, we
    # leave any original name derived from a middleware or view
    # handler in place so error details identify the correct
    # transaction.

    if hasattr(module.RegexURLResolver, 'resolve403'):
        module.RegexURLResolver.resolve403 = wrap_url_resolver_nnn(
                module.RegexURLResolver.resolve403, priority=3)

    if hasattr(module.RegexURLResolver, 'resolve404'):
        module.RegexURLResolver.resolve404 = wrap_url_resolver_nnn(
                module.RegexURLResolver.resolve404, priority=3)

    if hasattr(module.RegexURLResolver, 'resolve500'):
        module.RegexURLResolver.resolve500 = wrap_url_resolver_nnn(
                module.RegexURLResolver.resolve500, priority=1)

    if hasattr(module.RegexURLResolver, 'resolve_error_handler'):
        module.RegexURLResolver.resolve_error_handler = wrap_url_resolver_nnn(
                module.RegexURLResolver.resolve_error_handler, priority=1)

    # Wrap function for performing reverse URL lookup to strip any
    # instrumentation wrapper when view handler is passed in.

    module.reverse = wrap_url_reverse(module.reverse)
