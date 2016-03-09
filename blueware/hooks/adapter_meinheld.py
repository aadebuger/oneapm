from blueware.agent import WSGIApplicationWrapper, wrap_in_function

def instrument_meinheld_server(module):

    def wrap_wsgi_application_entry_point(application, *args, **kwargs):
        application = WSGIApplicationWrapper(application)
        args = [application] + list(args)
        return (args, kwargs)

    wrap_in_function(module, 'run', wrap_wsgi_application_entry_point)
