---
title: EasyOCR para Odoo — Guía de usuario
subtitle: Leer facturas de proveedor y tickets desde Odoo
version: 19.0.1.0.0
date: 2026-10-07
author: EasySoft Tech S.L.
---

[[TOC]]

[[TOF]]

# 1. Qué hace EasyOCR y qué necesita

EasyOCR lee las facturas de proveedor y los tickets de gasto que llegan en PDF o
en foto, saca de ellos el proveedor, el número, la fecha y los importes, y con
esos datos prepara la factura de proveedor en Odoo.

Funciona con documentos de dos clases:

- **PDF que ya llevan texto** (los que le envía un proveedor por correo
  electrónico). Estos se leen siempre, sin coste y sin conexión a nada.
- **Escaneos y fotos** de papel, que son una imagen y no llevan texto dentro.
  Para leer estos hace falta el servicio de EasyOCR.

## Lo que necesita para funcionar

El módulo se instala y funciona solo. Puede usarlo para leer PDF con texto
desde el primer día, gratis y sin configurar nada.

Lo que **no** puede hacer por sí solo es leer un escaneo o una foto: eso lo
resuelve el servicio de extracción de EasyOCR, y **hasta que no lo configure,
los escaneos y las fotos no se leerán**. Si pulsa «Leer con IA» sin haberlo
configurado, el módulo se lo dirá con este aviso, sin más consecuencias:

!["Aviso de que la extracción con IA está desactivada"](img/10-ia-apagada.png)

Cuando eso ocurre no se pierde nada: el documento se queda donde estaba, con el
archivo adjunto intacto, y puede leerlo a mano o volver a intentarlo más tarde.

## Lo que cuesta

El módulo es **software libre**, con la misma licencia que el propio Odoo. No
hay nada que pagar por él y el código fuente completo va con cada versión.

Lo que se contrata aparte es **el servicio de lectura**. Si trabaja solo con PDF
que ya traen texto, no necesita contratar nada.

# 2. Instalación

El módulo se llama **EasyOCR** y se instala como cualquier otra aplicación de
Odoo: entre en **Aplicaciones**, borre el filtro «Aplicaciones» y busque
«EasyOCR».

![La aplicación EasyOCR en la pantalla de Aplicaciones](img/01-instalacion.png)

Sobre la ficha verá el botón para instalarla. Si ya está instalada, la ficha se
limita a ofrecerle más información, como en la imagen.

Al terminar la instalación aparece una aplicación nueva llamada **EasyOCR** en
el menú principal. Al abrirla entra en su pantalla de inicio:

![La pantalla de inicio de EasyOCR](img/02-inicio.png)

Arriba del todo están los números: cuántos **documentos** hay, cuántos han
acabado en **factura** y cuántas **plantillas** tiene guardadas. Cada uno es
también un atajo: púlselo y va a su lista.

Debajo, cada tarjeta lleva a un sitio:

- **Subir un documento** — elige un PDF o una foto y el visor se abre con él
  dentro. Es el camino corto para meter una factura a mano.
- **Documentos** — las facturas y tickets leídos, o esperando a leerse.
- **Bandeja de entrada** — lo que le han entregado otros módulos y todavía
  nadie ha mirado.
- **Capturar un recibo** — la página del móvil, para fotografiar un ticket.
- **Plantillas** — los recuadros guardados de cada proveedor.
- **Facturas de proveedor** — las facturas de compra, donde han ido a parar los
  documentos que ha facturado.
- **Registro de webhooks** — las llamadas que ha hecho el servicio.
- **Ajustes** — solo aparece si usted puede configurar el módulo.

El **Abrir** de cada tarjeta, con su flecha, indica que la tarjeta entera se
pulsa; no hay que apuntarle a nada en concreto.

Los permisos van en dos niveles: **Usuario** (trabajar con documentos) y
**Responsable** (además, configurar y lanzar la lectura con IA). Se asignan
desde **Ajustes > Usuarios**, como cualquier otro permiso de Odoo.

# 3. Configuración

La configuración vive en **Ajustes > EasyOCR** y viene en dos bloques.

![La sección EasyOCR en Ajustes](img/03-ajustes.png)

