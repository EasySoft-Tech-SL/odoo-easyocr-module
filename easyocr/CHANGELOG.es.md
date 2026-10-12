# Registro de cambios

Todos los cambios destacables de este módulo se documentan aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), y la numeración de versiones es la de Odoo:
`<odoo series>.<major>.<minor>.<patch>`.

Una sección por versión publicada, la más nueva arriba. El encabezado lleva la versión
del módulo sin la serie (1.0.9 es 19.0.1.0.9 en 19.0 y 18.0.1.0.9 en 18.0, ambas
publicadas el mismo día) y el día en que se publicó.

Este fichero viaja dentro del módulo: es lo que muestra la página Historial de cambios de
la configuración del módulo. Junto a él va una traducción al español, en `CHANGELOG.es.md`.

## [1.0.13] - 2026-10-12

### Cambiado

- **El módulo corre en cinco series de Odoo, de la 16.0 a la 20.0.** Una rama por serie,
  el mismo código en todas salvo donde una serie difiere de verdad: la etiqueta con la
  que se escribe una vista de lista, cómo declara sus modificadores una vista, cómo lee
  el cuerpo la ruta del webhook, y las plantillas de Odoo 20, que son Owl 3 y ya no Owl
  2. `docs/SERIES.md` es la lista de esas diferencias, medida en cada serie. Hasta ahora
  el módulo cubría la 18.0 y la 19.0.
- **Se llama EasyOCR Invoice Capture.** Ese es el nombre que muestran la ficha de la Apps
  Store, la lista de aplicaciones y las propias pantallas del módulo. El nombre técnico y
  la carpeta siguen siendo `easyocr`: son lo que una instancia instalada guarda en su
  base de datos, y cambiarlos dejaría a una actualización buscando un módulo que no está.
- **La ficha de la tienda abre con todo el flujo en una animación.** Tres pasos, del
  fichero al asiento, en unos segundos, en lugar de un párrafo pidiéndole al lector que
  se los imagine.

### Corregido

- **La pantalla de Facturas pedía un tipo de vista que su serie no tiene.** La acción
  declaraba su lista como `tree` en la 18 y la 19, donde la etiqueta es `list` desde la
  18, y el archivo llevaba la etiqueta `list` en la 16 y la 17, donde solo existe `tree`.
  Cada serie nombra ahora la vista que busca su propia versión de Odoo.
- **Un cuerpo de webhook que no es JSON salía como error de servidor.** Algo que
  publicara en el webhook un cuerpo que nadie puede leer recibía un 500, lo que invita al
  emisor a repetir la misma llamada ilegible. Ahora recibe un 400 y no se escribe nada en
  el registro.
- **Los botones de un lote no sabían si ya se había enviado.** Preguntaban por la
  referencia del lote en el servicio, un campo que ese mismo formulario esconde a quien no
  está en el grupo técnico. Odoo 16 se negaba a cargar la vista por ello, la 17 se negaba
  en `readonly`, y de la 18 a la 20 cargaba y decidía sobre un campo que a ese lector no se
  le había dado. Preguntan por la fecha de salida, que se escribe en el mismo momento y
  solo cuando el servicio ya ha tomado los ficheros, así que dice lo mismo. Una prueba lee
  las vistas y falla cuando una condición nombra un campo que su propia vista esconde.
- **El cliente web no arrancaba en la 16 y la 17.** Hasta la 17 el paquete del backend llega
  al navegador como script clásico, y un fichero solo se convierte en módulo si lo dice en
  la primera línea: `/** @odoo-module **/`. Todos los scripts del módulo empezaban con sus
  `import` y nada más, así que el navegador se paraba en el primero y dejaba la pantalla en
  blanco, sin nada en el registro que dijera por qué. Ahora el marcador abre los nueve en
  esas dos series; desde la 18 el paquete ya es un módulo y el marcador no aporta nada.
- **Las plantillas de la 16 no llegaban a la aplicación.** Odoo 16 las recoge solo con el
  selector `[t-name][owl]`, así que una plantilla escrita como en cualquier otra serie no
  llega a ningún sitio y la primera pantalla que la pide muere con "Missing template". El
  atributo está en las 13 plantillas de esa rama y solo en ellas; desde la 17 no se lee y el
  fichero se escribe como en las demás.
