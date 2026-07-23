# Clasificador de expedientes aduaneros

Aplicación de línea de comandos que procesa un directorio de documentos de
comercio internacional, los agrupa en **expedientes** (identificados por su MRN)
organizados **por cliente**, y emite un informe con el estado de cada expediente
y las incidencias detectadas.

Prueba técnica para Omnesia. Sin base de datos, sin interfaz gráfica y **sin
dependencias de terceros en tiempo de ejecución**.

---

## Ejecución

Requiere Python ≥ 3.10. No hay nada que instalar para ejecutarlo.

```bash
# Uso por defecto: lee dataset/inbox y escribe en salida/
python3 -m expedientes

# Explícito
python3 -m expedientes --inbox dataset/inbox --salida salida

# Ver el informe por terminal (el resumen sale por stderr, así que
# redirigir stdout produce un fichero limpio)
python3 -m expedientes --informe-stdout -q > informe.md

# Detenerse si algún fichero no ha podido procesarse (CI / orquestador)
python3 -m expedientes --fallar-si-incidencias

# Todas las opciones
python3 -m expedientes --help
```

| Opción | Efecto |
|---|---|
| `--inbox RUTA` | Directorio de entrada (por defecto `dataset/inbox`). Se trata como **solo lectura**. |
| `--salida RUTA` | Directorio de salida (por defecto `salida`). Se reconstruye en cada ejecución. |
| `--forzar` | Permite reconstruir un destino no vacío que no haya generado esta herramienta. |
| `--informe-stdout` | Vuelca además el informe Markdown por salida estándar. |
| `--fallar-si-incidencias` | Devuelve código 2 si algún fichero no pudo procesarse. |
| `-q`, `--silencioso` | Suprime el resumen por consola. |

Códigos de salida: `0` correcto · `1` error de ejecución · `2` hubo incidencias
(sólo con `--fallar-si-incidencias`). Se distinguen deliberadamente: un lote con
incidencias **no** es un fallo de la herramienta, así que por defecto devuelve 0;
la bandera existe para que un orquestador pueda decidir lo contrario. Un inbox
inexistente devuelve 1 aunque se pase la bandera.

### Tests

```bash
python3 -m pip install pytest
python3 -m pytest
```

**162 tests**, ~0,4 s. Los de integración se omiten automáticamente si
`dataset/inbox` no está presente.

---

## Estructura del proyecto

```
expedientes/
├── modelo.py          Vocabulario del dominio: tipos, motivos, Documento, Expediente
├── normalizacion.py   Alias de tipo, slug de cliente, formatos de fecha
├── validacion.py      Reglas duras: formato MRN, letra de control del NIF, distancia
├── lectura.py         Inbox -> Documento válido | Descarte motivado
├── clasificador.py    Agrupación por MRN, titular del expediente, versiones
├── escritura.py       Materialización idempotente del árbol de salida
├── informe.py         Informe en Markdown y JSON
└── cli.py             Interfaz de línea de comandos
tests/                 162 tests (unitarios + integración contra el dataset real)
```

El pipeline es una **tubería de transformaciones puras** con un único punto de
escritura al final:

```
leer_inbox  ->  clasificar  ->  escribir_salida + escribir_informes
(por fichero)   (por MRN)       (único efecto sobre el disco)
```

Todo lo que decide vive en funciones sin efectos secundarios, lo que permite
testear cada regla de negocio sin tocar el sistema de ficheros.

### Salida generada

```
salida/
├── archivo/
│   └── <NIF>_<cliente-slug>/
│       └── <MRN>/
│           ├── DUA.txt
│           ├── FACTURA.txt
│           ├── PACKING.txt
│           ├── TRANSPORTE.txt          (si existe)
│           └── CERTORIGEN.txt          (si existe)
├── _descartes/
│   └── <motivo>/                       una carpeta por motivo
│       ├── <fichero-original>
│       └── <fichero-original>.motivo.json    problema + decisión adoptada
└── informes/
    ├── informe.md
    └── informe.json
```

