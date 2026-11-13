"""Test runner with a small Django 5.0 / Python 3.14 compatibility shim.

Django 5.0's ``BaseContext.__copy__`` calls ``copy(super())``. Python 3.14
removed the implicit ``__dict__`` that this relied on, so rendering any
template through the test client fails while the test client tries to save a
copy of the template context. Production template rendering is unaffected.

The shim below performs the same shallow copy explicitly and is installed only
while the test suite runs.
"""
from django.template.context import BaseContext
from django.test.runner import DiscoverRunner


def _compatible_context_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _compatible_context_copy


class SakayGuideTestRunner(DiscoverRunner):
    """Use the explicit context copy while testing on Python 3.14+."""

    def __init__(self, *args, **kwargs):
        BaseContext.__copy__ = _compatible_context_copy
        super().__init__(*args, **kwargs)
