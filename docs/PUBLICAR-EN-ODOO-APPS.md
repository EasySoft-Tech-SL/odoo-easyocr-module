# Publicar en la Odoo Apps Store

Estado a 8-oct-2026: **el repositorio está listo; falta enviarlo**, que necesita
entrar con la cuenta en apps.odoo.com.

## Lo que ya está en el repositorio

La tienda **lee el repositorio**, no el ZIP (el ZIP es para la release y para
instalar a mano). Escanea la rama y monta la ficha con lo que encuentre:

| Qué mira | Dónde está |
|---|---|
| Descripción larga | `addons/easyocr/static/description/index.html` (sin scripts, imágenes relativas dentro del módulo) |
| Icono | `static/description/icon.png`, **100x100**, como los módulos oficiales de Odoo |
| Icono en grande | `static/description/icon_hi.png`, 512x512 |
| Portada y capturas | La clave `images` del manifiesto: la **primera** es la portada del catálogo, las demás van a la galería |
| Nombre, resumen, categoría | Manifiesto: `EasyOCR`, `Accounting/Accounting` |
| Autor y soporte | `author`, `website`, `support` (`info@easysoft.es`) |

Sin las tres primeras, la revisión de Odoo contesta «the module has no icon»,
«no cover image» o «non-html description»; están puestas por eso.

## Cómo se envía

1. Entrar en <https://apps.odoo.com> con la cuenta de Odoo de la empresa.
2. «Submit your module» (o «Sell your app»): se le da la **URL del repositorio**
   y la **rama**.
3. Ramas: `19.0` alimenta las fichas de Odoo 19 y `18.0` las de Odoo 18. El
   mismo nombre técnico en las dos ramas **es una sola ficha con dos
   versiones**, así que se envían las dos.
4. La tienda vuelve a escanear el repositorio a su ritmo (horas o días): la
   ficha no cambia en el momento.

## Para cada versión nueva

- **Subir el `version` del manifiesto.** Es lo que hace que la tienda vuelva a
  mirar el contenido; una edición con la misma versión se le puede escapar.
- Comprobar antes de empujar: `python tools/build_zip.py` (versión, layout,
  finales de línea, sin restos) y una instalación limpia del ZIP publicado en un
  Odoo sin módulos nuestros. El escaneo **no instala** el módulo: que la ficha
  esté publicada no quiere decir que instale, y eso ya pasó una vez (v1.0.0).
- El ZIP sobra en la tienda, pero no en la release de GitHub.

## Lo que NO se publica ahí

El servicio de extracción no es un módulo de la tienda: se contrata aparte. La
ficha lo dice en «What you need», sin prometer que la lectura de escaneos venga
incluida con la descarga.
