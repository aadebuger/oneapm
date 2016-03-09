import logging
import sys
import weakref
import UserList

from blueware.agent import (application, update_wrapper, callable_name,
                            current_transaction, WebTransaction, FunctionTrace,
                            FunctionTraceWrapper, ErrorTrace)

_logger = logging.getLogger(__name__)

class RequestProcessWrapper(object):

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

    def __call__(self):
        assert self._bw_instance != None

        transaction = current_transaction()

        # Check to see if we are being called within the context of any
        # sort of transaction. If we are, then we don't bother doing
        # anything and just call the wrapped function. This should not
        # really ever occur with Twisted.Web wrapper but check anyway.

        if transaction:
            return self._bw_next_object()

        # Always use the default application specified in the agent
        # configuration.

        app = application()

        # We need to fake up a WSGI like environ dictionary with the key
        # bits of information we need.

        environ = {}

        environ['REQUEST_URI'] = self._bw_instance.path

        # Now start recording the actual web transaction.

        transaction = WebTransaction(app, environ)

        if not transaction.enabled:
            return self._bw_next_object()

        transaction.__enter__()

        self._bw_instance._bw_transaction = transaction

        self._bw_instance._bw_is_deferred_callback = False
        self._bw_instance._bw_is_request_finished = False
        self._bw_instance._bw_wait_function_trace = None

        # We need to add a reference to the Twisted.Web request object
        # in the transaction as only able to stash the transaction in a
        # deferred. Need to use a weakref to avoid an object cycle which
        # may prevent cleanup of transaction.

        transaction._bw_current_request = weakref.ref(self._bw_instance)

        try:
            # Call the original method in a trace object to give better
            # context in transaction traces. Three things can happen
            # within this call. The render() function which is in turn
            # called can return a result immediately which means user
            # code should have called finish() on the request, it can
            # raise an exception which is caught in process() function
            # where error handling calls finish(), or it can return that
            # it is not done yet and register deferred callbacks to
            # complete the request.

            with FunctionTrace(transaction,
                    name='Request/Process', group='Python/Twisted'):
                result = self._bw_next_object()

            # In the case of a result having being returned or an
            # exception occuring, then finish() will have been called.
            # We can't just exit the transaction in the finish call
            # however as need to still pop back up through the above
            # function trace. So if flagged that have finished, then we
            # exit the transaction here. Otherwise we setup a function
            # trace to track wait time for deferred and manually pop the
            # transaction as being the current one for this thread.

            if self._bw_instance._bw_is_request_finished:
                transaction.__exit__(None, None, None)
                self._bw_instance._bw_transaction = None
                self._bw_instance = None

            else:
                self._bw_instance._bw_wait_function_trace = \
                        FunctionTrace(
                        transaction, name='Deferred/Wait',
                        group='Python/Twisted')

                self._bw_instance._bw_wait_function_trace.__enter__()
                transaction.drop_transaction()

        except:  # Catch all
            # If an error occurs assume that transaction should be
            # exited. Technically don't believe this should ever occur
            # unless our code here has an error or Twisted.Web is
            # broken.

            _logger.exception('Unexpected exception raised by Twisted.Web '
                    'Request.process() exception.')

            transaction.__exit__(*sys.exc_info())
            self._bw_instance._bw_transaction = None
            self._bw_instance = None

            raise

        return result

class RequestFinishWrapper(object):

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

    def __call__(self):
        assert self._bw_instance != None

        # Call finish() method straight away if request is not even
        # associated with a transaction.

        if not hasattr(self._bw_instance, '_bw_transaction'):
            return self._bw_next_object()

        # Technically we should only be able to be called here without
        # an active transaction if we are in the wait state. If we
        # are called in context of original request process() function
        # or a deferred the transaction should already be registered.

        transaction = self._bw_instance._bw_transaction

        if self._bw_instance._bw_wait_function_trace:
            if current_transaction():
                _logger.debug('The Twisted.Web request finish() method is '
                        'being called while in wait state but there is '
                        'already a current transaction.')
            else:
                transaction.save_transaction()

        elif not current_transaction():
            _logger.debug('The Twisted.Web request finish() method is '
                    'being called from request process() method or a '
                    'deferred but there is not a current transaction.')

        # Except for case of being called when in wait state, we can't
        # actually exit the transaction at this point as may be called
        # in context of an outer function trace node. We thus flag that
        # are finished and pop back out allowing outer scope to actually
        # exit the transaction.

        self._bw_instance._bw_is_request_finished = True

        # Now call the original finish() function.

        if self._bw_instance._bw_is_deferred_callback:

            # If we are in a deferred callback log any error against the
            # transaction here so we know we will capture it. We
            # possibly don't need to do it here as outer scope may catch
            # it anyway. Duplicate will be ignored so not too important.
            # Most likely the finish() call would never fail anyway.

            try:
                with FunctionTrace(transaction,
                        name='Request/Finish', group='Python/Twisted'):
                    result = self._bw_next_object()

            except:  # Catch all
                transaction.record_exception(*sys.exc_info())
                raise

        elif self._bw_instance._bw_wait_function_trace:

            # Now handle the special case where finish() was called
            # while in the wait state. We might get here through
            # Twisted.Web itself somehow calling finish() when still
            # waiting for a deferred. If this were to occur though then
            # the transaction will not be popped if we simply marked
            # request as finished as no outer scope to see that and
            # clean up. We will thus need to end the function trace and
            # exit the transaction. We end function trace here and then
            # the transaction down below.

            try:
                self._bw_instance._bw_wait_function_trace.__exit__(
                        None, None, None)

                with FunctionTrace(transaction,
                        name='Request/Finish', group='Python/Twisted'):
                    result = self._bw_next_object()

                transaction.__exit__(None, None, None)

            except:  # Catch all
                transaction.__exit__(*sys.exc_info())
                raise

            finally:
                self._bw_instance._bw_wait_function_trace = None
                self._bw_instance._bw_transaction = None
                self._bw_instance = None

        else:
            # This should be the case where finish() is being called in
            # the original render() function.

            with FunctionTrace(transaction,
                    name='Request/Finish', group='Python/Twisted'):
                result = self._bw_next_object()

        return result

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

