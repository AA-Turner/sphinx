class Baz:
    def __new__(cls, x, y):
        pass


def test_crasher():
    obj = Baz.__dict__['__new__']
    name = getattr(obj, '__name__', None)
    code = getattr(obj, '__code__', None)
    defaults = getattr(obj, '__defaults__', None)
    kwdefaults = getattr(obj, '__kwdefaults__', None)
    annotations = getattr(obj, '__annotations__', None)
