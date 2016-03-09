from blueware.agent import (update_wrapper, callable_name, 
							current_transaction, FunctionTrace)
class ResourceRenderWrapper(object):

    def __init__(self, wrapped):
        if isinstance(wrapped, tuple):
            (instance, wrapped) = wrapped
        else:
            instance = None

        update_wrapper(self, wrapped)

        self._bw_instance = instance
        self._bw_next_object = wrapped

        if not hasattr(self, '_bw_last_object'):
            self._bw_last_object = wrapped

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self._bw_next_object.__get__(instance, klass)
        return self.__class__((instance, descriptor))

    def __call__(self, *args):

        # Temporary work around due to customer calling class method
        # directly with 'self' as first argument. Need to work out best
        # practice for dealing with this.

        if len(args) == 2:
            # Assume called as unbound method with (self, request).
            instance, request = args
        else:
            # Assume called as bound method with (request).
            instance = self._bw_instance
            request = args[-1]

        assert instance != None

        transaction = current_transaction()

        if transaction is None:
            return self._bw_next_object(*args)

        # This is wrapping the render() function of the resource. We
        # name the function node and the web transaction after the name
        # of the handler function augmented with the method type for the
        # request.

        name = "%s.render_%s" % (
                callable_name(
                instance), request.method)
        transaction.set_transaction_name(name, priority=1)

        with FunctionTrace(transaction, name):
            return self._bw_next_object(*args)

def instrument_twisted_web_resource(module):
    module.Resource.render = ResourceRenderWrapper(module.Resource.render)
