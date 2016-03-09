from blueware.agent import current_transaction, wrap_function_trace


def blueware_browser_timing_header():
    transaction = current_transaction()
    return transaction and transaction.browser_timing_header() or ''

def blueware_browser_timing_footer():
    transaction = current_transaction()
    return transaction and transaction.browser_timing_footer() or ''

def instrument_django_template(module):

    # Wrap methods for rendering of Django templates. The name
    # of the method changed in between Django versions so need
    # to check for which one we have. The name of the function
    # trace node is taken from the name of the template. This
    # should be a relative path with the template loader
    # uniquely associating it with a specific template library.
    # Therefore do not need to worry about making it absolute as
    # meaning should be known in the context of the specific
    # Django site.

    def template_name(template, *args):
        return template.name

    if hasattr(module.Template, '_render'):
        wrap_function_trace(module, 'Template._render',
                name=template_name, group='Template/Render')
    else:
        wrap_function_trace(module, 'Template.render',
                name=template_name, group='Template/Render')

    # Django 1.8 no longer has module.libraries. As automatic way is not
    # preferred we can just skip this now.

    if not hasattr(module, 'libraries'):
        return

    # Register template tags used for manual insertion of RUM
    # header and footer.
    #
    # TODO This can now be installed as a separate tag library
    # so should possibly look at deprecating this automatic
    # way of doing things.

    library = module.Library()
    library.simple_tag(blueware_browser_timing_header)
    library.simple_tag(blueware_browser_timing_footer)

    module.libraries['django.templatetags.blueware'] = library

