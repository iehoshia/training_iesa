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

    def get_subdivision_country(self):
        Zip = Pool().get('country.zip')

        if self.zip and self.country:
            zips = Zip.search([
                        ('zip', '=', self.zip),
                        ('subdivision.country', '=', self.country.id),
                        ])
            if zips:
                zip_, = zips
                self.city = zip_.city
                if zip_.subdivision:
                    self.subdivision = zip_.subdivision

    @fields.depends('zip', 'country', 'city', 'subdivision')
    def on_change_zip(self):
        return self.get_subdivision_country()

    @fields.depends('zip', 'country', 'city', 'subdivision')
    def on_change_country(self):
        return self.get_subdivision_country()