class DeferredUserList(UserList.UserList):

    def pop(self, i=-1):
        import twisted.internet.defer
        item = super(DeferredUserList, self).pop(i)

        item0 = item[0]
        item1 = item[1]

        if item0[0] != twisted.internet.defer._CONTINUE:
            item0 = (FunctionTraceWrapper(
                     item0[0], group='Python/Twisted/Callback'),
                     item0[1], item0[2])

        if item1[0] != twisted.internet.defer._CONTINUE:
            item1 = (FunctionTraceWrapper(
                     item1[0], group='Python/Twisted/Errback'),
                     item1[1], item1[2])

        return (item0, item1)

class DeferredWrapper(object):

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

    def __call__(self, *args, **kwargs):

        # This is wrapping the __init__() function so call that first.

        self._bw_next_object(*args, **kwargs)

        # We now wrap the list of deferred callbacks so can track when
        # each callback is actually called.

        if self._bw_instance:
            transaction = current_transaction()
            if transaction:
                self._bw_instance._bw_transaction = transaction
                self._bw_instance.callbacks = DeferredUserList(
                        self._bw_instance.callbacks)

class DeferredCallbacksWrapper(object):

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

    def __call__(self):
        assert self._bw_instance != None

        transaction = current_transaction()

        # If there is an active transaction then deferred is being
        # called within a context of another deferred so simply call the
        # callback and return.

        if transaction:
            return self._bw_next_object()

        # If there is no transaction recorded against the deferred then
        # don't need to do anything and can simply call the callback and
        # return.

        if not hasattr(self._bw_instance, '_bw_transaction'):
            return self._bw_next_object()

        transaction = self._bw_instance._bw_transaction

        # If we can't find a Twisted.Web request object associated with
        # the transaction or it is no longer valid then simply call the
        # callback and return.

        if not hasattr(transaction, '_bw_current_request'):
            return self._bw_next_object()

        request = transaction._bw_current_request()

        if not request:
            return self._bw_next_object()

        try:
            # Save the transaction recorded against the deferred as the
            # active transaction.

            transaction.save_transaction()

            # Record that are calling a deferred. This changes what we
            # do if the request finish() method is being called.

            request._bw_is_deferred_callback = True

            # We should always be calling into a deferred when we are
            # in the wait state for the request. We need to exit that
            # wait state.

            if request._bw_wait_function_trace:
                request._bw_wait_function_trace.__exit__(None, None, None)
                request._bw_wait_function_trace = None

            else:
                _logger.debug('Called a Twisted.Web deferred when we were '
                        'not in a wait state.')

            # Call the deferred and capture any errors that may come
            # back from it.

            with ErrorTrace(transaction):
                with FunctionTrace(
                        transaction, name='Deferred/Call',
                        group='Python/Twisted'):
                    return self._bw_next_object()

        finally:
            # If the request finish() method was called from the
            # deferred then we need to exit the transaction. Other wise
            # we need to create a new function trace node for a new wait
            # state and pop the transaction.

            if request._bw_is_request_finished:
                transaction.__exit__(None, None, None)
                self._bw_instance._bw_transaction = None

            else:
                # XXX Should we be removing the transaction from the
                # deferred object as well. Can the same deferred be
                # called multiple times for same request. It probably
                # can be reregistered.

                request._bw_wait_function_trace = \
                        FunctionTrace(
                        transaction, name='Deferred/Wait',
                        group='Python/Twisted')

                request._bw_wait_function_trace.__enter__()
                transaction.drop_transaction()

            request._bw_is_deferred_callback = False

class InlineGeneratorWrapper(object):

    def __init__(self, wrapped, generator):
        self._bw_wrapped = wrapped
        self._bw_generator = generator

    def __iter__(self):
        name = callable_name(self._bw_wrapped)
        iterable = iter(self._bw_generator)
        while 1:
            transaction = current_transaction()
            with FunctionTrace(
                  transaction, name, group='Python/Twisted/Generator'):
                yield next(iterable)

class InlineCallbacksWrapper(object):

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

    def __call__(self, *args, **kwargs):
        transaction = current_transaction()

        if not transaction:
            return self._bw_next_object(*args, **kwargs)

        result = self._bw_next_object(*args, **kwargs)

        if not result:
            return result

        return iter(InlineGeneratorWrapper(self._bw_next_object, result))

def instrument_twisted_web_server(module):
    module.Request.process = RequestProcessWrapper(module.Request.process)

def instrument_twisted_web_http(module):
    module.Request.finish = RequestFinishWrapper(module.Request.finish)

def instrument_twisted_web_resource(module):
    module.Resource.render = ResourceRenderWrapper(module.Resource.render)

def instrument_twisted_internet_defer(module):
    module.Deferred.__init__ = DeferredWrapper(module.Deferred.__init__)
    module.Deferred._runCallbacks = DeferredCallbacksWrapper(
            module.Deferred._runCallbacks)

    #_inlineCallbacks = module.inlineCallbacks
    #def inlineCallbacks(f):
    #    return _inlineCallbacks(InlineCallbacksWrapper(f))
    #module.inlineCallbacks = inlineCallbacks
