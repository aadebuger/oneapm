from blueware.agent import wrap_function_wrapper, FunctionTrace

from . import retrieve_current_transaction

def template_generate_wrapper(wrapped, instance, args, kwargs):
    transaction = retrieve_current_transaction()

    if transaction is None:
        return wrapped(*args, **kwargs)

    with FunctionTrace(transaction, name=instance.name,
            group='Template/Render'):
        return wrapped(*args, **kwargs)

def template_generate_python_wrapper(wrapped, instance, args, kwargs):
    result = wrapped(*args, **kwargs)

    if result is not None:
        return 'import blueware.agent as _bw_blueware_agent\n' + result

def block_generate_wrapper(wrapped, instance, args, kwargs):

    def execute(writer, *args, **kwargs):
        if not hasattr(instance, 'line'):
            return wrapped(writer, *args, **kwargs)

        writer.write_line('with _bw_blueware_agent.FunctionTrace('
                '_bw_blueware_agent.current_transaction(), name=%r, '
                'group="Template/Block"):' % instance.name, instance.line)

        with writer.indent():
            writer.write_line("pass", instance.line)
            return wrapped(writer, *args, **kwargs)

    return execute(*args, **kwargs)

def instrument_cyclone_template(module):
    wrap_function_wrapper(module, 'Template.generate',
            template_generate_wrapper)
    wrap_function_wrapper(module, 'Template._generate_python',
            template_generate_python_wrapper)
    wrap_function_wrapper(module, '_NamedBlock.generate',
            block_generate_wrapper)