- **Las pantallas que preguntan por el grupo del lector preguntaban de la otra forma.** Hasta
  la 17 el usuario es un servicio cuyo `hasGroup` contesta con una promesa, y no existe
  `@web/core/user`: importarlo dejaba al módulo con una dependencia sin resolver y ninguna
  de las dos pantallas cargaba. Desde la 18 es al revés. Cada rama toma el usuario de donde
  lo guarda su propia serie.
- **La pantalla de configuración no se dibujaba en la 16.** El registro de widgets de vista
  guarda el propio componente hasta la 16 y un envoltorio `{ component: ... }` desde la 17,
  y escrito al revés la pantalla no se dibuja: la 16 lanza "C is not a constructor" y las
  series nuevas no dicen nada.
- **Una prueba lee las cuatro cosas de los ficheros.** `tests/test_easyocr_assets.py` es el
  mismo fichero en las cinco ramas y comprueba solo lo que lee la serie en la que corre, así
  que una regla copiada de la serie de al lado falla ahí y no en una pantalla en blanco.

## [1.0.12] - 2026-10-12

### Cambiado

- **La carpeta del módulo está ahora en la raíz del repositorio, que es donde la Odoo
  Apps Store la busca.** La tienda lee los hijos directos de la raíz del repositorio y no
  baja más, así que `addons/easyocr/` le salía como "No module found in repository". Las
  herramientas que apuntaban a `addons/` se han movido con el módulo: el empaquetador, los
  dos workflows, el `docker-compose.yml` local y el README. No ha cambiado nada de lo que
  hace el módulo, y lo único distinto dentro del ZIP de la release es el número de versión.

## [1.0.11] - 2026-10-12

### Cambiado

- **La página Acerca de se lee en el idioma del lector.** Dibujaba el README del
  módulo en inglés sea cual sea el idioma de la pantalla, lo que dejaba la única
  página que explica el módulo como la única que un lector en español tenía que
  tragarse en un idioma que no es el suyo. El fichero viaja ahora en el mismo par
  que el historial, y una prueba mantiene los dos al mismo paso.

### Corregido

- **Dos campos de un modelo compartían etiqueta, y Odoo avisaba en cada
  instalación.** El número de líneas de un documento y sus líneas salían ambos como
  "Líneas", y el número de documentos de un lote y sus documentos, ambos como
  "Documentos". Ahora son "Número de líneas" y "Número de documentos", que es además
  lo que permite distinguir los unos de los otros en pantalla.
- **El README del repositorio apuntaba a una captura que no está.** El fichero se
  renombró en la guía de usuario y el README se quedó con el nombre viejo, así que
  GitHub dibujaba el pie sobre un recuadro vacío.

## [1.0.10] - 2026-10-11

### Cambiado

- **Las páginas de configuración llevan el aspecto de Odoo, no el del módulo de
  Dolibarr.** Los títulos del historial y del README salían dibujados con los pesos
  y los colores del módulo del que esto es un port, lo que dejaba cada uno más
  pequeño y más claro que el texto que encabeza, y la fila de cabecera de las
  tablas conservaba su barra gris. Ahora ambos son lo que Odoo da a un título y a
  una tabla en cualquier otra pantalla de sus ajustes.
- **El historial es una sección por versión publicada.** Era un único bloque con
  todo lo que había desde la primera entrega, así que la página no tenía ni versión
  ni día de los que tirar. Está recompuesto desde el historial del propio
  repositorio: una sección por versión, la más nueva arriba, cada una con el día en
  que salió.
- **El historial se pliega, un bloque por versión, con la más nueva abierta.** Un
  fichero que crece con cada entrega se lee por arriba; el resto queda a un clic.

### Corregido

- **La página de licencia mandaba al lector a un sitio web que nunca respondió.** La
  dirección del producto estaba escrita como un subdominio de la de la empresa. Es
  `easyocr.es`.
- **El historial se leía en inglés sea cual sea el idioma del lector.** Ahora viaja
  en inglés y en español, y una prueba mantiene los dos al mismo paso, para que una
  versión no caiga en un fichero y no en el otro.

## [1.0.9] - 2026-10-11

### Corregido

- **Las cinco páginas de configuración se dejaban atrás la pantalla de ajustes.** Cada
  página se abría como una pantalla propia, y el menú de la izquierda pertenece a la
  pantalla de ajustes, así que se iba con ella. Ahora las páginas se pintan dentro de la
  pantalla de ajustes, bajo la barra de pestañas, y el menú se queda donde está.