## Leer con IA

|[tabla: Opciones del servicio de lectura]|
|---|---|
| **Leer con IA** | Enciende o apaga el envío de documentos al servicio. Mientras está apagado, el módulo no manda nada a ningún sitio. |
| **URL del servicio** | La dirección del servicio de EasyOCR. Se escribe sin nada más: el módulo añade por su cuenta la parte final de la dirección. |
| **Clave API** | La clave que identifica su cuenta ante el servicio. Se la da EasyOCR al contratar el servicio. |
| **Probar la conexión** | Comprueba la clave contra el servicio y dice si vale. Está justo debajo de la clave y **no gasta ninguna lectura**. |
| **Tiempo de espera** | Cuántos segundos espera Odoo la respuesta antes de darse por vencido. Una página escaneada puede tardar, así que conviene dejarlo generoso. |
| **Decirle al servicio quiénes somos** | Añade el nombre y el NIF de su empresa a la petición, para que el servicio distinga las dos partes del documento y no le devuelva su propia empresa como proveedor. |

### Probar la conexión

![El botón Probar la conexión junto a la clave API](img/18-probar-conexion.png)

Antes de leer el primer documento, pulse **Probar la conexión**. Pregunta al
servicio a nombre de quién va esa clave, y contesta una de estas cosas:

| **La cuenta y el plan** | La clave vale. Además dice cuántas páginas le quedan este mes. |
| **El servicio ha rechazado la clave API** | La clave no es válida, o es de otra cuenta. Cópiela otra vez desde el panel de EasyOCR. |
| **El servicio no se ha podido alcanzar** | La dirección del servicio no es correcta o no hay conexión. |
| **El servicio necesita una clave API** | No hay ninguna escrita en la casilla. |

Esta comprobación **no consume ninguna lectura**: solo pregunta quién es, no
manda ningún documento. Por eso se puede pulsar tantas veces como haga falta.

## Documentos y facturas

|[tabla: Qué hace el módulo con lo que lee]|
|---|---|
| **Confirmar la factura automáticamente** | Confirma la factura en cuanto se crea, en lugar de dejarla en borrador. Apagado viene: confirmar contabiliza la factura y le pone número. Si al confirmar falla algo, la factura se queda en borrador con el motivo escrito en ella. |
| **Crear los productos que no existan** | Cuando una línea trae una referencia de proveedor que no casa con ningún producto, lo crea. Apagado viene, para que el catálogo no crezca solo. |
| **Aceptar nuestra propia empresa como proveedor** | Permite contabilizar un documento cuyo NIF sea el suyo. Apagado viene, porque casi siempre es un documento que se ha leído al revés. |
| **Rechazar un documento ya leído** | Antes de enviar un archivo al servicio, busca otro documento con el mismo contenido que ya se haya leído y no lo manda. Encendido viene: leerlo otra vez costaría lo mismo y no cambiaría nada. |
| **Ventana de duplicados** | Hasta dónde mira esa comprobación, en días. 0 significa sin límite. Sirve para un proveedor cuyo documento mensual es exactamente el mismo archivo cada mes. |

## Tickets fotografiados

|[tabla: Dónde acaba un ticket fotografiado desde el móvil]|
|---|---|
| **Un ticket fotografiado acaba en** | **Factura de proveedor** (viene así) o **gasto de empleado**. Una factura de proveedor necesita un proveedor; un ticket de gasolinera no lo es, así que el gasto de empleado suele encajar mejor cuando quien hace la foto es quien ha pagado. |
| **Dejar que el móvil envíe el gasto** | Permite que quien hizo la foto presente el gasto para aprobación en ese momento, en lugar de dejarlo en borrador hasta que entre en Odoo. Aprobar sigue siendo cosa de quien aprueba: nadie aprueba su propio gasto. |

Para el gasto de empleado hace falta que quien fotografía tenga **ficha de
empleado** en Odoo. Si no la tiene, el ticket se guarda igual y la página del
móvil se lo dirá, en lugar de perderse.

## Webhooks

Estos tres solo importan si va a recibir documentos por la vía automática, sin
nadie delante. De serie, un aviso del servicio **solo deja el documento**: no
factura nada.

