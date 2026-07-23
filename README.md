# Clasificador de expedientes aduaneros

CLI que procesa un directorio de documentos de comercio internacional, los agrupa
en **expedientes** (identificados por su MRN) **por cliente**, y emite un informe
con el estado de cada expediente y las incidencias detectadas.

Prueba técnica para Omnesia. Sin base de datos, sin interfaz gráfica y sin
dependencias de terceros en tiempo de ejecución.

---

## Ejecución

Requiere Python ≥ 3.10. No hay nada que instalar.

```bash
# Por defecto: lee dataset/inbox y escribe en salida/
python3 -m expedientes

# Rutas explícitas
python3 -m expedientes --inbox dataset/inbox --salida salida

# Volcar el informe por stdout (el resumen va por stderr)
python3 -m expedientes --informe-stdout -q > informe.md

# Todas las opciones
python3 -m expedientes --help
```

| Opción | Efecto |
|---|---|
| `--inbox RUTA` | Directorio de entrada (defecto `dataset/inbox`). Solo lectura. |
| `--salida RUTA` | Directorio de salida (defecto `salida`). Se reconstruye en cada ejecución. |
| `--forzar` | Permite reconstruir un destino no vacío ajeno a esta herramienta. |
| `--informe-stdout` | Vuelca además el informe Markdown por salida estándar. |
| `--fallar-si-incidencias` | Devuelve código 2 si algún fichero no pudo procesarse. |
| `-q`, `--silencioso` | Suprime el resumen por consola. |

Códigos de salida: `0` correcto · `1` error de ejecución · `2` hubo incidencias
(solo con `--fallar-si-incidencias`). Un lote con incidencias no es un fallo de la
herramienta, así que por defecto devuelve 0; la bandera existe para que un
orquestador decida lo contrario.

### Tests

```bash
python3 -m pip install pytest && python3 -m pytest
```

162 tests. Los de integración se omiten si `dataset/inbox` no está presente.

---

## El dominio en una pantalla

Un **expediente** es una operación de importación o exportación, identificada por
su **MRN**: el código de 18 caracteres que la aduana asigna a la declaración. A lo
largo de su vida acumula hasta cinco tipos documentales:

| Tipo | Qué es | ¿Exigible? |
|---|---|---|
| `DUA` | Declaración de aduanas | **Obligatorio** |
| `FACTURA` | Base del valor en aduana | **Obligatorio** |
| `PACKING` | Packing list | **Obligatorio** |
| `TRANSPORTE` | CMR, B/L o AWB | Opcional |
| `CERTORIGEN` | Certificado de origen | Opcional |

Un expediente es **COMPLETO** cuando contiene al menos los tres obligatorios; el
transporte y el certificado de origen son deseables pero no condicionan el estado.
Es el criterio literal del enunciado, y vive en un único sitio del código
(`modelo.py:26-36`: `TIPOS_OBLIGATORIOS` y `TIPOS_OPCIONALES`), de modo que
cambiarlo es editar una tupla. El informe lista los documentos ausentes separando
ambos grupos, para que se distinga «falta el DUA» de «falta el certificado».

---

## Estructura

```
expedientes/
├── modelo.py          Tipos, motivos, Documento, Expediente
├── normalizacion.py   Alias de tipo, slug de cliente, fechas
├── validacion.py      Formato MRN, letra de control del NIF, distancia
├── lectura.py         Inbox -> Documento válido | Descarte motivado
├── clasificador.py    Agrupación por MRN, titular, versiones
├── escritura.py       Materialización idempotente del árbol de salida
├── informe.py         Informe en Markdown y JSON
└── cli.py             Interfaz de línea de comandos
```

El pipeline es una tubería de transformaciones puras con un único punto de
escritura al final (`leer_inbox -> clasificar -> escribir`), de modo que cada
regla de negocio se testea sin tocar el disco.

Salida generada:

```
salida/
├── archivo/<NIF>_<cliente-slug>/<MRN>/{DUA,FACTURA,PACKING,TRANSPORTE,CERTORIGEN}.txt
├── _descartes/<motivo>/<fichero> + <fichero>.motivo.json   (problema + decisión)
└── informes/{informe.md, informe.json}
```