- **Esas páginas no se podían desplazar.** Odoo fija la altura de una pantalla y deja el
  desplazamiento al panel de ajustes; una pantalla propia no tiene ese panel. Una página
  más larga que la ventana mostraba la parte que cabía y nada por debajo. Ahora la página
  se pinta dentro de ese panel, así que es el panel el que la desplaza.
- **Una página mostraba lo que le había pedido la pestaña anterior.** Abrir el historial de
  cambios justo después del plan decía "No se encuentra el historial de cambios", porque la
  barra de pestañas reutilizaba la página en vez de pintar una nueva y lo que contenía
  seguía siendo la respuesta del plan. Ahora cada pestaña es una página propia.

## [1.0.8] - 2026-10-10

### Añadido

- **Páginas de configuración.** Las pestañas que el módulo del que este es un port tiene
  sobre su configuración: Configuración, Plan de Servicio, Acuerdo de Licencia, Telemetría
  y Protección de Datos, Acerca de e Historial de cambios, bajo un menú Configuración
  propio y solo para responsables de EasyOCR. La página del plan pregunta al servicio por
  la cuenta, la suscripción, la cuota mensual, las estadísticas, los límites y el monedero,
  y distingue una clave rechazada de un servicio caído. La página de telemetría dice qué
  envía realmente este módulo, incluido si va también nuestro propio nombre.
- **Pruebas.** 274, que cubren cada opción por su efecto y no por su valor, y cada una
  comprobada hasta fallar cuando se rompe lo que vigila. Eso incluye lo que una plantilla
  le pide a un componente: un binding que nombra algo que el componente no tiene no da
  error en ninguna parte, y uno de ellos dejó un botón en el fichero y en ninguna pantalla
  hasta que se midió.

### Corregido

- **El bloque de IA y el pie se iban con los campos al desplazar.** Ahora, en la columna
  derecha del visor, solo se desplaza la parte central, como en el módulo del que este es
  un port: el aviso de IA se queda arriba, y las acciones, la ayuda y los atajos abajo.
- **Guardar una plantilla encima de la que estaba en uso proponía un nombre nuevo.** Ahora
  el diálogo ofrece el nombre de la plantilla que se había aplicado.

## [1.0.7] - 2026-10-09

### Corregido

- **Una plantilla elegida en el desplegable volvía sin recuadros.** El desplegable entrega
  su valor como texto, y el servidor buscaba la plantilla por ese texto y no encontraba
  nada. Ahora los ids se leen como números en ambos lados, y el desplegable de proveedores
  tenía el mismo fallo.
- **Las etiquetas de nombre tapaban el recuadro vecino.** En campos impresos a una línea de
  distancia, la etiqueta de un recuadro se posaba sobre el recuadro de arriba. Ahora cada
  etiqueta va donde no tapa ningún otro recuadro ni otra etiqueta: arriba, abajo o al lado.
- **Un recuadro leía la línea de debajo.** Un campo dibujado alrededor de una línea también
  se llevaba la línea que solo rozaba ("01/07/2026 02/07/2026"). Ahora una línea cuenta
  solo cuando la mayor parte queda dentro del recuadro.
- **Dibujar junto a un recuadro se apoderaba de su esquina.** Con un campo elegido, ahora
  solo agarra el cuadradito pintado de la esquina; en cualquier otro punto, la pulsación
  dibuja.

## [1.0.6] - 2026-10-09

### Corregido

- **La propia descripción del módulo decía que no podía leer nada.** El README que se
  distribuye dentro del módulo seguía listando la extracción y la creación de facturas como
  pendientes. Ahora dice qué hace el módulo y cómo configurarlo.

## [1.0.5] - 2026-10-09

### Corregido

- **Capturas de pantalla rehechas sobre una factura inventada.** La galería de la Apps
  Store y la guía de usuario mostraban un presupuesto real, con el nombre y el NIF de un
  cliente real, y una interfaz que ya no es la del módulo. Ahora todas las capturas se
  toman de las pantallas actuales y sobre un proveedor ficticio.
- **Palabras escritas directamente en las vistas llegaban a la pantalla en inglés.** La
  ayuda o la etiqueta propia de una vista es un término suyo, que se busca bajo esa vista:
  la explicación del ajuste de borrador, el historial de lotes y sus botones, y el ejemplo
  de las instrucciones de IA se quedaban en inglés en una pantalla en español. Ahora todos
  ellos los comprueba una prueba.

