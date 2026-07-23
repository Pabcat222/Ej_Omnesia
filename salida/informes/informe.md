# Informe de clasificacion documental

Generado: 2026-07-21T10:10:10+00:00

## Resumen

- Ficheros leidos del inbox: **96**
- Expedientes identificados: **20** (8 clientes)
- Completos: **18** / Incompletos: **2**
- Documentos archivados: **83**
- Ficheros descartados: **13**
- Avisos no bloqueantes: **13**

Un expediente es **COMPLETO** cuando contiene DUA, FACTURA y PACKING.
TRANSPORTE y CERTORIGEN son opcionales y no alteran el estado.

## Expedientes

| Cliente | NIF | MRN | Estado | Documentos encontrados | Obligatorios ausentes | Opcionales ausentes |
|---|---|---|---|---|---|---|
| Aceites del Sur SL | 12898185S | `26ES0ZW5Y7YWB6HHBX` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Aceites del Sur SL | 12898185S | `26ES1XMXPFFDZN97KD` | COMPLETO | DUA, FACTURA, PACKING, TRANSPORTE | - | CERTORIGEN |
| Congelados Atlantico SA | 44582623K | `26ESHGDBTXVL72JJAP` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING | - | TRANSPORTE |
| Congelados Atlantico SA | 44582623K | `26ESWVVCU6XUX2LFAK` | COMPLETO | DUA, FACTURA, PACKING, TRANSPORTE | - | CERTORIGEN |
| Congelados Atlantico SA | 44582623K | `26ESZ73E9EAR21SU35` | INCOMPLETO | DUA, PACKING, TRANSPORTE | FACTURA | CERTORIGEN |
| Electro Import Iberia SL | 50693756P | `26ES57ED9UXZPP5XAB` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING | - | TRANSPORTE |
| Electro Import Iberia SL | 50693756P | `26ESDX26CENWCZ1R5N` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING | - | TRANSPORTE |
| Frutas Levante SL | 46490500W | `26ES1EX0NT21NTKJCJ` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING | - | TRANSPORTE |
| Frutas Levante SL | 46490500W | `26ESSD385Y6CJ6F92R` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Frutas Levante SL | 46490500W | `26ESY3834NB29S6VN4` | COMPLETO | DUA, FACTURA, PACKING | - | TRANSPORTE, CERTORIGEN |
| Maderas Soria SL | 20989659C | `26ESA70XSGJHX8HA9W` | COMPLETO | DUA, FACTURA, PACKING, TRANSPORTE | - | CERTORIGEN |
| Maderas Soria SL | 20989659C | `26ESSK12FXU518CW6M` | COMPLETO | DUA, FACTURA, PACKING, TRANSPORTE | - | CERTORIGEN |
| Quimicas Ebro SL | 75502037Y | `26ES13YWB77MXATXKP` | COMPLETO | DUA, FACTURA, PACKING, TRANSPORTE | - | CERTORIGEN |
| Quimicas Ebro SL | 75502037Y | `26ESTZK6P9UDW63M0N` | INCOMPLETO | FACTURA, PACKING | DUA | TRANSPORTE, CERTORIGEN |
| Quimicas Ebro SL | 75502037Y | `26ESX3909YK5ZXEVMW` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Textil Manresa SA | 66061562L | `26ES5G587C1R2WG98T` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Textil Manresa SA | 66061562L | `26ESEBBLM0LPAL207U` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Textil Manresa SA | 66061562L | `26ESMZCVNHP1ZW2PWD` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING | - | TRANSPORTE |
| Vinos Rioja Export SA | 55464039E | `26ES26FUALY9PLRV38` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |
| Vinos Rioja Export SA | 55464039E | `26ES6YUREB0VGFKKS9` | COMPLETO | CERTORIGEN, DUA, FACTURA, PACKING, TRANSPORTE | - | - |

## Incidencias

Ficheros que no han podido incorporarse al archivo. Cada uno se conserva en `_descartes/<motivo>/` junto a un sidecar `.motivo.json` con este mismo detalle.

