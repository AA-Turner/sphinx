"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

import inspect

from sphinx.util.inspect import isabstractmethod, iscoroutinefunction


class Baz:
    def __new__(cls, x, y):
        pass


def test_autodoc_class_signature_separated_new():
    obj = Baz.__dict__['__new__']
    isabstractmethod(obj)
    iscoroutinefunction(obj)
    inspect.isasyncgenfunction(obj)
