from blueware.agent import WSGIApplicationWrapper, wrap_in_function

def instrument_cherrypy_wsgiserver_wsgiserver2(module):

    def wrap_wsgi_application_entry_point(server, bind_addr, application,
            *args, **kwargs):
        application = WSGIApplicationWrapper(application)
        args = [server, bind_addr, application] + list(args)
        return (args, kwargs)

    wrap_in_function(module, 'CherryPyWSGIServer.__init__', wrap_wsgi_application_entry_point)
