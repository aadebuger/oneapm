from blueware.agent import wrap_function_trace

    
def instrument_django_core_mail(module):
    wrap_function_trace(module, 'mail_admins')
    wrap_function_trace(module, 'mail_managers')
    wrap_function_trace(module, 'send_mail')
