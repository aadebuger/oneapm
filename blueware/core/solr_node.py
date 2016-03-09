from collections import namedtuple

import blueware.core.trace_node

from blueware.core.metric import TimeMetric

_SolrNode = namedtuple('_SolrNode',
        ['library', 'command', 'children', 'start_time', 'end_time',
        'duration', 'exclusive'])

class SolrNode(_SolrNode):

    def time_metrics(self, stats, root, parent):
        """Return a generator yielding the timed metrics for this
        memcache node as well as all the child nodes.

        """

        yield TimeMetric(name='Solr/all', scope='',
                duration=self.duration, exclusive=self.exclusive)

        if root.type == 'WebTransaction':
            yield TimeMetric(name='Solr/allWeb', scope='',
                    duration=self.duration, exclusive=self.exclusive)
        else:
            yield TimeMetric(name='Solr/allOther', scope='',
                    duration=self.duration, exclusive=self.exclusive)

        name = 'Solr/%s' % self.command

        yield TimeMetric(name=name, scope='', duration=self.duration,
                  exclusive=self.exclusive)

        yield TimeMetric(name=name, scope=root.path,
                duration=self.duration, exclusive=self.exclusive)

    def trace_node(self, stats, root, connections):

        name = 'SolrClient/%s/%s' % (self.library, self.command)

        name = root.string_table.cache(name)

        start_time = blueware.core.trace_node.node_start_time(root, self)
        end_time = blueware.core.trace_node.node_end_time(root, self)

        children = []

        root.trace_node_count += 1

        params = None

        class_name = name
        method_name = ''

        return blueware.core.trace_node.TraceNode(start_time=start_time,
                end_time=end_time, name=name, params=params, children=children,
                label=class_name, method_name=method_name)