| Motivo | Nº |
|---|---|
| artefacto_sistema | 2 |
| conflicto_cliente | 1 |
| duplicado_exacto | 3 |
| fichero_vacio | 1 |
| mrn_invalido | 3 |
| sin_estructura | 1 |
| version_superada | 2 |

| Fichero | Problema detectado | Decision adoptada |
|---|---|---|
| `.DS_Store` | Artefacto del sistema de ficheros o temporal de ofimatica. | No se intenta interpretar; se aparta sin analizar. |
| `~$factura.tmp` | Artefacto del sistema de ficheros o temporal de ofimatica. | No se intenta interpretar; se aparta sin analizar. |
| `CERTORIGEN_26ES13YWB77MXATXKP_20260615_75502037Y.txt` | Declara el MRN 26ESDX26CENWCZ1R5N, cuyo titular es 50693756P (Electro Import Iberia SL), pero identifica como cliente a 75502037Y (Quimicas Ebro SL). | No se incorpora al expediente: mezclar documentos de dos clientes es un fallo mas grave que un expediente incompleto. |
| `FACTURA_26ESY3834NB29S6VN4_20260530_46490500W_copia.txt` | Contenido byte a byte identico a FACTURA_26ESY3834NB29S6VN4_20260530_46490500W.txt (sha256 047ad41f2eed...). | Se conserva FACTURA_26ESY3834NB29S6VN4_20260530_46490500W.txt y se aparta esta copia. |
| `PACKING_26ESA70XSGJHX8HA9W_20260131_20989659C_copia.txt` | Contenido byte a byte identico a PACKING_26ESA70XSGJHX8HA9W_20260131_20989659C.txt (sha256 9a850c41d028...). | Se conserva PACKING_26ESA70XSGJHX8HA9W_20260131_20989659C.txt y se aparta esta copia. |
| `PACKING_26ESDX26CENWCZ1R5N_20260507_50693756P_copia.txt` | Contenido byte a byte identico a PACKING_26ESDX26CENWCZ1R5N_20260507_50693756P.txt (sha256 e0531f86f23f...). | Se conserva PACKING_26ESDX26CENWCZ1R5N_20260507_50693756P.txt y se aparta esta copia. |
| `vacio.txt` | El fichero no tiene contenido (0 bytes). | Se aparta: no hay nada que clasificar. |
| `CERTORIGEN_26ESA70XSGJHX8HA9WZ_20260131_20989659C.txt` | El MRN '26ESA70XSGJHX8HA9WZ' (19 caracteres) no cumple el formato de 18 caracteres AAPP + 14 alfanumericos. | Se aparta sin reasignar: el MRN identifica el expediente y una fusion erronea contaminaria un expediente ajeno. Candidato mas proximo para revision manual: 26ESA70XSGJHX8HA9W. |
| `TRANSPORTE_26ESDX26CENWCZ1R5_20260507_50693756P.txt` | El MRN '26ESDX26CENWCZ1R5' (17 caracteres) no cumple el formato de 18 caracteres AAPP + 14 alfanumericos. | Se aparta sin reasignar: el MRN identifica el expediente y una fusion erronea contaminaria un expediente ajeno. Candidato mas proximo para revision manual: 26ESDX26CENWCZ1R5N. |
| `TRANSPORTE_26ESHGDB-XVL72JJAP_20260412_44582623K.txt` | El MRN '26ESHGDB-XVL72JJAP' (18 caracteres) no cumple el formato de 18 caracteres AAPP + 14 alfanumericos. | Se aparta sin reasignar: el MRN identifica el expediente y una fusion erronea contaminaria un expediente ajeno. Candidato mas proximo para revision manual: 26ESHGDBTXVL72JJAP. |
| `notas_reunion.txt` | El contenido no expone los campos minimos TIPO, MRN, NIF-CLIENTE (claves encontradas: ninguna). | Se aparta: no es un documento del expediente clasificable. |
| `DUA_26ES1XMXPFFDZN97KD_20260521_12898185S.txt` | Existe una version posterior del mismo DUA marcada como rectificacion: DUA_26ES1XMXPFFDZN97KD_20260521_12898185S (1).txt. | Se archiva la version rectificada y esta se conserva en descartes como historico. |
| `FACTURA_26ESSD385Y6CJ6F92R_20260123_46490500W.txt` | Existe una version posterior del mismo FACTURA marcada como rectificacion: FACTURA_26ESSD385Y6CJ6F92R_20260123_46490500W (1).txt. | Se archiva la version rectificada y esta se conserva en descartes como historico. |

