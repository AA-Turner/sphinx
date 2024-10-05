import inspect


class Baz:
    def __new__(cls, x, y):
        pass


def test_autodoc_class_signature_separated_new():
    obj = Baz.__dict__['__new__']
    inspect.isasyncgenfunction(obj)
