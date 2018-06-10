#:after:party/party:section:direcciones#

Códigos postales de país
========================

En el formulario de las direcciones de la empresa, si disponemos de un país en la
dirección, podemos introducir el código postal y nos rellenará automáticamente la
subdivisión y la ciudad a que corresponde ese código postal.

Por ejemplo, el código 08720 y España, rellenará los campos:

* Localidad: Vilafranca del Penedès,
* Provincia: Barcelona,
* País: España.


#:inside:party/party:section:configuration#

País por defecto en las direcciones
===================================

En el campo |default_country| podemos especificar el país que se utilizará por
defecto para la creación de nuevas direcciones de tercero.

.. |default_country| field:: party.configuration/default_country
