from blueware.agent import wrap_function_trace


def instrument_django_http_multipartparser(module):
    wrap_function_trace(module, 'MultiPartParser.parse')