## [1.0.4] - 2026-10-09

### Corregido

- **Hacer la factura desde el resultado de la lectura solo decía que había fallado.** Un
  proveedor que nadie tenía en ficha paraba la factura, y el diálogo se tragaba el motivo.
  Ahora el proveedor se crea con lo que se leyó (nombre, NIF, dirección, población, código
  postal, país, teléfono y correo), como hace el módulo del que este es un port, y cuando
  el servidor sí rechaza, el diálogo dice por qué.
- **El resultado de la lectura, rehecho.** Cada tarjeta es una rejilla de campos
  etiquetados; los que llegan a la factura (número de factura, fechas, datos del proveedor)
  se pueden corregir ahí y se escriben primero en el documento. El NIF del proveedor dice
  si el contacto existe o se va a crear. Las líneas llevan código, producto, tipo, cantidad,
  precio, descuento, IVA, RE, IRPF y su total, en el formato numérico del propio lector, y
  aparece un aviso cuando no cuadran con los totales del documento. El pie agrupa estado,
  diario y tipo de documento (factura o rectificativa), y el pago usa el método y el banco
  elegidos, o el diario de banco de la compañía. El IVA, el RE y el IRPF escritos en una
  línea se convierten en los impuestos de la compañía con esos tipos, que las líneas
  editadas perdían antes. El diálogo se puede usar con el teclado: Esc lo cierra,
  Ctrl+Enter hace la factura, Tab se queda dentro, y cada control tiene un nombre que lee
  un lector de pantalla.
- **El diálogo del resultado de la lectura no se cerraba.** Se abre en el área principal,
  donde el "cerrar" propio de Odoo no hace nada, así que la cruz, Cancelar, Esc y un clic
  fuera lo dejaban en pantalla. Ahora vuelve a la pantalla de la que salió.
- **Guardar una plantilla no pedía nunca su nombre.** El visor leía la función que cierra
  el diálogo como si fuera la respuesta, así que toda plantilla se guardaba sin mostrar el
  diálogo y con el nombre "removeCurrentOverlay". Ahora el diálogo se abre, y su nombre, su
  proveedor y sus instrucciones son lo que se guarda. Además, el desplegable de plantillas
  muestra la plantilla en uso en vez de "Sin plantilla".
- **Cuatro rótulos del visor se quedaban en inglés.** "Invoice date", "Total excl. tax",
  "Total price" y "Tax amount" tenían su traducción, pero Odoo solo envía al navegador los
  términos a los que apunta un script o una plantilla, y estos solo apuntaban a un modelo.
  Ahora todos los términos que pide un script los comprueba una prueba.
- **El visor y la pantalla de lotes no se abrían en modo depuración.** Odoo entrega a una
  acción de cliente más propiedades de las que listaban, y en modo depuración eso los
  detiene en seco.
- **Un recuadro estirado más allá de su esquina opuesta se convertía en una línea.** Empezar
  un recuadro nuevo junto a uno viejo podía agarrar su esquina y aplastarlo a nada. Ahora un
  estirón que deja un recuadro por debajo del mínimo se deshace, y dibujar un recuadro
  suelta el campo, como hace Dolibarr.
- **Detalles de redacción.** El botón del documento dice "Extraer con IA" como el del visor;
  la nota bajo el aviso de IA ya no apunta a un botón que no está cuando el servicio está
  apagado; y un nombre terminado en punto ya no se lee "S.L.." en el aviso de ya leído.

## [1.0.3] - 2026-10-09

### Corregido

- **Alineado con el módulo del que es un port.** La portada, el visor, el resultado de la
  lectura, las plantillas, las facturas, el registro de webhooks, la pantalla de lotes y
  los ajustes ahora se leen como los del módulo de Dolibarr, pantalla a pantalla: las
  mismas etiquetas, las mismas secciones, el mismo teclado y el mismo orden, en los siete
  idiomas. El resultado de la lectura ganó sus tarjetas plegables y su payload sin procesar,
  sus líneas editables y el pago, y el visor su lista de comprobación, la cuota, las
  instrucciones de IA, el desplegable de proveedores y deshacer.

## [1.0.2] - 2026-10-08

### Añadido

