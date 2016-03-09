from blueware.agent import wrap_in_function, WSGIApplicationWrapper

def instrument_django_core_servers_basehttp(module):

    # Allow 'runserver' to be used with Django <= 1.3. To do
    # this we wrap the WSGI application argument on the way in
    # so that the run() method gets the wrapped instance.
    #
    # Although this works, if anyone wants to use it and make
    # it reliable, they may need to first need to patch Django
    # as explained in the ticket:
    #
    #   https://code.djangoproject.com/ticket/16241
    #
    # as the Django 'runserver' is not WSGI compliant due to a
    # bug in its handling of errors when writing response.
    #
    # The way the agent now uses a weakref dictionary for the
    # transaction object may be enough to ensure the prior
    # transaction is cleaned up properly when it is deleted,
    # but not absolutely sure that will always work. Thus is
    # still a risk of error on subsequent request saying that
    # there is an active transaction.
    #
    # TODO Later versions of Django use the wsgiref server
    # instead which will likely need to be dealt with via
    # instrumentation of the wsgiref module or some other means.

    import django

    framework = ('Django', django.get_version())

    def wrap_wsgi_application_entry_point(server, application, **kwargs):
      return ((server, WSGIApplicationWrapper(application,
              framework='Django'),), kwargs)

    # XXX Because of risk of people still trying to use the
    # inbuilt Django development server and since the code is
    # not going to be changed, could just patch it to fix
    # problem and the instrumentation we need.

    if (not hasattr(module, 'simple_server') and
            hasattr(module.ServerHandler, 'run')):

        # Patch the server to make it work properly.

        def run(self, application):
            try:
                self.setup_environ()
                self.result = application(self.environ, self.start_response)
                self.finish_response()
            except Exception:
                self.handle_error()
            finally:
                self.close()


        def close(self):
            if self.result is not None:
                try:
                    self.request_handler.log_request(
                            self.status.split(' ',1)[0], self.bytes_sent)
                finally:
                    try:
                        if hasattr(self.result,'close'):
                            self.result.close()
                    finally:
                        self.result = None
                        self.headers = None
                        self.status = None
                        self.environ = None
                        self.bytes_sent = 0
                        self.headers_sent = False

        # Leaving this out for now to see whether weakref solves
        # the problem.

        #module.ServerHandler.run = run
        #module.ServerHandler.close = close

        # Now wrap it with our instrumentation.

        wrap_in_function(module, 'ServerHandler.run',
                wrap_wsgi_application_entry_point)

