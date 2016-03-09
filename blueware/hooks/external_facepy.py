from blueware.agent import wrap_external_trace

def instrument(module):

    def url_query(graph_obj, method, path, *args, **kwargs):
        return '/'.join([graph_obj.url, path])

    wrap_external_trace(module, 'GraphAPI._query', 'facepy', url_query)

    #def url_method(graph_obj, path, *args, **kwargs):
        #return '/'.join([graph_obj.url, path])

    #wrap_external_trace(module, 'GraphAPI.get', 'facepy', url_method)

    #wrap_external_trace(module, 'GraphAPI.post', 'facepy', url_method)

    #wrap_external_trace(module, 'GraphAPI.delete', 'facepy', url_method)

    #def url_search(graph_obj, path, *args, **kwargs):
        #return '/'.join([graph_obj.url, 'search'])

    #wrap_external_trace(module, 'GraphAPI.search', 'facepy', url_search)
