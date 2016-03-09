from blueware.agent import wrap_external_trace

def instrument(module):

    def url_request(rest_obj, method, url, *args, **kwargs):
        return url

    wrap_external_trace(module, 'rest.RESTClientObject.request', 'dropbox', url_request)
