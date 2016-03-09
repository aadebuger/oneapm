from blueware.agent import (global_settings, callable_name, current_transaction,
							wrap_function_wrapper, function_wrapper, FunctionTrace)
from blueware.hooks.framework_django import django_settings
import sys


@function_wrapper
def _bw_wrapper_django_template_base_InclusionNode_render_(wrapped,
        instance, args, kwargs):

    transaction = current_transaction()

    if transaction is None:
        return wrapped(*args, **kwargs)

    if wrapped.__self__ is None:
        return wrapped(*args, **kwargs)

    file_name = getattr(wrapped.__self__, '_bw_file_name', None)

    if file_name is None:
        return wrapped(*args, **kwargs)

    name = wrapped.__self__._bw_file_name

    with FunctionTrace(transaction, name, 'Template/Include'):
        return wrapped(*args, **kwargs)

def _bw_wrapper_django_template_base_generic_tag_compiler_(wrapped, instance,
        args, kwargs):

    if wrapped.__code__.co_argcount > 6:
        # Django > 1.3.

        def _bind_params(parser, token, params, varargs, varkw, defaults,
                name, takes_context, node_class, *args, **kwargs):
            return node_class
    else:
        # Django <= 1.3.

        def _bind_params(params, defaults, name, node_class, parser, token,
                *args, **kwargs):
            return node_class

    node_class = _bind_params(*args, **kwargs)

    if node_class.__name__ == 'InclusionNode':
        result = wrapped(*args, **kwargs)

        result.render = (
                _bw_wrapper_django_template_base_InclusionNode_render_(
                result.render))

        return result

    return wrapped(*args, **kwargs)

def _bw_wrapper_django_template_base_Library_tag_(wrapped, instance,
        args, kwargs):

    def _bind_params(name=None, compile_function=None, *args, **kwargs):
        return compile_function

    compile_function = _bind_params(*args, **kwargs)

    if not callable(compile_function):
        return wrapped(*args, **kwargs)

    def _get_node_class(compile_function):

        node_class = None

        # Django >= 1.4 uses functools.partial

        if isinstance(compile_function, functools.partial):
            node_class = compile_function.keywords.get('node_class')

        # Django < 1.4 uses their home-grown "curry" function,
        # not functools.partial.

        if (hasattr(compile_function, 'func_closure')
                and hasattr(compile_function, '__name__')
                and compile_function.__name__ == '_curried'):

            # compile_function here is generic_tag_compiler(), which has been
            # curried. To get node_class, we first get the function obj, args,
            # and kwargs of the curried function from the cells in
            # compile_function.func_closure. But, the order of the cells
            # is not consistent from platform to platform, so we need to map
            # them to the variables in compile_function.__code__.co_freevars.

            cells = dict(zip(compile_function.__code__.co_freevars,
                    (c.cell_contents for c in compile_function.func_closure)))

            # node_class is the 4th arg passed to generic_tag_compiler()

            if 'args' in cells and len(cells['args']) > 3:
                node_class = cells['args'][3]

        return node_class

    node_class = _get_node_class(compile_function)

    if node_class is None or node_class.__name__ != 'InclusionNode':
        return wrapped(*args, **kwargs)

    # Climb stack to find the file_name of the include template.
    # While you only have to go up 1 frame when using python with
    # extensions, pure python requires going up 2 frames.

    file_name = None
    stack_levels = 2

    for i in range(1, stack_levels + 1):
        frame = sys._getframe(i)

        if ('generic_tag_compiler' in frame.f_code.co_names
                and 'file_name' in frame.f_code.co_freevars):
            file_name = frame.f_locals.get('file_name')

    if file_name is None:
        return wrapped(*args, **kwargs)

    if isinstance(file_name, module_django_template_base.Template):
        file_name = file_name.name

    node_class._bw_file_name = file_name

    return wrapped(*args, **kwargs)


@function_wrapper
def _bw_wrapper_django_inclusion_tag_wrapper_(wrapped, instance,
        args, kwargs):

    transaction = current_transaction()

    if transaction is None:
        return wrapped(*args, **kwargs)

    name = hasattr(wrapped, '__name__') and wrapped.__name__

    if name is None:
        return wrapped(*args, **kwargs)

    qualname = callable_name(wrapped)

    tags = django_settings.instrumentation.templates.inclusion_tag

    if '*' not in tags and name not in tags and qualname not in tags:
        return wrapped(*args, **kwargs)

    with FunctionTrace(transaction, name, group='Template/Tag'):
        return wrapped(*args, **kwargs)

@function_wrapper
def _bw_wrapper_django_inclusion_tag_decorator_(wrapped, instance,
        args, kwargs):

    def _bind_params(func, *args, **kwargs):
        return func, args, kwargs

    func, _args, _kwargs = _bind_params(*args, **kwargs)

    func = _bw_wrapper_django_inclusion_tag_wrapper_(func)

    return wrapped(func, *_args, **_kwargs)

def _bw_wrapper_django_template_base_Library_inclusion_tag_(wrapped,
        instance, args, kwargs):

    return _bw_wrapper_django_inclusion_tag_decorator_(
            wrapped(*args, **kwargs))

def instrument_django_template_base(module):
    global module_django_template_base
    module_django_template_base = module

    settings = global_settings()

    if 'django.instrumentation.inclusion-tags.r1' in settings.feature_flag:
        wrap_function_wrapper(module, 'generic_tag_compiler',
                _bw_wrapper_django_template_base_generic_tag_compiler_)

        wrap_function_wrapper(module, 'Library.tag',
                _bw_wrapper_django_template_base_Library_tag_)

        wrap_function_wrapper(module, 'Library.inclusion_tag',
                _bw_wrapper_django_template_base_Library_inclusion_tag_)
