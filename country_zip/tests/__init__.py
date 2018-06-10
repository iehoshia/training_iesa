# This file is part helloword module for Tryton.  The COPYRIGHT file at the top
# level of this repository contains the full copyright notices and license
# terms.
try:
    from trytond.modules.country_zip.tests.test_country_zip import suite
except ImportError:
    from .test_country_zip import suite

__all__ = ['suite']