---

## Resultado sobre el dataset

| Métrica | Valor |
|---|---|
| Ficheros leídos | 96 |
| Expedientes (clientes) | 20 (8) |
| Completos / Incompletos | 18 / 2 |
| Archivados / Descartados | 83 / 13 |
| Avisos no bloqueantes | 13 |

`83 + 13 = 96`: ningún fichero se pierde. Es un invariante verificado por test.

Descartes por motivo: `duplicado_exacto` 3 · `mrn_invalido` 3 ·
`artefacto_sistema` 2 · `version_superada` 2 · `conflicto_cliente` 1 ·
`fichero_vacio` 1 · `sin_estructura` 1.

Avisos por código: `ALIAS_TIPO` 6 · `NIF_CORREGIDO` 3 · `RECTIFICACION_APLICADA` 2
· `FECHA_INVALIDA` 1 · `TITULAR_POR_DUA` 1. Afectan a 12 de los 83 documentos
archivados; el decimotercero cuelga del expediente, no de un documento.

Los 2 expedientes incompletos son `26ESTZK6P9UDW63M0N` (sin DUA) y
`26ESZ73E9EAR21SU35` (sin FACTURA). Se comprobó que esos ficheros no están en el
inbox: la ausencia es del dataset, no del clasificador. El informe completo está en
[`salida/informes/informe.md`](salida/informes/informe.md).

---

## Decisiones de diseño

Todas siguen el mismo esquema: qué problema aparece en los datos, qué se hace, por
qué, y qué alternativa se descartó.

### D1 · El contenido es la fuente de verdad; el nombre es solo una pista

- **Problema.** El nombre de fichero codifica `TIPO_MRN_FECHA_NIF`, pero a veces
  contradice al contenido y a veces ni siquiera se puede parsear.
- **Decisión.** Todo dato del resultado sale de los campos `CLAVE: valor` del
  cuerpo del documento. El nombre se analiza (`analizar_nombre`), pero solo para
  **contrastar y avisar**: si diverge, prevalece el contenido y se emite
  `TIPO_DIVERGENTE`, `MRN_DIVERGENTE` o `FECHA_DIVERGENTE`.
- **Por qué.** El nombre es metadato manipulable —`_copia`, `(1)`, alias,
  minúsculas, un guion de más— mientras que el contenido tiene estructura estable.
  Un sistema que confíe en el nombre archiva mal en cuanto alguien renombra un
  fichero al descargarlo.
- **Alternativa descartada.** Tomar el nombre como fuente primaria y el contenido
  como respaldo: invierte exactamente la fiabilidad de las dos señales.
- **En el dataset.** Una sola divergencia real de valor:
  `CERTORIGEN_26ES13YWB77MXATXKP_...` declara dentro el MRN `26ESDX26CENWCZ1R5N`
  (y acaba en `conflicto_cliente`, D5). El resto son diferencias de *forma* que la
  normalización absorbe sin ruido: 6 alias de tipo, 2 nombres en minúsculas, 2
  fechas en `dd-mm-aaaa` y 5 sufijos de copia. Ningún dato del nombre entra en el
  resultado.

### D2 · Catálogo explícito de alias de tipo

- **Problema.** El mismo tipo lógico aparece con etiquetas distintas: `FRA`,
  `PLIST`, `PACKINGLIST`, `CMR`, `CERTIFICADO ORIGEN`.
- **Decisión.** Un diccionario cerrado (`ALIAS_TIPO`, `normalizacion.py:19`)
  traduce cada etiqueta —ya normalizada a mayúsculas, sin acentos ni separadores—
  a uno de los cinco tipos canónicos. Lo que no está en el catálogo se descarta
  con motivo `tipo_desconocido`.
- **Por qué.** Fallar ruidosamente ante un tipo nuevo obliga a que **una persona**
  decida si es legítimo, en vez de que el programa lo adivine por parecido y
  archive una factura como packing list. Dar de alta un alias es añadir una línea.
- **Alternativa descartada.** Emparejar por similitud (prefijo común, distancia de
  edición): clasifica con seguridad aparente y sin dejar rastro de la duda.