---

## Resultado sobre el dataset

| Métrica | Valor |
|---|---|
| Ficheros leídos | 96 |
| Expedientes identificados | 20 (8 clientes) |
| Completos / Incompletos | 18 / 2 |
| Documentos archivados | 83 |
| Ficheros descartados | 13 |
| Avisos no bloqueantes | 13 |

`83 + 13 = 96`: **ningún fichero se pierde por el camino**. Es un invariante
verificado por test.

Incidencias por motivo: `duplicado_exacto` 3 · `mrn_invalido` 3 ·
`artefacto_sistema` 2 · `version_superada` 2 · `conflicto_cliente` 1 ·
`fichero_vacio` 1 · `sin_estructura` 1.

El informe completo está en [`salida/informes/informe.md`](salida/informes/informe.md).

---

## Decisiones de diseño

### D1 · El contenido es la fuente de verdad; el nombre es sólo una pista

Cada fichero contiene los mismos campos que su nombre, y en 9 casos **no
coinciden**. Se toma siempre el contenido y se emite un aviso con la divergencia.

*Por qué:* el nombre es metadato manipulable por humanos y por herramientas
(`_copia`, `(1)`, alias, formatos de fecha distintos); el contenido es el
documento emitido. Además el nombre puede ser directamente inparseable
(`notas_reunion.txt`), mientras que el contenido tiene una estructura estable.

*Alternativa descartada:* exigir que ambos coincidan y descartar si no. Habría
mandado a incidencias 9 documentos perfectamente válidos.

**Ningún dato del nombre entra en el resultado.** Sólo sirve para generar avisos.

### D2 · Catálogo de alias de tipo documental

`FRA` → FACTURA, `PLIST`/`PACKINGLIST` → PACKING, `CMR`/`B/L`/`AWB` →
TRANSPORTE, `CERTIFICADO ORIGEN` → CERTORIGEN, etc. La comparación se hace tras
normalizar (mayúsculas, sin acentos, sin separadores), de modo que
`certificado de origen`, `CERTIFICADO_ORIGEN` y `CertificadoOrigen` colapsan en
la misma entrada.

*Por qué un catálogo explícito y no heurística:* un tipo desconocido debe fallar
de forma ruidosa (`tipo_desconocido`) para que alguien decida si es un tipo
legítimo que hay que dar de alta, no clasificarse "por parecido".

*Alcance del catálogo:* sólo contiene los alias que aparecen en el dataset más
`B/L` y `AWB`, que el enunciado nombra explícitamente como formas del documento
de transporte. No se anticipan sinónimos hipotéticos (`INVOICE`, `SAD`, `EUR1`…):
darlos de alta es añadir una línea el día que aparezcan, y hasta entonces sólo
serían código no ejercitado que aparenta cobertura.

### D3 · Un MRN mal formado nunca se autocorrige

El MRN se valida contra el formato general de la UE: `\d{2}[A-Z]{2}[A-Z0-9]{14}`
(18 caracteres). Tres ficheros no lo cumplen. Van a
`_descartes/mrn_invalido/` **con el MRN válido más cercano sugerido en el
informe**, pero no se fusionan.

*Por qué:* el MRN es la clave de identidad que asigna la aduana. Una fusión
errónea mete un documento en el expediente de otra operación de forma
silenciosa, y ese error no vuelve a detectarse. Prefiero un expediente
visiblemente incompleto que uno silenciosamente contaminado. La sugerencia
(distancia de Levenshtein ≤ 1, y sólo si el candidato es único) le ahorra el
trabajo al operador sin tomar la decisión por él.

*Nota:* no se codifica `26ES` a fuego. El lote es de 2026/España, pero el
clasificador debe seguir sirviendo en 2027 y con otros países.

### D4 · La letra de control del NIF desambigua sin heurísticas

