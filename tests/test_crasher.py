"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

import inspect
import types
from functools import partial, partialmethod, singledispatchmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from typing_extensions import TypeIs


class Baz:
    def __new__(cls, x, y):
        pass


def safe_getattr(obj: Any, name: str, *defargs: Any) -> Any:
    """A getattr() that turns all exceptions into AttributeErrors."""
    if len(defargs) > 1:
        msg = f'safe_getattr expected at most 3 arguments, got {len(defargs)}'
        raise TypeError(msg)

    try:
        return getattr(obj, name, *defargs)
    except Exception as exc:
        # sometimes accessing a property raises an exception (e.g.
        # NotImplementedError), so let's try to read the attribute directly
        try:
            # In case the object does weird things with attribute access
            # such that accessing `obj.__dict__` may raise an exception
            return obj.__dict__[name]
        except Exception:
            pass

        # this is a catch-all for all the weird things that some modules do
        # with attribute access
        if defargs:
            return defargs[0]

        raise AttributeError(name) from exc


def unwrap_all(obj: Any, *, stop: Callable[[Any], bool] | None = None) -> Any:
    """Get an original object from wrapped object.

    Unlike :func:`unwrap`, this unwraps partial functions, wrapped functions,
    class methods and static methods.

    When specified, *stop* is a predicate indicating whether an object should
    be unwrapped or not.
    """
    if callable(stop):
        while not stop(obj):
            if isinstance(obj, partial | partialmethod):
                obj = obj.func
            elif inspect.isroutine(obj) and hasattr(obj, '__wrapped__'):
                obj = obj.__wrapped__
            elif isclassmethod(obj) or isstaticmethod(obj):
                obj = obj.__func__
            else:
                return obj
        return obj  # in case the while loop never starts

    while True:
        if isinstance(obj, partial | partialmethod):
            obj = obj.func
        elif inspect.isroutine(obj) and hasattr(obj, '__wrapped__'):
            obj = obj.__wrapped__
        elif isclassmethod(obj) or isstaticmethod(obj):
            obj = obj.__func__
        else:
            return obj


def isabstractmethod(obj: Any) -> bool:
    """Check if the object is an :func:`abstractmethod`."""
    return safe_getattr(obj, '__isabstractmethod__', False) is True


def iscoroutinefunction(obj: Any) -> TypeIs[Callable[..., types.CoroutineType]]:
    """Check if the object is a :external+python:term:`coroutine` function."""
    obj = unwrap_all(obj, stop=_is_wrapped_coroutine)
    return inspect.iscoroutinefunction(obj)


def _is_wrapped_coroutine(obj: Any) -> bool:
    """Check if the object is wrapped coroutine-function."""
    if isstaticmethod(obj) or isclassmethod(obj) or isinstance(obj, partial | partialmethod):
        # staticmethod, classmethod and partial method are not a wrapped coroutine-function
        # Note: Since 3.10, staticmethod and classmethod becomes a kind of wrappers
        return False
    return hasattr(obj, '__wrapped__')


def isclassmethod(
    obj: Any,
    cls: Any = None,
    name: str | None = None,
) -> TypeIs[classmethod]:
    """Check if the object is a :class:`classmethod`."""
    if isinstance(obj, classmethod):
        return True
    if inspect.ismethod(obj) and obj.__self__ is not None and inspect.isclass(obj.__self__):
        return True
    if cls and name:
        # trace __mro__ if the method is defined in parent class
        sentinel = object()
        for basecls in getmro(cls):
            meth = basecls.__dict__.get(name, sentinel)
            if meth is not sentinel:
                return isclassmethod(meth)
    return False


def getmro(obj: Any) -> tuple[type, ...]:
    """Safely get :attr:`obj.__mro__ <class.__mro__>`."""
    __mro__ = safe_getattr(obj, '__mro__', None)
    if isinstance(__mro__, tuple):
        return __mro__
    return ()


def isstaticmethod(
    obj: Any,
    cls: Any = None,
    name: str | None = None,
) -> TypeIs[staticmethod]:
    """Check if the object is a :class:`staticmethod`."""
    if isinstance(obj, staticmethod):
        return True
    if cls and name:
        # trace __mro__ if the method is defined in parent class
        sentinel = object()
        for basecls in getattr(cls, '__mro__', [cls]):
            meth = basecls.__dict__.get(name, sentinel)
            if meth is not sentinel:
                return isinstance(meth, staticmethod)
    return False


def test_crasher():
    obj = Baz.__new__
    isabstractmethod(obj)
    iscoroutinefunction(obj)
    isclassmethod(obj)
    isinstance(obj, singledispatchmethod)
    inspect.isasyncgenfunction(obj)
