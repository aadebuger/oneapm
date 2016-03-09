from blueware.agent import (FunctionTraceWrapper, register_application, 
                    BackgroundTask, wrap_function_wrapper)

from blueware.hooks.framework_django import django_settings

def _bw_wrapper_BaseCommand___init___(wrapped, instance, args, kwargs):
    instance.handle = FunctionTraceWrapper(instance.handle)
    if hasattr(instance, 'handle_noargs'):
        instance.handle_noargs = FunctionTraceWrapper(instance.handle_noargs)
    return wrapped(*args, **kwargs)

def _bw_wrapper_BaseCommand_run_from_argv_(wrapped, instance, args, kwargs):
    def _args(argv, *args, **kwargs):
        return argv

    _argv = _args(*args, **kwargs)

    subcommand = _argv[1]

    commands = django_settings.instrumentation.scripts.django_admin
    startup_timeout = \
            django_settings.instrumentation.background_task.startup_timeout

    if subcommand not in commands:
        return wrapped(*args, **kwargs)

    application = register_application(timeout=startup_timeout)

    with BackgroundTask(application, subcommand, 'Django'):
        return wrapped(*args, **kwargs)

def instrument_django_core_management_base(module):
    wrap_function_wrapper(module, 'BaseCommand.__init__',
            _bw_wrapper_BaseCommand___init___)
    wrap_function_wrapper(module, 'BaseCommand.run_from_argv',
            _bw_wrapper_BaseCommand_run_from_argv_)
