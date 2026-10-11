=======
EasyOCR
=======

Extrae facturas de proveedor y tickets de gasto a partir de archivos PDF e
imágenes.

Este módulo es la versión para Odoo del EasyOCR de Dolibarr, de EasySoft Tech
S.L. Un documento existe desde que se sube su archivo, así que uno que no se
pueda leer sigue a la vista y se puede reintentar en vez de desaparecer.

Qué hace
========

- Lee gratis los PDF que ya llevan su texto, dibujando rectángulos sobre la
  página en un visor, y guarda esos rectángulos como plantilla por proveedor.
- Lee escaneos y fotografías con el servicio de extracción EasyOCR, y muestra el
  resultado en un diálogo donde se puede revisar y corregir cada valor.
- Crea la factura de proveedor o el abono, con una línea por cada línea leída y
  los impuestos de la empresa para los tipos leídos (IVA, recargo de equivalencia
  y retención). Un proveedor que no está dado de alta se crea desde la lectura.
- Opcionalmente registra el pago, manda lotes enteros al servicio, archiva
  tickets fotografiados desde una página para el móvil y registra los webhooks
  del servicio.

Instalación
===========

Instala el módulo desde el menú Aplicaciones, o desde la línea de comandos:

::

   odoo -d <base-de-datos> -i easyocr --stop-after-init

El módulo depende de ``base``, ``mail``, ``account`` y ``hr_expense``, todos
ellos parte de Odoo Community.

Configuración
=============

Ve a *Ajustes > EasyOCR*. Leer PDF que ya llevan su texto no necesita nada. Leer
escaneos y fotografías necesita el servicio EasyOCR: activa la extracción con IA,
rellena la dirección del servicio y la clave API, y usa *Probar la conexión*, que
no gasta ninguna lectura. Los ajustes son por compañía.

Problemas conocidos / Hoja de ruta
==================================

- El IGIC (Canarias) todavía no está contemplado.
- Un tipo para el que la empresa no tiene ningún impuesto de compra deja la línea
  sin impuesto: el módulo no se lo inventa.

Seguimiento de errores
======================

Los errores se registran en `GitHub Issues <https://github.com/EasySoft-Tech-SL/odoo-easyocr-module/issues>`_.

Créditos
========

Autores
-------

* EasySoft Tech S.L. <https://easysoft.es>

Mantenedores
------------

Este módulo lo mantiene EasySoft Tech S.L.
