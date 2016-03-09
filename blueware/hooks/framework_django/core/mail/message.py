from blueware.agent import wrap_function_trace


def instrument_django_core_mail_message(module):
    wrap_function_trace(module, 'EmailMessage.send')
