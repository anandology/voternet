"""Caching utilities"""

import functools

cache = {}

OBJ_CACHE = {}

def _get_obj_key(obj):
    cls = obj.__class__
    mod = cls.__module__
    key = (mod + "." + cls.__name__, obj.id)
    return key

def invalidate_object_cache(objects):
    for obj in objects:
        obj_key = _get_obj_key(obj)
        OBJ_CACHE.pop(obj_key, None)

def object_memoize(f=None, key=None):
    if f is None:
        return lambda f: object_memoize(f, key=key)
    @functools.wraps(f)
    def g(self):
        obj_key = _get_obj_key(self)
        obj_cache = OBJ_CACHE.setdefault(obj_key, {})
        if key not in obj_cache:
            obj_cache[key] = f(self)
        return obj_cache[key]
    return g

def memoize(f=None, key=None):
    if f is None:
        return lambda f: memoize(f, key=key)
    if key is None:
        key = f.__name__
    @functools.wraps(f)
    def g(*args, **kwargs):
        cache_key = key, args, tuple(sorted(kwargs.items()))
        if cache_key not in cache:
            cache[cache_key] = f(*args, **kwargs)
        return cache[cache_key]
    return g

def invalidate_cache(_key, *args, **kwargs):
    cache_key = _key, args, tuple(sorted(kwargs.items()))
    cache.pop(cache_key, None)
