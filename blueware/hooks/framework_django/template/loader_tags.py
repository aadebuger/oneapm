from blueware.agent import (callable_name, current_transaction, 
                    FunctionTrace, FunctionWrapper)


def wrap_template_block(wrapped):

    name = callable_name(wrapped)

    def wrapper(wrapped, instance, args, kwargs):
        transaction = current_transaction()

        if transaction is None:
            return wrapped(*args, **kwargs)

        with FunctionTrace(transaction, name=instance.name,
                group='Template/Block'):
            return wrapped(*args, **kwargs)

    return FunctionWrapper(wrapped, wrapper)

def instrument_django_template_loader_tags(module):

    # Wrap template block node for timing, naming the node after
    # the block name as defined in the template rather than
    # function name.

    module.BlockNode.render = wrap_template_block(module.BlockNode.render)
