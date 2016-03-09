import logging
import sys
import weakref

from blueware.agent import (application, update_wrapper,
                            WebTransaction, current_transaction, FunctionTrace)

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
        self._bw_instance._bw_request_finished = False
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

            if self._bw_instance._bw_request_finished:
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

def instrument_twisted_web_server(module):
    module.Request.process = RequestProcessWrapper(module.Request.process)