- **El banco de trabajo.** Una sola pantalla para todo el trabajo: se abre esperando un
  fichero (abrirlo o arrastrarlo, desde la primera tarjeta de la aplicación) y se convierte
  en el visor en el sitio en cuanto se elige uno. El fichero a la izquierda, y a la derecha
  la columna que tiene el módulo del que este es un port: el aviso de IA con el plan y lo
  que queda de la cuota mensual, leer con IA (que lo dice cuando la cuenta no puede leer),
  los nueve campos sobre los que dibujar un recuadro, la plantilla, los valores leídos de
  cada recuadro (tomados de la propia capa de texto del PDF) y un pie con las dos acciones
  que terminan el trabajo, guardar la plantilla y hacer la factura. Conserva alrededor la
  navegación propia de Odoo, para que los menús sigan a mano, y lleva un camino de vuelta
  al documento al que pertenece.

### Corregido

- **El visor escondía los menús de Odoo.** Se abría a pantalla completa, así que la
  navegación propia de la aplicación (y con ella todas las demás pantallas) desaparecía
  hasta que quien lee salía del visor. Ahora se abre dentro de Odoo con los menús en su
  sitio, y su barra lateral es la que tiene el módulo del que este es un port: el plan y lo
  que queda de la cuota arriba de la columna, y el teclado detallado abajo (1-8 elige un
  campo, Ctrl+S guarda la plantilla, Ctrl+Enter hace la factura, Esc suelta el campo).

## [1.0.1] - 2026-10-08

### Añadido

- **Documentos.** Modelo con el fichero, el proveedor, las fechas y los importes, un flujo
  de estados (pendiente / recibido / procesado), una secuencia, las líneas de proveedor
  leídas del documento y una huella del fichero para que un documento ya leído se reconozca
  cuando vuelve.
- **Volver a leerlo, a propósito.** Un fichero cuya huella ya se leyó no se lee una segunda
  vez a espaldas de quien lee, y tampoco se rechaza: el módulo cuenta lo que sabe de la
  lectura anterior (el fichero, el día y la factura en que quedó) y pregunta. Sí lo lee otra
  vez y cuesta una lectura; dejarlo estar no cuesta nada y deja el documento exactamente
  como estaba. La pregunta es la misma desde el formulario y desde el visor.
- **Bandeja de entrada de documentos.** Lo que entrega otro módulo antes de que nadie lo
  haya mirado, con su propia lista, su formulario y su búsqueda.
- **Ver una lectura trabajar.** Leer un escaneo tarda segundos y el botón que lo arrancó se
  queda muerto mientras corre, lo que antes dejaba la pantalla sin decir absolutamente nada.
  Una barra recorre las etapas de una lectura (el fichero que sale, el texto que vuelve, los
  campos que se van calculando) y se queda antes del final, porque una barra que se llena
  antes de que llegue la respuesta es una mentira que quien lee pilla.
- **Lo que encontró la lectura.** Una lectura termina en una pantalla, no en un aviso
  fugaz: de qué estaba seguro el servicio, cuánto tardó, cuánto costó en tokens y páginas,
  y los datos del proveedor que se habían leído y se tiraban porque el documento no tiene
  campo para ellos: la dirección, la población, el teléfono, el correo y la forma de pago
  que quiere. Desde ahí, un botón abre el documento para hacer el asiento.
- **Plantillas por proveedor.** Los recuadros dibujados sobre el papeleo de un proveedor se
  guardan bajo ese proveedor, así que la siguiente factura del mismo proveedor se abre con
  ellos ya pintados y su texto leído del fichero nuevo. El proveedor se resuelve en el
  servidor, primero por NIF y luego por nombre, ya que un documento no tiene ninguno propio
  hasta que se convierte en factura.
- **Recuadros que se mueven y se redimensionan.** Un recuadro ya dibujado se arrastra desde
  dentro para moverlo, o se estira desde uno de los cuadraditos de sus esquinas para cambiar
  su tamaño, y el texto que hay debajo se lee otra vez al soltar. Un recuadro no puede salir
  de la página: fuera de ella no hay nada que leer ni nada a lo que agarrarse.
- **Leer sin el servicio.** Los recuadros dibujados sobre una página llenan el documento con
  lo que leen, y eso no cuesta nada porque el texto ya estaba en el fichero: un importe
  impreso "320,77 EUR" y una fecha impresa 30/09/2026 se leen como tales, y un recuadro que
  no leyó nada deja su campo en paz en vez de vaciarlo. La fecha en que el proveedor quiere
  que se le pague, que el servicio siempre devolvía y nada guardaba, ahora se guarda y va en
  la factura.
