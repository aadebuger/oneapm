from blueware.agent import (current_transaction, wrap_wsgi_application,
            wrap_function_trace,wrap_transaction_name, wrap_function_wrapper,
            callable_name, FunctionTrace)


IGNORE_TRANSACTION_LIST = ['/longpolling/poll']


class _WSGIApplicationIterable(object):

    def __init__(self, transaction, generator):
        self.transaction = transaction
        self.generator = generator

    def __iter__(self):
        try:
            with FunctionTrace(self.transaction, name='Response',
                    group='Python/WSGI'):
                for item in self.generator:
                    yield item

        except GeneratorExit:
            raise

        except: # Catch all
            self.transaction.record_exception()
            raise

    def close(self):
        try:
            with FunctionTrace(self.transaction, name='Finalize',
                    group='Python/WSGI'):
                if hasattr(self.generator, 'close'):
                    name = callable_name(self.generator.close)
                    with FunctionTrace(self.transaction, name):
                        self.generator.close()

        except: # Catch all
            self.transaction.record_exception()
            raise


class _WSGIApplication(object):

    def __init__(self, wsgi_application):
        self.wsgi_application = wsgi_application

    def __call__(self, environ, start_response):

        # Should ignore transaction here because this is the outter wrapper of 
        # wsgi application, which means there is no transaction associate with
        # current request was initialized or activated at this point.
        if environ.get('PATH_INFO', '') in IGNORE_TRANSACTION_LIST:
            environ['blueware.ignore_transaction'] = True

        transaction = current_transaction(active_only=False)
        # At this point, no transaction has been initialized or activated.
        if transaction is None:
            return self.wsgi_application(environ, start_response)

        name = callable_name(self.wsgi_application)

        with FunctionTrace(transaction, name='Application',
                group='Python/WSGI'):
            with FunctionTrace(transaction, name=name):
                result = self.wsgi_application(environ, start_response)

        return _WSGIApplicationIterable(transaction, result)


def _bw_wrapper_applictation(wrapped, instance, *args, **kwargs):
    # The params is always values like below
    # wrapped : application
    # instance: None
    # args    : ((environ, start_response), {})
    # kwargs  : {}
    return _WSGIApplication(wrapped)(*args[0])

def instrument_openerp_service_wsgi_server(module):

    # Wrap wsgi application.
    wrap_wsgi_application(module, 'application')

    # Before the wrapped wsgi application called , filter the longpolling
    # request which correspond to url /longpolling/poll by set the environ 
    # value blueware.ignore_transaction to True to ignore this transaction.
    wrap_function_wrapper(module, 'application', _bw_wrapper_applictation)

def instrument_openerp_http(module):

    # Wrap the correspond dispatch function for request.
    # At this point the url and function info has bind to an endpoint.
    # The name used as web transaction is the path to the function.
    def transaction_httprequest_dispatch(instance, *args, **kwargs):
        return '{0}:{1}'.format(
                callable_name(instance.endpoint.method),
                instance.httprequest.method)
    wrap_transaction_name(module, 'HttpRequest.dispatch',
            name=transaction_httprequest_dispatch,
            group='Python/OpenERP')

    def transaction_jsonrequest_dispatch(instance, *args, **kwargs):
        return '{0}:{1}'.format(
                callable_name(instance.endpoint.method),
                instance.httprequest.method)
    wrap_transaction_name(module, 'JsonRequest.dispatch',
            name=transaction_jsonrequest_dispatch,
            group='Python/OpenERP')

    # Wrap functions which coordinate the execution of the request 
    # initial phase. This is for timing how long this phase take.
    # This phase only execute once.
    # NOTICE: this is not captured due to the unkown bug that some of the
    # first request data was not captured.
    wrap_function_trace(module, 'Root.load_addons',
            group='Fixture/Execute')

    # Wrap functions which coordinate the execution of the different phases
    # of the request handling. This is for timing how long these phases take.
    wrap_function_trace(module, 'Root.setup_session',
            group='Python/OpenERP')

    wrap_function_trace(module, 'Root.setup_db',
            group='Python/OpenERP')

    wrap_function_trace(module, 'Root.setup_lang',
            group='Python/OpenERP')

    wrap_function_trace(module, 'WebRequest._call_function',
            group='Python/OpenERP')

    wrap_function_trace(module, 'Response.render',
            group='Python/OpenERP')


def instrument_openerp_modules_registry(module):

    # NOTICE: this is not captured due to the unkown bug that some of the
    # first request data was not captured.
    wrap_function_trace(module, 'RegistryManager.new',
            group='Fixture/Create')
