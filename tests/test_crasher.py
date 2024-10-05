class Baz:
    def __new__(cls, x, y):
        pass


def test_crasher():
    assert Baz.__new__.__annotations__ == {}
    obj = Baz.__dict__['__new__']
    obj.__annotations__
    getattr(obj, '__annotations__', None)


if __name__ == '__main__':
    assert Baz.__new__.__annotations__ == {}
    obj = Baz.__dict__['__new__']
    obj.__annotations__
    getattr(obj, '__annotations__', None)
