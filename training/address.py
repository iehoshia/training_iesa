# This file is part country_zip module for Tryton.  The COPYRIGHT file at the
# top level of this repository contains the full copyright notices and license
# terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

__all__ = ['Address']

class Address:
    __metaclass__ = PoolMeta
    __name__ = 'party.address'

    @staticmethod
    def default_country():
        Configuration = Pool().get('party.configuration')
        config = Configuration(1)
        if config.default_country:
            return config.default_country.id
