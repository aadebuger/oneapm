import sys
import logging
import UserList
from blueware.agent import (FunctionTraceWrapper, update_wrapper,
                            current_transaction, ErrorTrace, FunctionTrace)


_logger = logging.getLogger(__name__)

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

        if hasattr(transaction, '_bw_current_request') and transaction._bw_current_request is not None:
            request = transaction._bw_current_request()
        else:
            request = None

        if request is None:
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

            if request._bw_request_finished:
                transaction.__exit__(None, None, None)
                self._bw_instance._bw_transaction = None

            else:
                # XXX Should we be removing the transaction from the
                # deferred object as well. Can the same deferred be
                # called multiple times for same request. It probably
                # can be reregistered.

                request._bw_wait_function_trace = FunctionTrace(transaction,
                                                                name='Deferred/Wait',
                                                                group='Python/Twisted')

                request._bw_wait_function_trace.__enter__()
                transaction.drop_transaction()

            request._bw_is_deferred_callback = False

def instrument_twisted_internet_defer(module):
    module.Deferred.__init__ = DeferredWrapper(module.Deferred.__init__)
    module.Deferred._runCallbacks = DeferredCallbacksWrapper(module.Deferred._runCallbacks)

    #_inlineCallbacks = module.inlineCallbacks
    #def inlineCallbacks(f):
    #    return _inlineCallbacks(InlineCallbacksWrapper(f))
    #module.inlineCallbacks = inlineCallbacks
