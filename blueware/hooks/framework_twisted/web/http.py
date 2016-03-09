import logging
import sys
from blueware.agent import (update_wrapper, current_transaction, FunctionTrace)


_logger = logging.getLogger(__name__)

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

    def __call__(self, *args):
        if len(args) == 1:
            self._bw_instance = args[0]

        assert self._bw_instance != None

        # Call finish() method straight away if request is not even
        # associated with a transaction.

        if not hasattr(self._bw_instance, '_bw_transaction'):
            return self._bw_next_object(*args)

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

        self._bw_instance._bw_request_finished = True

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
                    result = self._bw_next_object(*args)

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
                    result = self._bw_next_object(*args)

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
                result = self._bw_next_object(*args)

        return result

def instrument_twisted_web_http(module):
    module.Request.finish = RequestFinishWrapper(module.Request.finish)