Tres clientes aparecen con dos NIF distintos que difieren sólo en la letra:
`20989659C/W`, `55464039E/R`, `75502037Y/D`. Se valida la letra de control
(módulo 23 sobre la parte numérica). En los tres casos **una variante es válida y
la otra no**, así que el NIF se normaliza a su forma canónica y se emite un aviso
`NIF_CORREGIDO`.

*Por qué:* la letra del NIF es un dígito verificador, no un dato opinable. Esto
convierte lo que parecía requerir una heurística ("el mayoritario", "el primero")
en una regla objetiva y verificable. Sin esta normalización aparecerían 11
clientes en lugar de 8, con expedientes partidos por la mitad.

*Suposición explícita:* si la letra no cuadra, se asume que el error está en la
letra y no en los 8 dígitos. Es lo más probable en una transcripción, y en
cualquier caso queda registrado en el informe.

*Alcance:* se validan DNI y NIE. Un CIF (persona jurídica) se acepta tal cual con
un aviso informativo, sin corregirse: su dígito de control sigue otro algoritmo.

### D5 · El titular del expediente lo fija el DUA, y si no hay DUA no se decide

Cuando los documentos de un mismo MRN declaran clientes distintos:

1. **Manda el NIF del DUA.** Es la declaración que la aduana asocia al MRN, luego
   es la fuente autorizada sobre a quién pertenece la operación.
2. **Si no hay un único DUA que arbitre, no se decide**: el expediente entero va a
   `_descartes/conflicto_cliente/`.

Los documentos que no coinciden con el titular van a esa misma cuarentena.

*Por qué:* mezclar documentos de dos clientes en un expediente aduanero es peor
que dejar un expediente incompleto — tiene implicaciones de confidencialidad y de
responsabilidad fiscal. Ante identidad contradictoria, se prefiere no clasificar.

*Por qué no hay desempate por mayoría:* fue la primera versión de esta regla y
**la eliminé tras auditar qué ramas ejercita realmente el dataset**. El único
expediente con NIF en conflicto (`26ESDX26CENWCZ1R5N`) se resuelve por DUA, así
que la rama de mayoría nunca se ejecutaba: era una política inventada para un
caso que el problema no plantea, y su único efecto real habría sido elegir un
titular equivocado con aparente seguridad. Prefiero que el sistema no responda a
que responda mal.

*En el dataset:* `CERTORIGEN_26ES13YWB77MXATXKP_...` declara internamente el MRN
`26ESDX26CENWCZ1R5N`, cuyo DUA pertenece a Electro Import Iberia, pero se
identifica como Químicas Ebro. Se aparta y se reporta.

*Limitación conocida y no resuelta a propósito:* si un expediente tuviera el DUA
de un cliente y todos los demás documentos de otro, esta regla archivaría sólo el
DUA y mandaría el resto a cuarentena. No hay ningún caso así en el dataset, y
cualquier regla que lo "arreglara" sería especulación: en ese escenario el
expediente queda incompleto se elija lo que se elija, y lo correcto es que un
humano lo mire.

### D6 · Duplicados: identidad material, rectificación, o nada

Ante varios documentos del mismo `(MRN, TIPO)`:

- **Mismo SHA-256** → duplicado material. Se conserva uno y el resto va a
  `duplicado_exacto`. Cuál se conserva es determinista (orden estable), no
  arbitrario según el orden del sistema de ficheros.
- **Contenidos distintos y exactamente uno marcado `NOTA: RECTIFICACION`** →
  prevalece el rectificado; el anterior va a `version_superada`.
- **Contenidos distintos sin marca que arbitre** → **no se elige ninguno**. El
  tipo queda como ausente en el expediente y todas las versiones van a
  `conflicto_version`.

*Por qué el tercer caso:* un dato elegido al azar entre dos que se contradicen es
peor que un hueco visible. El hueco se ve en el informe y alguien lo arregla; el
dato equivocado no.

### D7 · Nada se pierde: todo descarte se materializa con su razón

