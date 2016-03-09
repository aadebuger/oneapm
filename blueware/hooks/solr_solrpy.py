from blueware.agent import wrap_solr_trace

def instrument(module):

    if hasattr(module.Solr, 'delete'):
        wrap_solr_trace(module, 'Solr.delete', 'solrpy', 'delete')

    if hasattr(module.Solr, 'delete_many'):
        wrap_solr_trace(module, 'Solr.delete_many', 'solrpy', 'delete')

    if hasattr(module.Solr, 'delete_query'):
        wrap_solr_trace(module, 'Solr.delete_query', 'solrpy', 'delete')

    if hasattr(module.Solr, 'add'):
        wrap_solr_trace(module, 'Solr.add', 'solrpy', 'add')

    if hasattr(module.Solr, 'add_many'):
        wrap_solr_trace(module, 'Solr.add_many', 'solrpy', 'add')

    if hasattr(module.Solr, 'commit'):
        wrap_solr_trace(module, 'Solr.commit', 'solrpy', 'commit')

    if hasattr(module.Solr, 'optimize'):
        wrap_solr_trace(module, 'Solr.optimize', 'solrpy', 'optimize')


    if hasattr(module.SolrConnection, 'query'):
        wrap_solr_trace(
                module, 'SolrConnection.query', 'solrpy', 'query')

    if hasattr(module.SolrConnection, 'raw_query'):
        wrap_solr_trace(module, 'SolrConnection.raw_query', 'solrpy', 'query')

    if hasattr(module, 'SearchHandler'):
        wrap_solr_trace(module, 'SearchHandler.__call__', 'solrpy', 'query')