- **Alcance.** El catálogo cubre solo lo que aparece en el dataset, más `B/L` y
  `AWB`, que el enunciado nombra explícitamente como formas del documento de
  transporte. No se anticipan sinónimos hipotéticos.
- **Matiz.** El contenido manda sobre el nombre (D1), pero el tipo que declara el
  contenido tampoco es libre: tiene que estar en este catálogo. En este dataset los
  alias aparecen siempre en el **nombre** —los contenidos ya usan el nombre
  canónico—, y el catálogo se aplica a ambos porque `normalizar_tipo` es la única
  puerta de entrada al vocabulario de tipos.

### D3 · Un MRN mal formado nunca se autocorrige

- **Problema.** Tres ficheros llevan un MRN corrupto: uno de 17 caracteres, uno de
  19 y uno con un guion en medio.
- **Decisión.** Se valida contra el formato UE `\d{2}[A-Z]{2}[A-Z0-9]{14}`. Lo que
  no encaja va a `_descartes/mrn_invalido/`, acompañado —cuando existe— del **MRN
  válido más cercano** (distancia de edición ≤ 1 y candidato único) como sugerencia
  para el operador. Pero **no se fusiona**.
- **Por qué.** El MRN *es* la identidad del expediente. Un expediente visiblemente
  incompleto se ve y se arregla; uno silenciosamente contaminado con documentos de
  otra operación no se ve, y en aduanas eso tiene consecuencias fiscales.
- **Alternativa descartada.** Aplicar la corrección automáticamente cuando el
  candidato es único. Es cómodo y acierta casi siempre; ese «casi» es justo el
  problema, porque el fallo queda invisible.
- **Detalle.** No se codifica `26ES` a fuego: se valida la *forma*, no el país ni
  el ejercicio concretos.

### D4 · La letra de control del NIF desambigua sin heurísticas

- **Problema.** El dataset contiene 11 NIF distintos, pero tres pares difieren solo
  en la letra final: `20989659C`/`W`, `55464039E`/`R`, `75502037Y`/`D`. Tomados al
  pie de la letra darían 11 clientes.
- **Decisión.** Se comprueba el dígito de control (módulo 23, para DNI y NIE). En
  los tres pares una variante es válida y la otra no, así que la inválida se
  normaliza a la canónica con aviso `NIF_CORREGIDO`. Resultado: **8 clientes**.
- **Por qué.** No es una heurística ni un parecido: es una comprobación aritmética
  con una única respuesta correcta. Permite unificar identidades sin inventar
  política.
- **Alternativa descartada.** Agrupar por los 8 dígitos ignorando la letra: colapsa
  también los casos en que dos NIF legítimos comparten número, y renuncia a
  detectar el error.
- **Límite.** Un CIF (persona jurídica) usa otro algoritmo de control, así que se
  acepta tal cual con aviso `NIF_NO_VALIDABLE` en lugar de rechazarlo. No hay
  ningún CIF ni NIE en el dataset: ambas ramas existen para no romperse ante un
  identificador legítimo que este validador no cubre, y están cubiertas por test.

### D5 · El titular del expediente lo fija el DUA

- **Problema.** Dentro de un mismo MRN, los documentos declaran clientes distintos.
- **Decisión.** Manda el NIF del DUA, la declaración que la aduana asocia al MRN.
  Si no hay exactamente un DUA que arbitre, no se decide: los documentos en
  conflicto van a `_descartes/conflicto_cliente/`.
- **Por qué.** El DUA es la fuente de autoridad del dominio, no un criterio
  inventado. Y ante identidad contradictoria sin árbitro, **no clasificar** es más
  seguro que clasificar: mezclar clientes en un expediente aduanero tiene
  implicaciones fiscales y de confidencialidad.
- **Alternativa descartada.** Desempate por mayoría de documentos. Se implementó y
  luego se retiró: el dataset nunca la ejercita —el único conflicto,
  `26ESDX26CENWCZ1R5N`, lo resuelve el DUA— así que era política inventada, sin
  respaldo, que habría decidido sola el día que sí importara.

