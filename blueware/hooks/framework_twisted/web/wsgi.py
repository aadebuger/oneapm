from blueware.agent import (wrap_function_wrapper, FunctionTrace, callable_name,
                            current_transaction)

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
        transaction = current_transaction()

        if transaction is None:
            return self.wsgi_application(environ, start_response)

        name = callable_name(self.wsgi_application)

        with FunctionTrace(transaction, name='Application',
                group='Python/WSGI'):
            with FunctionTrace(transaction, name=name):
                result = self.wsgi_application(environ, start_response)

        return _WSGIApplicationIterable(transaction, result)

def _bw_wrapper_WSGIResource___init___(wrapped, instance, args, kwargs):

    def _params(reactor, threadpool, wsgi_application, *args, **kwargs):
        return reactor, threadpool, wsgi_application

    reactor, threadpool, wsgi_application = _params(*args, **kwargs)
    wsgi_application = _WSGIApplication(wsgi_application)

    return wrapped(reactor, threadpool, wsgi_application)

def instrument_twisted_web_wsgi(module):

    wrap_function_wrapper(module, 'WSGIResource.__init__',
        _bw_wrapper_WSGIResource___init___)
