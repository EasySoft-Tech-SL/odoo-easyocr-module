# Paridad Dolibarr ↔ Odoo — plan de trabajo

Referencia: `D:\laragon\www\erp-v23\public\custom\easyocr` (Dolibarr 23.0.1).
Texto canónico: `langs/es_ES/easyocr.lang`. Estado: **en curso** (2026-10-09).

## Pantallas de Dolibarr

1. `index.php` — landing con tarjetas + contadores.
2. `extract.php` — el visor/workbench.
3. `batch.php` — envío por lotes + historial.
4. `scan-expense.php` — captura móvil de tickets.
5. `templates.php` / `templates_view.php` — listado y detalle de plantillas.
6. `invoices.php` — histórico de facturas generadas.
7. `webhook_logs.php` — log de webhooks.
8. `admin/setup.php` — configuración.

## 1. Landing (`index.php` → home de Odoo)

- [ ] Subtítulo: «Herramienta de extracción de contenido textual de archivos PDF para la creación automática de facturas de proveedor en Dolibarr.» (Odoo dice otra cosa).
- [ ] Contadores arriba: «N Facturas», «N Plantillas» (Odoo añade «N Documentos», Dolibarr no lo tiene).
- [ ] Sección «Accesos directos» con 7 tarjetas (título + descripción exactos):
  - Cargar Pdf — «Importa un PDF y extrae datos de facturas de proveedor de forma visual.»
  - Envío por lotes — «Procesa múltiples PDFs a la vez con extracción automática mediante IA.»
  - Escanear gasto — «Escanea un ticket de gasto desde el móvil y regístralo automáticamente.»
  - Plantillas — «Gestiona las plantillas de selección de zonas asociadas a proveedores.»
  - Facturas — «Consulta el historial de facturas generadas desde PDFs importados.»
  - Logs de Webhook — «Audita las notificaciones del webhook recibidas y revisa los fallos de procesamiento.»
  - Configuración — «Configura la clave API, el servicio en la nube y las opciones del módulo.»
- [ ] Odoo tiene «Documentos» y «Bandeja de entrada» como tarjetas que Dolibarr no muestra (decidir: quitar o integrar).

## 2. Visor (`extract.php` → visor OWL)

- [ ] **Etiquetas de campo** (9) distintas. Dolibarr: Con fecha de / Factura / HT totales / Precio total / IVA / Descripción / CIF/NIF / Vencimiento / Proveedor. Odoo: Fecha / Número de factura / Total libre de impuestos / Total / Impuesto / Descripción / NIF / Fecha de vencimiento / Proveedor. → Cambiar `BOX_FIELDS` en modelo + JS.
- [ ] Hint del hero IA: «Envía el PDF al servicio de IA para extraer datos automáticamente».
- [ ] Botón: «Extraer con IA» (Odoo: «Leer con IA»).
- [ ] Título de sección «Etiquetas» (Odoo: «Fields/Campos») + hint «Selecciona una etiqueta → Dibuja un rectángulo sobre el PDF».
- [ ] Título «Plantillas» + botón «Aplicar».
- [ ] Sección colapsable **Instrucciones IA** (falta).
- [ ] Sección colapsable **Metadatos PDF** (falta).
- [ ] **Selector de Proveedor** en «Datos extraídos» (falta).
- [ ] Checklist: título «Completitud» + «Completitud: N/5» (Odoo solo «N/5»).
- [ ] Hero IA: indicador de estado «✓ ✓ ✓» (plan/quota/wallet).
- [ ] **Barra de ayuda** como popup con 2 bloques (Atajos de teclado: 1-4, Ctrl+Z, Ctrl+S, Ctrl+Enter, Esc; Interacción: arrastrar PDF, dibujar, mover, redimensionar, zoom). Odoo tiene una línea.
- [ ] Atajos: `1-4` (no 1-8) + `Ctrl+Z` deshacer (falta).
- [ ] «Generar Factura» (F mayúscula).
- [ ] Footer: al elegir plantilla, «Editar plantilla» en vez de «Guardar plantilla».

## 3. Modal de resultado IA (`eo-modal-ai` → `ocr_result_dialog`)

- [ ] Título «Resultado IA» (Odoo: «What the reading found»).
- [ ] Meta pills: «confianza», «páginas» (nombres Dolibarr).
- [ ] Pie con **estado factura (Validada/Borrador)**, **diario**, **tipo documento**, **pago (modo + cuenta)** + «Cancelar» / «Crear factura». (Odoo solo Cancelar/Crear.)
- [ ] Tabla de líneas **editable** (añadir/quitar línea). (Odoo es de solo lectura.)
- [ ] Botón «Añadir línea».
- [ ] Botón «Aplicar datos» (aplicar a la ficha).

## 4. Confirmar factura (`eo-modal-confirm`)

- [ ] Modal «Confirmar generación de factura» con «Se creará una factura de proveedor con los siguientes datos:», tipo de documento (Factura de proveedor / Presupuesto de proveedor), «Crear pago asociado» (modo + cuenta), «Cancelar» / «Confirmar y Generar». (Odoo genera directo sin confirmar.)

## 5. Plantillas (`templates.php` → lista easyocr.template)

- [ ] Subtítulo + nota «Las plantillas se crean sobre un PDF: carga uno en el visor…».
- [ ] Columnas: Nombre, Proveedor, Instrucciones IA, Nº Campos, Creación.

## 6. Facturas (`invoices.php` → facturas de proveedor)

- [ ] Comparar columnas (Ref, Ref. Proveedor, Fecha, Tercero…).

## 7. Logs de webhook (`webhook_logs.php` → easyocr.webhook.log)

- [ ] Columnas: ID, Recibido, Evento, Batch, ID documento, Fichero, Estado documento, Estado proceso, Mensaje, Factura, Proveedor, Payload (JSON).
- [ ] Botón «Purgar registros >30 días».

## 8. Configuración (`admin/setup.php` → res.config.settings)

- [ ] Secciones: Configuración IA OCR (habilitar, URL, clave API, timeout) · Configuración general (borrador, auto-crear productos) · Pago automático webhook (marcar pagadas, cuenta, método) · Gastos de empleado (diana, validación).
- [ ] Enlace «Panel de gestión» / «Sitio web del servicio».

## Notas de implementación

- Los textos exactos salen de `easyocr.lang` (es_ES). Paridad i18n = copiar los msgids.
- Atajos y comportamiento (Ctrl+Z, 1-4) también cuentan como paridad.
- El orden de implementación: visor (2) → modal IA (3) → confirmar factura (4) → landing (1) → resto de listados/setup.