|[tabla: Qué puede hacer un aviso del servicio por su cuenta]|
|---|---|
| **Crear la factura desde un webhook** | Cuando el servicio avisa de que ha terminado de leer, crear la factura sin esperar a nadie. Apagado viene: un webhook es un mensaje de fuera y una factura es un apunte contable. |
| **Marcar la factura como pagada** | Registrar el pago en esas facturas, como si el dinero ya hubiera salido. Solo se aplica a una factura confirmada: una en borrador no tiene contra qué pagarse, y el registro lo dirá. |
| **Cuenta bancaria** | Dónde se registra ese pago. |
| **Forma de pago** | Cómo se registra en esa cuenta. Si se deja vacío, Odoo coge el que la cuenta tenga por defecto. |

Cuando termine, pulse **Guardar**. El botón **Descartar** deja todo como estaba.

**Nada de esto hace falta si solo va a leer PDF que ya traen texto.** Deje
«Leer con IA» apagado y el módulo funcionará igual.

## Un ajuste que no está en esta pantalla

Si va a recibir documentos desde el servicio por la vía automática —sin nadie
delante— hay un quinto ajuste que no tiene casilla en la pantalla: el **secreto
compartido**. Se guarda como parámetro del sistema, con el nombre
`easyocr.webhook_secret`.

Mientras ese valor no exista, la dirección que recibe los avisos del servicio
rechaza **todas** las llamadas. Es deliberado: un secreto con un valor por
defecto no es un secreto, así que el módulo prefiere quedarse cerrado antes que
abierto. Si no va a usar esta vía, no tiene que hacer nada.

# 4. Dónde viven los documentos

## Meter un documento: un paso

Desde la pantalla de inicio, **Subir un documento** es el camino corto: elige
el PDF o la foto y **el visor se abre con el documento dentro**. No hay que
crear una ficha, ni adjuntar el archivo, ni guardar antes.

![El diálogo de subir un documento](img/17-subir-documento.png)

La **Referencia** se rellena sola con el nombre del archivo; cámbiela si quiere
otra cosa. Al pulsar **Abrir el visor**, el documento queda guardado y ya está
en el visor, listo para dibujar los recuadros o para mandarlo leer.

Esto **no llama al servicio**: abrir un archivo no es pedir que se lea.

## La lista de documentos

Lo mismo se puede hacer desde **EasyOCR > Documentos**, que es donde están
todos los documentos y donde se vuelve a ellos después.

![La lista de documentos, con los tres estados](img/04-documentos.png)

La lista tiene una columna **Estado** con tres valores posibles:

- **Pendiente** (en negro): el archivo está dentro, todavía no se ha leído.
- **Procesado** (en verde): ya se ha leído y revisado.
- **Error** (en rojo): se intentó leer y no se pudo. El motivo está en el propio
  documento, y se puede volver a intentar.

Puede buscar por referencia, proveedor o número de documento, y agrupar por
proveedor, estado o fecha desde los filtros de la barra de búsqueda.

Al abrir un documento, la ficha tiene los datos a la izquierda y los botones
arriba:

![La ficha de un documento pendiente](img/05-ficha-documento.png)

| **Abrir el visor** | Abre la pantalla grande donde se ve el documento y se dibujan las casillas. |
| **Leer con IA** | Manda el archivo al servicio. Solo aparece si hay archivo adjunto y si tiene usted el permiso de responsable. |
| **Crear factura** | Prepara la factura de proveedor con lo que hay en la ficha. |
| **Marcar como procesado** | Da el documento por revisado sin crear nada. |

Debajo, cuatro pestañas: **Líneas**, **Archivo** (el PDF), **Notas** y
**Extracción** (la respuesta del servicio y su nivel de confianza, útil solo
cuando hay que pedir soporte).

## Las líneas que se han leído

La pestaña **Líneas** es lo que el servicio ha sacado del documento, artículo a
artículo, y es de donde sale la factura:

![Las líneas leídas de un documento](img/16-lineas-leidas.png)

