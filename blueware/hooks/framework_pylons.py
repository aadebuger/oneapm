import sys
import types

from blueware.agent import (current_transaction, wrap_object, wrap_transaction_name,
                            wrap_function_trace, wrap_error_trace, callable_name, import_module)

def name_controller(self, environ, start_response):
    action = environ['pylons.routes_dict']['action']
    return "%s.%s" % (callable_name(self), action)

class capture_error(object):
    def __init__(self, wrapped):
        if isinstance(wrapped, tuple):
            (instance, wrapped) = wrapped
        else:
            instance = None
        self.__instance = instance
        self.__wrapped = wrapped

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self.__wrapped.__get__(instance, klass)
        return self.__class__((instance, descriptor))

    def __call__(self, *args, **kwargs):
        transaction = current_transaction()
        if transaction:
            webob_exc = import_module('webob.exc')
            try:
                return self.__wrapped(*args, **kwargs)
            except webob_exc.HTTPException:
                raise
            except:  # Catch all
                transaction.record_exception(*sys.exc_info())
                raise
        else:
            return self.__wrapped(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.__wrapped, name)

def instrument(module):

    if module.__name__ == 'pylons.wsgiapp':
        wrap_error_trace(module, 'PylonsApp.__call__')

    elif module.__name__ == 'pylons.controllers.core':
        wrap_transaction_name(module, 'WSGIController.__call__', name_controller)
        wrap_function_trace( module, 'WSGIController.__call__')

        def name_WSGIController_perform_call(self, func, args):
            return callable_name(func)

        wrap_function_trace(module, 'WSGIController._perform_call',
                            name_WSGIController_perform_call)
        wrap_object(module, 'WSGIController._perform_call', capture_error)

    elif module.__name__ == 'pylons.templating':

        wrap_function_trace(module, 'render_genshi')
        wrap_function_trace(module, 'render_mako')
        wrap_function_trace(module, 'render_jinja2')