Cada fichero descartado se **copia** a `_descartes/<motivo>/` junto a un sidecar
`<fichero>.motivo.json` con el problema detectado y la decisión adoptada.

*Alcance:* el enunciado sólo pide **reportar** los ficheros no procesables.
Archivarlos además en disco es un requisito añadido por el cliente de este
desarrollo, no una iniciativa propia; queda anotado para que no se confunda con
las decisiones técnicas del resto del documento.

*Por qué:* la razón del descarte tiene que estar disponible donde está el
fichero, no sólo en un informe global que puede perderse o quedar desfasado.
Además el árbol de descartes es navegable: el nombre de la carpeta ya dice el
motivo.

### D8 · Incidencia bloqueante vs. aviso informativo

Se distinguen dos niveles:

- **Descarte**: el fichero no entra en el archivo (10 motivos posibles).
- **Aviso**: anomalía detectada que **no** impide clasificar — NIF corregido,
  alias de tipo, fecha inválida, divergencia nombre/contenido, fecha fuera del
  ejercicio del MRN.

*Por qué:* tratar toda anomalía como bloqueante haría inútil el sistema (14 de
83 documentos archivados llevan algún aviso). Tratarlas todas como ignorables
ocultaría problemas reales. El informe separa ambas listas.

### D9 · Carpeta de cliente: `<NIF>_<slug-razón-social>`

Ejemplo: `20989659C_maderas-soria-sl`.

*Por qué:* el NIF (ya canonizado por D4) es el identificador único y estable; el
slug sólo aporta legibilidad al navegar el árbol. Usar sólo el nombre comercial
sería frágil — no es único ni estable, y un cambio de razón social partiría el
archivo en dos.

*Consecuencia:* como la carpeta combina ambos, un mismo NIF escrito con dos
razones sociales (`Maderas Soria SL` y `MADERAS SORIA, S.L.`) generaría dos
directorios para un solo cliente, contradiciendo que el NIF es la clave. Por eso
se unifica el nombre por NIF antes de escribir: gana el más frecuente, medido en
documentos, con desempate alfabético para que sea reproducible. La regla afecta
sólo a **cómo se presenta** el cliente; la identidad la sigue fijando el NIF, y
el cambio se deja anotado como aviso `RAZON_SOCIAL_UNIFICADA`.

### D10 · Idempotencia por reconstrucción total, con destino protegido

El árbol de salida se **borra y se reconstruye entero** en cada ejecución. Misma
entrada ⇒ mismo árbol byte a byte, sin restos ni acumulación.

*Por qué no sincronización incremental:* exigiría detectar borrados y
reconciliar estados, y no aporta nada cuando el coste de rehacerlo es
milisegundos.

*Protección, en dos capas:* reconstruir un directorio equivocado destruye datos,
así que antes de borrar nada se comprueba que:

1. **La entrada y el destino no se solapan.** Si el inbox cuelga del destino, la
   herramienta borraría su propia entrada; si el destino cuelga del inbox,
   escribir ahí modificaría un directorio que es de sólo lectura. Ambos casos se
   rechazan, comparando rutas ya resueltas para que `inbox/../inbox` no se cuele.
   Como red adicional, `escribir_salida` verifica que ningún fichero de origen
   viva bajo el destino, de modo que la protección también aplica al uso
   programático de la librería, no sólo al CLI.
2. **El destino es nuestro.** Sólo se reconstruye si es inexistente, está vacío o
   lleva el centinela `.omnesia-salida`. En otro caso se aborta y hay que pasar
   `--forzar`. Nótese que `--forzar` **no** desactiva la comprobación 1: no hay
   forma de que la herramienta borre el inbox.

El determinismo se consigue ordenando explícitamente en todas partes (recorrido
del inbox, expedientes, tipos, desempates entre documentos equivalentes). El
único valor no determinista es el sello temporal del informe, que es inyectable
para que los tests comparen byte a byte.

### D11 · Informe en Markdown y JSON

