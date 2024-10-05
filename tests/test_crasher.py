import inspect


class Baz:
    def __new__(cls, x, y):
        pass


def crasher():
    obj = Baz.__new__
    inspect.isasyncgenfunction(obj)
