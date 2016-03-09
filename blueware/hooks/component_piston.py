import types

import blueware.packages.six as six

from blueware.agent import (current_transaction, FunctionTrace, callable_name,
                            wrap_object, wrap_in_function)

class MethodWrapper(object):

    def __init__(self, wrapped, priority=None):
        self._bw_name = callable_name(wrapped)
        self._bw_wrapped = wrapped
        self._bw_priority = priority

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self._bw_wrapped.__get__(instance, klass)
        return self.__class__(descriptor)

    def __getattr__(self, name):
        return getattr(self._bw_wrapped, name)

    def __call__(self, *args, **kwargs):
        transaction = current_transaction()
        if transaction:
            transaction.set_transaction_name(self._bw_name,
                    priority=self._bw_priority)
            with FunctionTrace(transaction, name=self._bw_name):
                return self._bw_wrapped(*args, **kwargs)
        else:
            return self._bw_wrapped(*args, **kwargs)

class ResourceInitWrapper(object):

    def __init__(self, wrapped):
        if isinstance(wrapped, tuple):
            (instance, wrapped) = wrapped
        else:
            instance = None
        self.__instance = instance
        self._bw_wrapped = wrapped

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self._bw_wrapped.__get__(instance, klass)
        return self.__class__((instance, descriptor))

    def __getattr__(self, name):
        return getattr(self._bw_wrapped, name)

    def __call__(self, *args, **kwargs):
        self._bw_wrapped(*args, **kwargs)
        handler = self.__instance.handler
        for name in six.itervalues(self.__instance.callmap):
            if hasattr(handler, name):
                setattr(handler, name, MethodWrapper(
                        getattr(handler, name), priority=6))

def instrument_piston_resource(module):

    wrap_object(module, 'Resource.__init__', ResourceInitWrapper)

def instrument_piston_doc(module):

    def in_HandlerMethod_init(self, method, *args, **kwargs):
        if isinstance(method, MethodWrapper):
            method = method._bw_wrapped
        return ((self, method) + args, kwargs)

    wrap_in_function(module, 'HandlerMethod.__init__', in_HandlerMethod_init)
