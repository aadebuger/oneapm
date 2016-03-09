import types

from blueware.agent import current_transaction, wrap_object, FunctionTraceWrapper

class stream_wrapper(object):
    def __init__(self, stream, filepath):
        self.__stream = stream
        self.__filepath = filepath
    def render(self, *args, **kwargs):
        return FunctionTraceWrapper(self.__stream.render, self.__filepath,
                                    'Template/Render')(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(self.__stream, name)
    def __iter__(self):
        return iter(self.__stream)
    def __or__(self, function):
        return self.__stream.__or__(function)
    def __str__(self):
        return self.__stream.__str__()
    def __unicode__(self):
        return self.__stream.__unicode__()
    def __html__(self):
        return self.__stream.__html__()

class wrap_template(object):
    def __init__(self, wrapped):
        if isinstance(wrapped, tuple):
            (instance, wrapped) = wrapped
        else:
            instance = None
        self.__instance = instance
        self.__wrapped = wrapped

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self.__wrapped.__get__(instance, klass)
        return self.__class__((instance, descriptor))

    def __call__(self, *args, **kwargs):
        transaction = current_transaction()
        if transaction and self.__instance:
            return stream_wrapper(self.__wrapped(*args, **kwargs),
                                  self.__instance.filepath)
        else:
            return self.__wrapped(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.__wrapped, name)

def instrument(module):

    if module.__name__ == 'genshi.template.base':

        wrap_object(module, 'Template.generate', wrap_template)
