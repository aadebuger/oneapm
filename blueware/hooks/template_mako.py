from blueware.agent import current_transaction, FunctionTrace, wrap_function_trace, wrap_object

class TemplateRenderWrapper(object):

    def __init__(self, wrapped):
        self.__wrapped = wrapped

    def __getattr__(self, name):
        return getattr(self.__wrapped, name)

    def __get__(self, instance, klass):
        if instance is None:
            return self
        descriptor = self.__wrapped.__get__(instance, klass)
        return self.__class__(descriptor)

    def __call__(self, template, *args, **kwargs):
        transaction = current_transaction()
        if transaction:
            if hasattr(template, 'filename'):
                name = template.filename or '<template>'
                with FunctionTrace(transaction, name=name, group='Template/Render'):
                    return self.__wrapped(template, *args, **kwargs)
            else:
                return self.__wrapped(template, *args, **kwargs)
        else:
            return self.__wrapped(template, *args, **kwargs)

def instrument_mako_runtime(module):

    wrap_object(module, '_render', TemplateRenderWrapper)

def instrument_mako_template(module):

    def template_filename(template, text, filename, *args):
        return filename

    wrap_function_trace(module, '_compile_text',
                        name=template_filename, group='Template/Compile')

    wrap_function_trace(module, '_compile_module_file',
                        name=template_filename, group='Template/Compile')
