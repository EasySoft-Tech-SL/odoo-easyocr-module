# Publicar en la Odoo Apps Store

Estado a 12-oct-2026: **está publicado para 18.0 y 19.0.** Esas dos ramas están
registradas, escaneadas sin errores y la ficha está viva en el catálogo. Las otras
tres series (16.0, 17.0 y 20.0) están en el repositorio y todavía **no** en la
tienda: se registran igual, y cada una añade una versión a la misma ficha.

- Odoo 19: <https://apps.odoo.com/apps/modules/19.0/easyocr>
- Odoo 18: <https://apps.odoo.com/apps/modules/18.0/easyocr>

Es **una sola ficha con una versión por serie** (el mismo nombre técnico en todas
las ramas), con selector de versión. El alta la hace sola la skill
`publicar-modulo-odoo-apps` (`~/.claude/skills/`): entra en la tienda sin
navegador, registra la URL, fuerza el escaneo y lee el resultado. El estado de
cada repositorio registrado se ve en <https://apps.odoo.com/apps/dashboard/repos>
(pide la sesión de odoo.com): ahí sale `Draft` mientras el escaneo no ha ido bien
y `Active` cuando ya está publicado.

**No hay aprobación previa.** El escaneo es lo que publica, y hasta que no sale
limpio el repositorio se queda en `Draft` sin publicar nada. La revisión de Odoo
es **posterior** y es una puntuación: cada ficha se puntúa por 5 criterios (icono,
portada, `license` en el manifiesto, valoración, y descripción en HTML) y la nota
decide el orden dentro del catálogo, no si sale. Lo que sí ocurre es lo contrario:
incumplir las guías del vendedor despublica la ficha hasta arreglarlo, y Odoo se
reserva retirar cualquier módulo sin avisar. Con la cuenta abierta, la propia
página de la ficha enseña la nota cuando no es 5 de 5.

## Lo que ya está en el repositorio

La tienda **lee el repositorio**, no el ZIP (el ZIP es para la release y para
instalar a mano). Escanea la rama y monta la ficha con lo que encuentre:

| Qué mira | Dónde está |
|---|---|
| Descripción larga | `easyocr/static/description/index.html` (sin scripts, imágenes relativas dentro del módulo) |
| Icono | `static/description/icon.png`, **100x100**, como los módulos oficiales de Odoo |
| Icono en grande | `static/description/icon_hi.png`, 512x512 |
| Portada y capturas | La clave `images` del manifiesto: la **primera** es la portada del catálogo, las demás van a la galería |
| Nombre, resumen, categoría | Manifiesto: `EasyOCR Invoice Capture`, `Accounting/Accounting` |
| Autor y soporte | `author`, `website`, `support` (`info@easysoft.es`) |

Sin las tres primeras, la revisión de Odoo contesta «the module has no icon»,
«no cover image» o «non-html description»; están puestas por eso.

## Cómo se envía

La tienda no tiene API de publicación: el alta es darle la **URL del
repositorio** y la **rama** en <https://apps.odoo.com/apps/upload>, y a partir de
ahí ella clona y escanea por su cuenta. Por eso lo hace la skill
`publicar-modulo-odoo-apps` (`auth`, `repos`, `register`, `scan`), y por eso el
ZIP no es el canal de publicación.

1. Se registra una vez por rama: `19.0` alimenta la versión de Odoo 19 y `18.0`
   la de Odoo 18. El mismo nombre técnico en todas las ramas **es una sola ficha
   con una versión por serie**, así que se registran las cinco. La URL va en forma
   ssh, con la rama detrás de la almohadilla:
   `ssh://git@github.com/EasySoft-Tech-SL/odoo-easyocr-module.git#19.0`.
2. La tienda vuelve a escanear a su ritmo (horas o días): la ficha no cambia en
   el momento. El escaneo se puede forzar desde el panel de cada repositorio.

## El layout: el módulo va en la RAÍZ del repositorio

Medido el 12-oct-2026 en el primer escaneo real, con el módulo todavía en
`addons/easyocr/`:

> No module found in repository ssh://git@github.com/EasySoft-Tech-SL/odoo-easyocr-module.git#19.0.
> Each module needs to be in a separate folder at the root of the repository,
> even if there is only one module.

La tienda lista los hijos directos de la raíz y **no recursiona**, igual que hace
Odoo con cada addons path. Así que el módulo se movió a `easyocr/` en todas las
ramas y todo lo que apuntaba a `addons/` se movió con él (el montaje de
`docker-compose.yml`, los dos workflows, `tools/` y el README). El ZIP no cambia:
ya llevaba `easyocr/` arriba, y el layout de la raíz es el que sirve para los dos
canales a la vez.

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