### D6 · Duplicados: identidad material, rectificación, o nada

- **Problema.** Varios ficheros compiten por el mismo hueco `(MRN, TIPO)`.
- **Decisión.** Tres casos, en este orden:
  1. **Mismo SHA-256** → son el mismo documento; se conserva uno de forma
     determinista y el resto va a `duplicado_exacto`.
  2. **Contenidos distintos y exactamente uno marcado `NOTA: RECTIFICACION`** →
     prevalece el rectificado; el anterior va a `version_superada` y sigue en disco
     como histórico.
  3. **Contenidos distintos sin marca** → no se elige ninguno
     (`conflicto_version`) y el tipo queda ausente en el expediente.
- **Por qué.** Cada caso tiene una respuesta objetiva distinta: identidad
  criptográfica, marca semántica del emisor, o ninguna evidencia. En el tercero, un
  hueco visible es mejor que un dato elegido al azar entre dos que se contradicen.
- **Alternativa descartada.** Desempatar por fecha del documento o de modificación
  del fichero. La fecha de sistema no dice nada sobre cuál es la versión buena, y
  la del documento suele coincidir en ambas versiones.
- **En el dataset.** 3 duplicados exactos y 2 rectificaciones. El caso 3 no se da:
  es la rama que evita elegir a ciegas si llegara a darse.

### D7 · Nada se pierde: todo descarte se materializa con su razón

- **Problema.** El enunciado pide *reportar* los ficheros no procesables.
- **Decisión.** Además de listarlos en el informe, cada uno se **copia** —nunca se
  mueve— a `_descartes/<motivo>/`, junto a un sidecar `<fichero>.motivo.json` con
  el problema detectado y la decisión adoptada.
- **Por qué.** Deja la razón pegada al fichero y hace el árbol navegable por
  motivo: quien tiene que arreglar los 3 MRN corruptos abre una carpeta en vez de
  filtrar un informe. Y el invariante `archivados + descartados = leídos` se vuelve
  comprobable mirando el disco.
- **Es un extra.** El enunciado solo exige el informe. Se mantiene porque el coste
  es bajo y hace el resultado auditable, pero no es un requisito.

### D8 · Incidencia bloqueante vs. aviso

- **Problema.** No toda anomalía impide procesar un fichero. Si se tratan todas
  igual, o se pierden documentos buenos o se ocultan problemas reales.
- **Decisión.** Dos categorías separadas y no intercambiables:
  - **Descarte** (`Motivo`, 10 valores): el fichero *no puede procesarse*. No entra
    en el archivo, se materializa en `_descartes/` y se lista como incidencia.
  - **Aviso** (`Aviso`, con severidad `INFO` o `ADVERTENCIA`): anomalía que **no
    impide clasificar**. El documento se archiva y la anomalía se anota.
- **Por qué.** Tratar todo como bloqueante costaría 12 de los 83 documentos
  archivados por cosas como que un fichero se llame `FRA_` en vez de `FACTURA_`, o
  que la letra del NIF esté mal: el sistema sería inútil. Ignorarlas escondería que
  un NIF se corrigió o que prevaleció una rectificación, que es justo lo que un
  operador necesita revisar.
- **Consecuencia.** El informe lleva dos tablas independientes, y el resumen cuenta
  `ficheros_descartados` y `avisos` por separado.

### D9 · Carpeta de cliente: `<NIF>_<slug-razón-social>`

- **Problema.** El enunciado propone `archivo/<cliente>/<MRN>/`, pero «cliente» no
  vale tal cual como nombre de carpeta. La razón social es texto libre: lleva
  comas, puntos, acentos y espacios, puede llegar escrita de dos formas distintas
  para la misma empresa, y en un caso patológico podría llevar una barra, que
  crearía un subdirectorio fantasma.
