from blueware.agent import wrap_transaction_name


def instrument_django_contrib_staticfiles_handlers(module):
    wrap_transaction_name(module, 'StaticFilesHandler.serve')
