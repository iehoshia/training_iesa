# This file is part of the country_zip module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class CountryZipTestCase(ModuleTestCase):
    'Test Country Zip module'
    module = 'country_zip'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CountryZipTestCase))
    return suite
