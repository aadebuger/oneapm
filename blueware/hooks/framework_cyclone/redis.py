from blueware.agent import wrap_datastore_trace

_redis_client_methods = ('quit', 'auth', 'ping', 'exists', 'delete',
    'type', 'keys', 'scan', 'randomkey', 'rename', 'renamenx', 'dbsize',
    'expire', 'persist', 'ttl', 'select', 'move', 'flushdb', 'flushall',
    'time', 'set', 'get', 'getbit', 'getset', 'mget', 'setbit',
    'setnx', 'setex', 'mset', 'msetnx', 'bitop', 'bitcount',
    'incr', 'incrby', 'decr', 'append', 'substr', 'rpush', 'lpush',
    'llen', 'lrange', 'ltrim', 'lindex', 'lset', 'lrem', 'lpop',
    'rpop', 'blpop', 'brpop', 'brpoplpush', 'rpoplpush', 'sadd',
    'srem', 'spop', 'smove', 'scard', 'sismember', 'sinter', 'sinterstore',
    'sunion', 'sunionstore', 'sdiff', 'sdiffstore', 'smembers', 'srandmember',
    'sscan', 'zadd', 'zrem', 'zincr', 'zdecr', 'zincrby', 'zrank', 'zrevrank',
    'zrange', 'zrevrange', 'zrangebyscore', 'zrevrangebyscore', 'zcount',
    'zcard', 'zscore', 'zremrangebyrank', 'zremrangebyscore', 'zunionstore',
    'zinterstore', 'zscan', 'hset', 'hsetnx', 'hget', 'hmget', 'hmset',
    'hincr', 'hdecr', 'hincrby', 'hexists', 'hdel', 'hlen', 'hkeys', 'hvals',
    'hgetall', 'hscan', 'sort', 'watch', 'unwatch', 'multi', 'commit', 'discard',
    'publish', 'save', 'bgsave', 'lastsave', 'shutdown', 'bgrewriteaof', 'info',
    'eval', 'evalsha', 'script_exists', 'script_flush', 'script_kill', 'script_load',
    'pfadd', 'pfcount', 'pfmerge')

def instrument_cyclone_redis(module):

    for name in _redis_client_methods:
        if name in vars(module.RedisProtocol):
            wrap_datastore_trace(module.RedisProtocol, name,
                product='Redis', target=None, operation=name)