- **Decisión.** El nombre de carpeta es `<NIF>_<slug>`, p. ej.
  `20989659C_maderas-soria-sl`. **El NIF —ya canonizado por D4— es la clave; el
  slug solo aporta legibilidad.** Si se borrase el slug el sistema funcionaría
  igual; si se borrase el NIF, se rompería.

  El *slug* es la razón social reducida a caracteres seguros para una ruta, en tres
  pasos (`normalizacion.py:57`): quitar acentos por descomposición Unicode, pasar a
  minúsculas, y sustituir cualquier secuencia que no sea `a-z0-9` por un guion.

  | Razón social | Carpeta resultante |
  |---|---|
  | `Maderas Soria SL` | `20989659C_maderas-soria-sl` |
  | `Congelados Atlantico SA` | `44582623K_congelados-atlantico-sa` |
  | `Electro Import Iberia SL` | `50693756P_electro-import-iberia-sl` |

- **Por qué.** El slug garantiza que el nombre de carpeta sea **portable** (sin
  `/`, `:`, comas ni espacios que rompan en otro sistema operativo u obliguen a
  entrecomillar en la terminal) y **estable byte a byte**: `Atlántico` puede llegar
  con el acento en NFC o en NFD, dos secuencias distintas que en pantalla se ven
  iguales y que un `==` no considera iguales; tras `quitar_acentos` las dos dan lo
  mismo. También absorbe diferencias de mayúsculas y de espaciado.
- **Lo que el slug *no* resuelve, y por eso hay una segunda pieza.** El slug
  normaliza la forma, no la redacción: `Congelados Atlantico SA` y
  `Congelados Atlántico, S.A.` son la misma empresa y dan slugs **distintos**
  (`...-sa` frente a `...-s-a`), porque el punto se convierte en separador. Si se
  usara el slug como clave, ese cliente tendría dos carpetas y el árbol mentiría
  sobre cuántos clientes hay. Dos medidas lo evitan:
  1. **La clave es el NIF**, que no depende de cómo se escriba el nombre.
  2. Si un mismo NIF aparece con varias razones sociales, **se unifica el nombre
     antes de escribir** —la más frecuente, desempate alfabético— con aviso
     `RAZON_SOCIAL_UNIFICADA`, de modo que las dos variantes acaben en la misma
     carpeta.

  El nombre es presentación, y la presentación no debe partir un expediente en dos.
  En este dataset el aviso no se dispara: los 8 clientes tienen nombre consistente.
- **Alternativa descartada.** Carpeta solo con el slug: más legible, pero dos
  empresas con nombre parecido colisionan en la misma ruta y la clave deja de ser
  estable en cuanto alguien corrige una razón social.
- **Detalle defensivo.** `slug()` termina en `or "sin-nombre"`: si un documento
  trajera el campo `CLIENTE:` vacío o compuesto solo de símbolos, el slug quedaría
  en cadena vacía y la carpeta se llamaría `20989659C_`. Así queda
  `20989659C_sin-nombre`, que se ve raro a propósito.

### D10 · Idempotencia por reconstrucción total, con destino protegido

- **Problema.** El enunciado exige poder ejecutar varias veces sin producir
  resultados inconsistentes.
- **Decisión.** El árbol de salida se borra y se reconstruye entero en cada
  ejecución: misma entrada ⇒ mismo árbol byte a byte. Antes de borrar se comprueba,
  con rutas resueltas, que (a) entrada y destino no se solapan y (b) el destino es
  nuestro: inexistente, vacío, o con el centinela `.omnesia-salida`. Si no lo es,
  hace falta `--forzar`, que **no** desactiva la protección del inbox.
- **Por qué.** Reconstruir es trivialmente idempotente y no deja residuos de
  ejecuciones anteriores; una escritura incremental tendría que razonar sobre qué
  borrar, y ahí es donde aparecen las inconsistencias. El centinela es la
  contrapartida obligada: un `--salida ~/Documentos` no puede vaciarle el
  directorio a nadie por accidente.
- **Determinismo.** El único valor no determinista es el sello temporal del
  informe, inyectable para que los tests comparen byte a byte.

### D11 · Informe en Markdown y JSON

- **Decisión.** Se emiten los dos, generados de la misma estructura en memoria.
- **Por qué.** Tienen lectores distintos: el Markdown es para la persona que
  resuelve las incidencias, el JSON es el contrato para integrar aguas abajo.
  Generarlos del mismo origen garantiza que no puedan divergir.

