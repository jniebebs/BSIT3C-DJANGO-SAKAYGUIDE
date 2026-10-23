"""Test compatibility shim for Django 5.0 running on Python 3.14.

Django 5.0's ``BaseContext.__copy__`` calls ``copy(super())``, which returns a
``super`` object on Python 3.14 and breaks the test client's template
instrumentation. Replace it with a direct attribute copy.
"""
from django.template.context import BaseContext


def _base_context_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _base_context_copy
