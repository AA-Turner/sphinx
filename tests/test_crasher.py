import inspect


class Baz:
    def __new__(cls, x, y):
        pass


def test_crasher():
    obj = Baz.__dict__['__new__']
    inspect.isasyncgenfunction(obj)
