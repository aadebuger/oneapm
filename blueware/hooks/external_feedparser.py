import sys
import types

import blueware.packages.six as six

from blueware.agent import current_transaction, update_wrapper, wrap_object, ExternalTrace

class capture_external_trace(object):

    def __init__(self, wrapped):
        update_wrapper(self, wrapped)
        self._bw_next_object = wrapped
        if not hasattr(self, '_bw_last_object'):
            self._bw_last_object = wrapped

    def __call__(self, url, *args, **kwargs):

        # The URL be a string or a file like object. Pass call
        # through if not a string.

        if not isinstance(url, six.string_types):
            return self._bw_next_object(url, *args, **kwargs)

        # Only then wrap the call if it looks like a URL. To
        # work that out need to first do some conversions of
        # accepted 'feed' formats to proper URL format.

        parsed_url = url

        if parsed_url.startswith('feed:http'):
            parsed_url = parsed_url[5:]
        elif parsed_url.startswith('feed:'):
            parsed_url = 'http:' + url[5:]

        if parsed_url.split(':')[0].lower() in ['http', 'https', 'ftp']:
            transaction = current_transaction()
            if current_transaction:
                trace = ExternalTrace(transaction, 'feedparser', parsed_url, 'GET')
                context_manager = trace.__enter__()
                try:
                    result = self._bw_next_object(url, *args, **kwargs)
                except:  # Catch all
                    context_manager.__exit__(*sys.exc_info())
                    raise
                context_manager.__exit__(None, None, None)
                return result
            else:
                return self._bw_next_object(url, *args, **kwargs)
        else:
            return self._bw_next_object(url, *args, **kwargs)

    def __getattr__(self, name):
       return getattr(self._bw_next_object, name)

def instrument(module):
    wrap_object(module, 'parse', capture_external_trace)