Cada línea trae su descripción, la referencia que el documento imprime, la
cantidad, el precio, el descuento y el tipo de IVA. **Se puede corregir
cualquier cosa aquí**: leer un documento mal es lo normal, y arreglarlo en esta
pestaña es más barato que arreglarlo luego en la factura. El **Importe neto** se
recalcula solo al cambiar la cantidad, el precio o el descuento.

Para quitar una línea que no debería estar, la papelera de su derecha. Para
añadir una que el servicio no vio, **Añadir una línea**.

Si el documento se lee otra vez, estas líneas se reemplazan por las de la nueva
lectura, no se suman.

# 5. El visor: dibujar de dónde se lee cada dato

El visor es la pantalla que da sentido al módulo. Se abre con **Abrir el visor**
y ocupa toda la pantalla: el documento a la izquierda, los datos a la derecha.

![El visor con el documento abierto y ningún campo marcado](img/06-visor-vacio.png)

Arriba hay una barra con nueve botones, uno por cada dato que se puede leer. El
color de cada botón es el color con el que se pintará el recuadro en el
documento, así que siempre se sabe qué recuadro es qué.

## El paso a paso

1. Pulse el botón del dato que quiere leer. Por ejemplo, **Proveedor**.
2. Con el botón pulsado, arrastre el ratón sobre el documento para dibujar un
   recuadro alrededor de ese dato. Como el recuadro se lee del texto que hay
   debajo, puede ajustarlo a una parte de la línea si le conviene.
3. Al soltar, el texto que ha quedado dentro aparece a la derecha, en la lista
   de datos.

Repita con los datos que le interesen. Así queda un documento con cinco campos
marcados:

![El visor con cinco campos marcados y sus valores a la derecha](img/07-visor-campos.png)

Si un recuadro no le convence, la **×** de su derecha lo quita. El botón
**Limpiar** borra todos de golpe.

A la derecha de la barra están los dos botones que cierran el trabajo, para que
no haya que salir del visor:

| **Leer con IA** | Manda el documento al servicio y rellena la ficha con lo que lea. Es lo mismo que el botón de la ficha del documento. |
| **Crear factura** | Prepara la factura de proveedor con lo que hay en la ficha y la abre. |

Mientras el servicio está leyendo, la barra lo dice y los botones quedan
bloqueados: una página escaneada tarda unos segundos, y es mejor saber que está
trabajando que pulsar dos veces.

Con esto ya tiene lo importante: los datos del proveedor leídos del documento,
sin teclear.

# 6. Guardar la plantilla del proveedor

Cuando los recuadros son los que quiere, póngale un nombre en la casilla
**Nombre de la plantilla** y pulse **Guardar plantilla**.

![El aviso de que la plantilla se ha guardado](img/08-plantilla-guardada.png)

La plantilla queda guardada en **EasyOCR > Plantillas**, con las casillas y las
coordenadas exactas de cada una:

![La ficha de una plantilla y sus casillas](img/09-plantilla-ficha.png)

**Conviene saberlo antes de contar con ello:** en esta versión la plantilla se
guarda, pero el módulo **todavía no la aplica solo** al siguiente documento del
mismo proveedor. Es decir, hoy la plantilla sirve como registro de dónde estaba
cada dato, pero los recuadros hay que volver a dibujarlos en cada documento.
Aplicarla automáticamente está en la hoja de ruta.

# 7. Leer un documento con IA

El botón **Leer con IA** es lo que lee los escaneos y las fotos. Manda el
archivo al servicio y rellena la ficha con lo que devuelve: nombre y NIF del
proveedor, número de documento, fecha, importe base y total.

Si sale bien, verá un aviso de que el documento se ha leído y los campos
rellenos. Si sale mal, el documento **no se pierde**: se queda con el motivo
escrito, y puede corregirlo a mano o volver a intentarlo.

## Cuando falla

Los avisos que se ve son estos:

