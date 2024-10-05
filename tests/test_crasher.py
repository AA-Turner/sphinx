import inspect
import types


class _void:
    """A private marker - used in Parameter & Signature."""


class Baz:
    def __new__(cls, x, y):
        pass


def test_crasher():
    obj = Baz.__dict__['__new__']
    if not callable(obj) or inspect.isclass(obj):
        # All function-like objects are obviously callables,
        # and not classes.
        return False

    name = getattr(obj, '__name__', None)
    code = getattr(obj, '__code__', None)
    defaults = getattr(obj, '__defaults__', _void) # Important to use _void ...
    kwdefaults = getattr(obj, '__kwdefaults__', _void) # ... and not None here
    annotations = getattr(obj, '__annotations__', None)

    test = (isinstance(code, types.CodeType) and
            isinstance(name, str) and
            (defaults is None or isinstance(defaults, tuple)) and
            (kwdefaults is None or isinstance(kwdefaults, dict)) and
            (isinstance(annotations, (dict)) or annotations is None) )

    inspect.isasyncgenfunction(obj)