- **Leer con el servicio.** Cliente para el servicio de extracción de EasyOCR, con un botón
  "Probar la conexión" en los ajustes que comprueba la clave sin gastar una lectura, y
  mensajes en lenguaje llano para cada forma en que el servicio puede rechazar un documento.
- **Lotes.** Los documentos de una carpeta entregados en una sola llamada. Los ficheros se
  eligen y se nombran en una pantalla propia y se quedan en la página hasta que se pulsa
  Enviar, que es donde se pagan las lecturas, todas de golpe. El servicio toma la pila
  entera en una sola petición y responde enseguida. Después la pantalla sigue el lote, dice
  por dónde va y qué volvió de cada fichero, y las lecturas caen sobre los propios
  documentos, listas para revisar. Un fichero ya leído se retiene y se pregunta por él, con
  las dos respuestas que prometen los botones: enviarlo igualmente, o dejarlo fuera y enviar
  el resto. Un lote que nadie está mirando lo recoge una tarea programada, y un webhook
  sobre el lote se archiva en cuanto el servicio lo dice.
- **Facturas.** Una factura de proveedor en borrador a partir de lo leído, una línea por
  línea leída, con el producto, el descuento y el tipo de cada una. Un documento que volvió
  sin nada más que sus dos importes sigue teniendo su impuesto: el tipo se deduce de ellos,
  y se usa cuando la compañía tiene ese impuesto exacto. Confirmación opcional, y el
  proveedor emparejado por NIF.
- **Facturas rectificativas.** Una rectificativa, que es el mismo documento con importes
  negativos, se convierte en factura rectificativa de proveedor en vez de en factura, con
  sus asientos al revés y el impuesto aún en la línea. La lectura lo activa por sí sola
  cuando el total vuelve negativo, y se puede poner a mano.
- **Tickets de gasto fotografiados.** Una página de captura para el móvil, que archiva la
  foto y se la entrega al módulo; el ticket puede acabar como factura de proveedor o como
  gasto de empleado. Cualquiera de los dos se puede cargar a un proyecto: el documento lleva
  la cuenta analítica que guarda el proyecto, y no hace falta ninguna aplicación aparte para
  eso. El campo aparece en el formulario del documento para las compañías que llevan
  contabilidad analítica, que es de lo que está hecho un proyecto en Odoo; una compañía que
  no la lleva nunca lo ve, y el formulario se abre igual.
- **Webhooks.** Un registro de cada llamada que hace el servicio, y la opción de crear la
  factura y registrar su pago sin nadie delante de la pantalla.
- **Ajustes.** Dieciséis opciones sobre el servicio, en qué se convierte un documento y qué
  puede hacer un webhook por su cuenta.
- **Idiomas.** Español, catalán, gallego, alemán, francés, italiano y portugués, con una
  prueba que comprueba que cada término llega a quien lee: etiquetas de campo, textos de
  ayuda, etiquetas de selección, nombres de modelos y de acciones, las frases que el módulo
  escribe en tiempo de ejecución, las palabras que pintan sus propias plantillas, y las
  etiquetas de los campos que toma prestados de Odoo y pone en pantalla.
- **CI.** Comprobación de sintaxis de Python, del manifiesto y de la estructura, y de que el
  XML está bien formado en las dos ramas.

### Corregido

- **Una instalación limpia de una versión publicada se paraba en seco.** Cada menú del
  módulo cuelga del menú raíz que lleva el nombre del módulo, y ese menú estaba declarado al
  final de las vistas de documentos. La pantalla de inicio también cuelga de él y se carga
  antes, así que instalar el ZIP publicado desde cero acababa en un `ParseError` al analizar
  la primera pantalla del módulo. Una actualización nunca lo mostraba, porque el menú ya
  estaba en la base de datos de una instalación anterior. Ahora el menú raíz vive en un
  fichero propio y es lo primero que carga el módulo.
- **El camino de vuelta desde el visor estaba en el fichero y en ninguna pantalla.**
  Colgaba de un nombre que el componente nunca pone en su estado, así que la condición era
  falsa para siempre y no se pintaba nada. Se encontró mirando la pantalla, y lo mantiene
  encontrado una prueba que lee cada binding de cada plantilla contra los componentes.
