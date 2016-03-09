import sys
import types
import time

import blueware.core.solr_node

import blueware.api.transaction
import blueware.api.time_trace
from ..common.object_wrapper import update_wrapper, wrap_object

class SolrTrace(blueware.api.time_trace.TimeTrace):

    node = blueware.core.solr_node.SolrNode

    def __init__(self, transaction, library, command):
        super(SolrTrace, self).__init__(transaction)

        self.library = library
        self.command = command

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, dict(
                library=self.library, command=self.command))

    def create_node(self):
        return self.node(library=self.library, command=self.command,
                children=self.children, start_time=self.start_time,
                end_time=self.end_time, duration=self.duration,
                exclusive=self.exclusive)

    def terminal_node(self):
        return True

class SolrTraceWrapper(object):

    def __init__(self, wrapped, library, command):
        if isinstance(wrapped, tuple):
            (instance, wrapped) = wrapped
        else:
            instance = None

        update_wrapper(self, wrapped)

        self._bw_instance = instance
        self._bw_next_object = wrapped

        if not hasattr(self, '_bw_last_object'):
            self._bw_last_object = wrapped

        self._bw_library = library
        self._bw_command = command

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self._bw_next_object.__get__(instance, klass)
        return self.__class__((instance, descriptor), self._bw_library,
                              self._bw_command)

    def __call__(self, *args, **kwargs):
        transaction = blueware.api.transaction.current_transaction()
        if not transaction:
            return self._bw_next_object(*args, **kwargs)

        if callable(self._bw_library):
            if self._bw_instance is not None:
                library = self._bw_library(self._bw_instance, *args,
                                           **kwargs)
            else:
                library = self._bw_library(*args, **kwargs)
        else:
            library = self._bw_library

        if callable(self._bw_command):
            if self._bw_instance is not None:
                command = self._bw_command(self._bw_instance, *args,
                                           **kwargs)
            else:
                command = self._bw_command(*args, **kwargs)
        else:
            command = self._bw_command

        with SolrTrace(transaction, library, command):
            return self._bw_next_object(*args, **kwargs)

def solr_trace(library, command):
    def decorator(wrapped):
        return SolrTraceWrapper(wrapped, library, command)
    return decorator

def wrap_solr_trace(module, object_path, library, command):
    wrap_object(module, object_path, SolrTraceWrapper, (library, command))