|[tabla: Motivos por los que una lectura puede fallar]|
|---|---|
| **La extracción con IA está desactivada** | No está encendida la opción en Ajustes. Actívela y vuelva a intentarlo. |
| **El servicio no se ha podido alcanzar** | La dirección no es correcta o no hay conexión. Revise la URL del servicio. |
| **El servicio ha rechazado la clave API** | La clave no es válida o es de otra cuenta. |
| **El servicio está caído u ocupado** | Es temporal. Vuelva a intentarlo dentro de un rato. |
| **No se ha podido emparejar ningún proveedor** | La lectura fue bien, pero el NIF del documento no está en ningún contacto. Cree el proveedor o indíquelo a mano en la ficha. |

Un aviso que **no** es un error: cuando el servicio solo puede leer el documento
en parte, lo dice y añade si merece la pena volver a intentarlo. En ese caso los
datos que sí ha leído quedan puestos, y el resto se completa a mano.

# 8. Crear la factura de proveedor

Con la ficha rellena —por la lectura con IA o a mano— el paso final es **Crear
factura**.

![La ficha del documento con los datos leídos](img/11-ficha-rellena.png)

El módulo busca el proveedor por su NIF y, si no lo encuentra, por el nombre.
Después prepara un borrador de factura de proveedor con esos datos:

![El borrador de factura creado desde el documento](img/12-factura-borrador.png)

## Cómo se arma la factura

- **Una línea de factura por cada línea leída** en la pestaña **Líneas**, con su
  cantidad, su precio y su descuento. Un documento con cinco artículos da una
  factura con cinco líneas, no una sola con el total.
- **El producto** de cada línea se busca por la referencia que imprime el
  documento: primero entre las referencias de ese proveedor, después por nuestro
  código o código de barras. Si no aparece y tiene encendido *Crear los
  productos que no existan*, se crea.
- **El IVA** de cada línea sale del tipo leído en el documento, buscando el
  impuesto de compras de ese mismo tipo. Si su empresa no tiene ninguno
  configurado a ese tipo, la línea se queda sin impuesto: el módulo no se lo
  inventa.

Si el documento no trae líneas —porque llegó por la vía automática o porque se
rellenó a mano—, la factura se hace con una sola línea por el importe base, sin
impuestos, como se ha hecho siempre.

## Qué conviene revisar antes de confirmarla

- **El proveedor.** Si no existía, se ha creado al vuelo. Compruebe que no se ha
  duplicado con una ficha que ya tuviera.
- **Las líneas y sus impuestos.** Sobre todo si el documento lleva varios tipos
  de IVA o descuentos por línea.
- **La fecha y la referencia.** Son las del documento original.

La factura queda **en borrador**: no se ha contabilizado nada. Puede editarla
con calma y confirmarla cuando esté conforme.

El mismo documento no se puede facturar dos veces: si ya tiene factura, el botón
desaparece de la ficha.

# 9. La bandeja de entrada

Otros módulos pueden entregarle archivos a EasyOCR sin que nadie los suba a
mano: un lector de documentos, una pasarela de correo, la captura del móvil. Lo
que llega por esa vía aparece en **EasyOCR > Bandeja de entrada**.

![La bandeja de entrada con dos archivos pendientes](img/13-bandeja.png)

Cada línea dice **quién lo entregó** (la columna Origen), cuándo llegó y en qué
estado está.

Lo importante de la bandeja es lo que **no** hace: al recibir un archivo **no se
llama al servicio de lectura**. El archivo se queda ahí esperando a que alguien
decida leerlo. Así, recibir un archivo no cuesta nada.

Desde la bandeja puede procesar un archivo (lo convierte en documento y abre su
visor), descartarlo —sin borrar nada, se puede recuperar— o abrir el documento
que ya se creó a partir de él. Si el mismo archivo llega dos veces, se rechaza el
segundo: el módulo lo reconoce por su contenido, no por el nombre.

# 10. Capturar un ticket desde el móvil

Cualquiera con usuario en Odoo puede abrir la dirección `/easyocr/capture` en el
navegador del móvil y fotografiar un ticket. Está pensada para instalarse en la
pantalla de inicio del teléfono y usarse como una aplicación.

![La página de captura en un móvil](img/14-movil.png)

1. **Hacer una foto** abre la cámara. También puede **elegir una foto** que ya
   tenga en el teléfono.
2. La foto se encoge en el propio móvil antes de salir, para no gastar datos.
3. Al enviarla, queda en la bandeja de entrada, con origen `expense-capture`.

