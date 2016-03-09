import sys
import threading
import logging
import functools

from blueware.packages import six

from blueware.agent import (callable_name, extra_settings, current_transaction, 
                    FunctionTrace, FunctionWrapper,wrap_error_trace, ignore_status_code)

_logger = logging.getLogger(__name__)

_boolean_states = {
   '1': True, 'yes': True, 'true': True, 'on': True,
   '0': False, 'no': False, 'false': False, 'off': False
}

def _setting_boolean(value):
    if value.lower() not in _boolean_states:
        raise ValueError('Not a boolean: %s' % value)
    return _boolean_states[value.lower()]

def _setting_set(value):
    return set(value.split())

_settings_types = {
    'browser_monitoring.transform': _setting_boolean,
    'instrumentation.templates.inclusion_tag' : _setting_set,
    'instrumentation.background_task.startup_timeout': float,
    'instrumentation.scripts.django_admin' : _setting_set,
}

_settings_defaults = {
    'browser_monitoring.transform': True,
    'instrumentation.templates.inclusion_tag': set(),
    'instrumentation.background_task.startup_timeout': 10.0,
    'instrumentation.scripts.django_admin' : set(),
}

django_settings = extra_settings('import-hook:django',
        types=_settings_types, defaults=_settings_defaults)

def should_ignore(exc, value, tb):
    from django.http import Http404

    if isinstance(value, Http404):
        if ignore_status_code(404):
            return True

def wrap_view_handler(wrapped, priority=3):

    # Ensure we don't wrap the view handler more than once. This
    # looks like it may occur in cases where the resolver is
    # called recursively. We flag that view handler was wrapped
    # using the '_bw_django_view_handler' attribute.

    if hasattr(wrapped, '_bw_django_view_handler'):
        return wrapped

    name = callable_name(wrapped)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        transaction.set_transaction_name(name, priority=priority)

        with FunctionTrace(transaction, name=name):
            try:
                return wrapped(*args, **kwargs)

            except:  # Catch all
                transaction.record_exception(ignore_errors=should_ignore)
                raise

    result = FunctionWrapper(wrapped, wrapper)
    result._bw_django_view_handler = True

    return result