El Markdown es para la persona que tiene que resolver las incidencias; el JSON
es el contrato para integrar el clasificador aguas abajo (Omnesia es una
plataforma orientada a eventos, y este proceso es un productor natural). Ambos
se generan de la misma estructura, así que no pueden divergir.

### D12 · Python 3 con la biblioteca estándar

Cero dependencias en tiempo de ejecución: `argparse`, `pathlib`, `dataclasses`,
`hashlib`, `json`, `re`, `unicodedata`, `shutil` cubren todo el problema.

Única dependencia de desarrollo: **pytest**, justificada por `parametrize` (las
tablas de casos límite de este problema se expresan de forma mucho más legible)
y por las fixtures de `tmp_path`. No es necesaria para ejecutar la aplicación.

---

## Suposiciones realizadas

1. **Un expediente contiene como mucho un documento de cada tipo.** Por eso el
   nombre canónico dentro del expediente es `<TIPO>.txt` y varias versiones del
   mismo tipo se resuelven a una (D6). Si el negocio admitiera varias facturas
   por expediente, cambiaría la clave de agrupación a `(MRN, TIPO, nº documento)`.
2. **`NOTA: RECTIFICACION` es una marca semántica del emisor**, no texto
   decorativo, y una rectificación siempre es posterior a lo que rectifica.
3. **Si la letra del NIF no cuadra, el error está en la letra** y no en los
   dígitos (D4).
4. **Los dos primeros dígitos del MRN son el ejercicio de la declaración.** Se
   usa sólo para emitir un aviso cuando la fecha del documento cae en otro año,
   nunca para descartar.
5. **La fecha del documento es informativa.** Una fecha imposible (`2026-02-30`)
   no impide clasificar: no forma parte de la identidad del expediente.
6. **El inbox es plano.** Los subdirectorios se ignoran; el enunciado describe un
   inbox de ficheros.
7. **Los documentos son texto UTF-8** (con o sin BOM: se decodifica con
   `utf-8-sig`, porque las herramientas de Windows lo anteponen y sin ello la
   primera clave del fichero se leería corrupta). El dataset usa `.txt`; en producción la
   capa de lectura se sustituiría por extractores por formato (PDF, XML) sin
   tocar el resto del pipeline.
8. **El inbox es de sólo lectura.** Nunca se mueve ni se renombra nada en origen:
   siempre se copia. Verificado por test.

---

## Casos límite detectados y tratamiento

| Caso en el dataset | Detección | Tratamiento |
|---|---|---|
| Documento sin `NIF-CLIENTE` | Campos mínimos | Descarte `sin_estructura`: sin cliente no se puede archivar por cliente |
| Fichero con BOM UTF-8 | `utf-8-sig` | Se lee con normalidad |
| `.DS_Store`, `~$factura.tmp` | Patrón de artefacto del SO/ofimática | Descarte `artefacto_sistema`, sin intentar interpretar |
| `vacio.txt` (0 bytes) | Contenido vacío o sólo espacios | Descarte `fichero_vacio` |
| `notas_reunion.txt` | Sin campos `TIPO` ni `MRN` | Descarte `sin_estructura` |
| Contenido no UTF-8 | `UnicodeDecodeError` | Descarte `no_decodificable` |
| `FRA_`, `PLIST_`, `PACKINGLIST_`, `CMR_`, `CERTIFICADO ORIGEN_` | Catálogo de alias (D2) | Se clasifican con aviso `ALIAS_TIPO` |
| 3 pares `_copia` con hash idéntico | SHA-256 | Descarte `duplicado_exacto`, se conserva uno |
| 2 pares `(1)` con `RECTIFICACION` | Marca en el contenido | Gana la rectificación; la previa a `version_superada` |
| `26ESA70XSGJHX8HA9W`**Z**, `26ESDX26CENWCZ1R5` (truncado), `26ESHGDB`**-**`XVL72JJAP` | Formato MRN | Descarte `mrn_invalido` + candidato sugerido |
| `20989659W`, `55464039R`, `75502037D` | Letra de control | Normalizados a `C`/`E`/`Y` con aviso |
| CERTORIGEN con MRN de otro cliente | Titular por DUA (D5) | Descarte `conflicto_cliente` |
| `FECHA: 2026-02-30` | Fecha inexistente | Aviso `FECHA_INVALIDA`, se clasifica igual |
| Fechas `09-04-2026` vs `20260409` | Múltiples formatos aceptados | Se normalizan; divergencia → aviso |
| Nombre dice un MRN y el contenido otro | Cruce nombre/contenido | Manda el contenido, aviso `MRN_DIVERGENTE` |

