"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

from sphinx.util import inspect


class Baz:
    def __new__(cls, x, y):
        pass


def test_autodoc_class_signature_separated_new():
    obj = Baz.__dict__['__new__']
    if inspect.isabstractmethod(obj):
        pass
    if inspect.iscoroutinefunction(obj) or inspect.isasyncgenfunction(obj):
        pass
    if (inspect.isclassmethod(obj) or
            inspect.is_singledispatch_method(obj) and inspect.isclassmethod(obj.func)):
        pass
