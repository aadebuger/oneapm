from blueware.agent import wrap_external_trace

def instrument(module):

    def url_connect_http(connection):
        return 'http://%s/' % connection.host

    wrap_external_trace(module, 'HTTPConnectionWithTimeout.connect', 'httplib2',
                        url_connect_http)

    def url_connect_https(connection):
        return 'https://%s/' % connection.host

    wrap_external_trace(module, 'HTTPSConnectionWithTimeout.connect', 'httplib2',
                        url_connect_https)

    def url_request(connection, uri, *args, **kwargs):
        return uri

    wrap_external_trace(module, 'Http.request', 'httplib2', url_request)
