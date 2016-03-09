from blueware.agent import wrap_solr_trace

def instrument(module):

    if hasattr(module.Solr, 'search'):
        wrap_solr_trace(module, 'Solr.search', 'pysolr', 'query')

    if hasattr(module.Solr, 'more_like_this'):
        wrap_solr_trace(module, 'Solr.more_like_this', 'pysolr', 'query')

    if hasattr(module.Solr, 'suggest_terms'):
        wrap_solr_trace(module, 'Solr.suggest_terms', 'pysolr', 'query')

    if hasattr(module.Solr, 'add'):
        wrap_solr_trace(module, 'Solr.add', 'pysolr', 'add')

    if hasattr(module.Solr, 'delete'):
        wrap_solr_trace(module, 'Solr.delete', 'pysolr', 'delete')

    if hasattr(module.Solr, 'commit'):
        wrap_solr_trace(module, 'Solr.commit', 'pysolr', 'commit')

    if hasattr(module.Solr, 'optimize'):
        wrap_solr_trace(module, 'Solr.optimize', 'pysolr', 'optimize')