### Sobre el código que el dataset no ejercita

Se auditó qué ramas dispara realmente `dataset/inbox` y se eliminó lo que era
política inventada (ver D5 y D2). Lo que queda sin ejercitar es deliberado y de
otra naturaleza — son **ramas `else` obligatorias, no funcionalidad especulativa**:

| Rama | Por qué se queda |
|---|---|
| `no_decodificable` | Es el `except UnicodeDecodeError` de `.decode()`. Sin él, un fichero binario **rompe la ejecución**. El dataset tiene uno (`.DS_Store`), sólo que lo intercepta antes el filtro de artefactos; si mañana llega como `factura.txt`, esta rama es lo único que evita el fallo. |
| `tipo_desconocido` | Es el caso en que `normalizar_tipo` devuelve `None`. Sin tratarlo, el `None` se propaga al resto del pipeline. |
| `conflicto_version` | Es el `else` de "hay varias versiones y exactamente una es rectificación", condición que sí se ejercita. Hay que hacer *algo* cuando no se cumple. |
| `TITULAR_INDETERMINADO` | Es el `else` de "hay un único DUA que arbitre". Negarse a decidir es una línea, no una heurística. |
| Validación de NIE y CIF | `validar_nif` tiene que responder algo ante un identificador que no es un DNI. La alternativa sería corregir un CIF con el algoritmo equivocado. |

Todas están cubiertas por tests, precisamente porque nunca las ejercita el
dataset: si se rompen, no habría forma de enterarse en producción.

---

## Cobertura de tests

| Fichero | Qué fija |
|---|---|
| `test_validacion.py` | Formato MRN, letra de control DNI/NIE/CIF, sugerencia por distancia |
| `test_normalizacion.py` | Alias de tipo, slug de cliente, formatos de fecha |
| `test_lectura.py` | Descartes por motivo, precedencia del contenido, avisos |
| `test_clasificador.py` | Completitud, duplicados, rectificaciones, titular, recuento |
| `test_escritura.py` | Layout, sidecars, idempotencia, protección del destino, inbox intacto |
| `test_informe.py` | Contenido del informe y determinismo |
| `test_integracion.py` | Cifras exactas sobre el dataset real, casos concretos y códigos de salida |

Los tests unitarios construyen su propio inbox en `tmp_path`, de modo que la
suite no depende del dataset y sigue siendo válida si éste cambia.

---

## Limitaciones y trabajo futuro

- **Un solo tipo por expediente** (suposición 1). Levantarlo implica cambiar la
  clave de agrupación y el nombrado dentro del expediente.
- **Todo en memoria.** Con 96 ficheros es irrelevante; para millones habría que
  procesar en flujo y volcar el informe incrementalmente. La estructura del
  pipeline ya lo permitiría: la lectura es fichero a fichero.
- **La sugerencia de MRN usa distancia de edición ≤ 1.** No cubre errores de
  transposición dobles ni MRN con dos caracteres corruptos.
- **No hay validación cruzada de contenido de negocio** (que BULTOS y PESO-KG
  concuerden entre el PACKING y la FACTURA del mismo expediente). Es la
  extensión natural: convertiría el clasificador en un validador de coherencia
  documental.
- **Los estados regulatorios** (admitida, circulando, ultimada) y los regímenes
  aduaneros no se modelan; el dataset no los expone y el enunciado los declara
  fuera de alcance.