### D12 · Python 3 con biblioteca estándar

- **Decisión.** Cero dependencias en ejecución (`argparse`, `pathlib`,
  `dataclasses`, `hashlib`, `json`, `re`, `unicodedata`, `shutil`, `enum`,
  `datetime`, `collections`). Única dependencia de desarrollo: **pytest**.
- **Por qué.** El enunciado pide justificar cualquier dependencia; la más fácil de
  justificar es la que no existe. `pytest` se usa por `parametrize` y la fixture
  `tmp_path`, y no hace falta para ejecutar la aplicación.

---

## Suposiciones

1. **Un expediente contiene como mucho un documento de cada tipo.** De ahí el
   nombre canónico `<TIPO>.txt` en el archivo y la resolución de versiones de D6.
2. **`NOTA: RECTIFICACION` es una marca semántica del emisor**, y una rectificación
   es siempre posterior a lo que rectifica.
3. **Si la letra del NIF no cuadra, el error está en la letra**, no en los dígitos
   (D4).
4. **La fecha del documento es informativa.** Una fecha imposible (`2026-02-30`) se
   avisa pero no impide clasificar, y los dos primeros dígitos del MRN no se
   interpretan como ejercicio ni se cruzan con ella. El dataset tiene un caso que
   ese cruce detectaría —`TRANSPORTE_26ES26FUALY9PLRV38`, fechado en 2027 con un
   MRN de 2026— y hoy pasa sin aviso: el enunciado no modela el ejercicio y D3 ya
   renuncia a interpretar el MRN por partes.
5. **El inbox es plano y de solo lectura**: los subdirectorios se ignoran y nunca
   se mueve ni renombra nada en origen (verificado por test).
6. **Los documentos son texto UTF-8** (con o sin BOM: se lee con `utf-8-sig`). En
   producción esta capa se sustituiría por extractores por formato sin tocar el
   resto del pipeline.

---

## Casos límite

La última columna distingue lo que el dataset ejercita de las ramas defensivas, que
existen para no romperse ante una entrada legítima pero no se disparan con estos
datos.

| Caso | Tratamiento | En el dataset |
|---|---|---|
| `.DS_Store`, `~$factura.tmp` | Descarte `artefacto_sistema` | 2 |
| Fichero de 0 bytes | Descarte `fichero_vacio` | 1 |
| Documento sin campos mínimos (`notas_reunion.txt`) | Descarte `sin_estructura` | 1 |
| MRN truncado, alargado o con carácter extra | Descarte `mrn_invalido` + candidato sugerido | 3 |
| Pares `_copia` con hash idéntico | Descarte `duplicado_exacto`, se conserva uno | 3 |
| Pares `(1)` con `RECTIFICACION` | Gana la rectificación; la previa a `version_superada` | 2 |
| CERTORIGEN con el MRN de otro cliente | Descarte `conflicto_cliente` (D5) | 1 |
| `FRA_`, `PLIST_`, `PACKINGLIST_`, `CMR_`, `CERTIFICADO ORIGEN_` | Aviso `ALIAS_TIPO`, se archiva con nombre canónico (D2) | 6 |
| `20989659W`, `55464039R`, `75502037D` | Normalizados a `C`/`E`/`Y`, aviso `NIF_CORREGIDO` (D4) | 3 |
| `FECHA: 2026-02-30` | Aviso `FECHA_INVALIDA`, se clasifica igual | 1 |
| Formatos `09-04-2026` vs `20260409`, nombres en minúsculas | Se normaliza sin ruido | 4 |
| Nombre y contenido con MRN distinto | Manda el contenido, aviso `MRN_DIVERGENTE` | 1 |
| Tipo documental fuera del catálogo | Descarte `tipo_desconocido` | — defensivo (D2) |
| Dos versiones distintas sin marca de rectificación | `conflicto_version`, el tipo queda ausente | — defensivo (D6) |
| Contenido no decodificable como UTF-8 | Descarte `no_decodificable` | — defensivo |
| CIF o NIE como identificador de cliente | Aviso `NIF_NO_VALIDABLE` / validación de NIE | — defensivo (D4) |