## Avisos

Anomalias detectadas que **no** han impedido clasificar el documento.

| MRN | Fichero | Codigo | Detalle |
|---|---|---|---|
| `26ES13YWB77MXATXKP` | `FACTURA_26ES13YWB77MXATXKP_20260615_75502037D.txt` | NIF_CORREGIDO | El NIF 75502037D tiene letra de control incorrecta; se normaliza a 75502037Y. |
| `26ES13YWB77MXATXKP` | `PACKINGLIST_26ES13YWB77MXATXKP_20260615_75502037Y.txt` | ALIAS_TIPO | El nombre usa el alias 'PACKINGLIST' para PACKING. |
| `26ES1XMXPFFDZN97KD` | `DUA_26ES1XMXPFFDZN97KD_20260521_12898185S (1).txt` | RECTIFICACION_APLICADA | Sustituye a DUA_26ES1XMXPFFDZN97KD_20260521_12898185S.txt. |
| `26ES1XMXPFFDZN97KD` | `FRA_26ES1XMXPFFDZN97KD_20260521_12898185S.txt` | ALIAS_TIPO | El nombre usa el alias 'FRA' para FACTURA. |
| `26ES1XMXPFFDZN97KD` | `TRANSPORTE_26ES1XMXPFFDZN97KD_20260230_12898185S.txt` | FECHA_INVALIDA | La fecha '2026-02-30' no corresponde a un dia real; el documento se clasifica igualmente. |
| `26ES5G587C1R2WG98T` | `PLIST_26ES5G587C1R2WG98T_20260110_66061562L.txt` | ALIAS_TIPO | El nombre usa el alias 'PLIST' para PACKING. |
| `26ES6YUREB0VGFKKS9` | `DUA_26ES6YUREB0VGFKKS9_20260605_55464039R.txt` | NIF_CORREGIDO | El NIF 55464039R tiene letra de control incorrecta; se normaliza a 55464039E. |
| `26ESA70XSGJHX8HA9W` | `DUA_26ESA70XSGJHX8HA9W_20260131_20989659W.txt` | NIF_CORREGIDO | El NIF 20989659W tiene letra de control incorrecta; se normaliza a 20989659C. |
| `26ESDX26CENWCZ1R5N` | (expediente) | TITULAR_POR_DUA | Documentos con 2 NIF distintos; el titular se fija por el DUA (50693756P). |
| `26ESHGDBTXVL72JJAP` | `CERTIFICADO ORIGEN_26ESHGDBTXVL72JJAP_20260412_44582623K.txt` | ALIAS_TIPO | El nombre usa el alias 'CERTIFICADO ORIGEN' para CERTORIGEN. |
| `26ESSD385Y6CJ6F92R` | `FACTURA_26ESSD385Y6CJ6F92R_20260123_46490500W (1).txt` | RECTIFICACION_APLICADA | Sustituye a FACTURA_26ESSD385Y6CJ6F92R_20260123_46490500W.txt. |
| `26ESX3909YK5ZXEVMW` | `FRA_26ESX3909YK5ZXEVMW_20260208_75502037Y.txt` | ALIAS_TIPO | El nombre usa el alias 'FRA' para FACTURA. |
| `26ESZ73E9EAR21SU35` | `CMR_26ESZ73E9EAR21SU35_20260416_44582623K.txt` | ALIAS_TIPO | El nombre usa el alias 'CMR' para TRANSPORTE. |