Si la lectura con IA está encendida, además se lee en el acto y la propia página
le enseña lo que se ha sacado del ticket. Si está apagada —como en la imagen—,
la foto se guarda igual y se lee a mano.

Si en **Ajustes > EasyOCR** ha puesto que un ticket fotografiado acabe en un
**gasto de empleado**, la página lo dirá y el gasto quedará creado a nombre de
quien hizo la foto, con la foto adjunta. Nada más: si quiere que además se
presente para aprobación sin abrir Odoo, encienda la casilla de al lado.

# 11. El registro de webhooks

Si el servicio de EasyOCR avisa a Odoo cuando termina una lectura, cada llamada
queda registrada en **EasyOCR > Registro de webhooks**.

![El registro de las llamadas recibidas](img/15-webhooks.png)

| **Recibido el** | Cuándo llegó la llamada. |
| **Evento** | Qué avisaba el servicio. |
| **Estado** | **Creado** si dio lugar a un documento, **Ignorado** si el aviso no era de los que se atienden, **Error** si el aviso llegó bien pero traía un valor ilegible. |
| **Documento del servicio** | El identificador que el servicio da al documento. |
| **Mensaje** | En palabras, qué pasó. |

Este registro es la única huella de las llamadas que no crearon nada, así que es
lo primero que hay que mirar si un documento leído por el servicio no aparece
por ninguna parte.

La columna **Mensaje** cuenta además lo que hizo el aviso cuando se le ha dado
permiso para ir más allá de dejar el documento: si creó la factura, si registró
el pago y, cuando no pudo, por qué. Por ejemplo, si pidió el pago pero la
factura se quedó en borrador, aquí lo dirá en lugar de quedarse callado.

# 12. Preguntas frecuentes

## He instalado el módulo y no lee mis escaneos

Es lo esperado. Un escaneo es una imagen, y para leerlo hace falta el servicio de
EasyOCR configurado y la opción **Leer con IA** encendida. Un PDF que ya trae
texto, en cambio, se lee sin configurar nada.

## ¿Puedo usar el módulo sin contratar el servicio?

Sí, para PDF que ya llevan texto. El módulo se instala, se usa y se lee igual;
lo único que no hará es leer fotos ni escaneos.

## Los recuadros de la plantilla no aparecen solos en el siguiente documento

Correcto, y es una limitación conocida de esta versión: la plantilla se guarda
pero todavía no se aplica sola. Hay que volver a dibujar los recuadros en cada
documento.

## El botón «Leer con IA» no me aparece

Ese botón es de **responsable**. Pídale a quien administra su Odoo que le asigne
el permiso, o que lance él la lectura. En el visor aparece junto a **Crear
factura**, a la derecha de la barra.

## He puesto la clave API y sigue sin leer

Vaya a **Ajustes > EasyOCR** y pulse **Probar la conexión**, justo debajo de la
clave. Le dirá si el servicio acepta esa clave, con qué cuenta y cuántas páginas
le quedan este mes, y **no gasta ninguna lectura**. Si contesta que la ha
rechazado, la clave no es válida o es de otra cuenta: cópiela otra vez desde el
panel de EasyOCR sin espacios delante ni detrás.

## ¿Qué pasa si la lectura se equivoca?

Nada irreversible. El módulo solo **propone**: rellena los campos de la ficha y
crea un borrador de factura. Nada se contabiliza hasta que usted confirma la
factura, así que siempre hay un momento para revisar y corregir.

## He creado una factura por error

La factura está en borrador. Bórrela como cualquier otra factura de proveedor en
borrador y vuelva a la ficha del documento: el módulo volverá a ofrecerle
**Crear factura**.

## ¿Se suben mis documentos a algún sitio?

Solo si usted lo pide. El módulo no manda nada al servicio hasta que se pulsa
**Leer con IA** —o hasta que llega una foto desde la captura del móvil con la
lectura encendida—. Recibir un archivo en la bandeja de entrada no envía nada.

---

*EasyOCR es una marca de EasySoft Tech S.L. Para soporte, escriba a
[info@easysoft.es](mailto:info@easysoft.es).*
