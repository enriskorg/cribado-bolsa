# Buscador de aulas de la Universidad Pablo de Olavide

Aplicación web de un solo archivo para consultar las capacidades y el equipamiento de las aulas y otros espacios docentes de la Universidad Pablo de Olavide (Sevilla). Permite ver la ficha de un aula concreta o buscar espacios que cumplan ciertos criterios: edificio, capacidad normal, capacidad en examen, si la pantalla del proyector bloquea la pizarra, tipo de pizarra y mobiliario.

**Herramienta no oficial.** No está desarrollada ni mantenida por la Universidad Pablo de Olavide. La fuente de verdad sigue siendo la documentación de la Unidad de Gestión de Espacios.

## Uso

Abre `index.html` en cualquier navegador. No requiere servidor, instalación ni conexión a internet (la tipografía se carga de Google Fonts si hay red, y si no, se usa la del sistema).

- **Consultar un aula**: elige edificio y aula en los desplegables. La ficha muestra capacidades, puesto adaptado, mobiliario, equipamiento audiovisual, oscurecimiento, pizarra, puertas y observaciones.
- **Buscar aulas por características**: combina filtros y ordena la tabla pulsando las cabeceras. Al pulsar una fila se abre su ficha. El filtro "Solo espacios docentes" (activo por defecto) excluye salas de juntas, de visitas, de grados, videoconferencia y laboratorios marcados como no docentes.

## Fuente de los datos

Los datos proceden del documento público *Espacios: capacidad y equipamientos (2026, actualizado a 18-09-2026)* disponible en la web de la Unidad de Gestión de Espacios de la UPO: <https://www.upo.es/campus/gestion-de-espacios/>

Se han transcrito manualmente desde el PDF a la estructura de datos de la aplicación. Cubre 17 edificios y 250 espacios. Los criterios de la hoja original se conservan:

- Las capacidades no incluyen la posición del docente ni los puestos adaptados.
- "Puesto adaptado" son posiciones sin silla, solo pupitre.
- El recuento de PC incluye el del docente.
- Los enchufes disponibles excluyen los ocupados por el equipamiento del aula.

## Avisos sobre la calidad de los datos

La hoja original tiene celdas vacías e inconsistencias que se han respetado en lugar de corregir por conjetura:

- Muchos espacios del **E23**, los sótanos del **E24** y varias salas singulares (juntas, grados, Rectorado) tienen la mayoría de campos sin rellenar. Se muestran como "No consta", que no equivale a "No": un espacio sin dato de bloqueo de pizarra no aparecerá al filtrar por "No bloquea".
- En filas con muchos huecos la alineación de columnas del PDF es ambigua y se ha interpretado por contexto. Para las aulas de docencia ordinaria el dato es fiable; para salas singulares conviene contrastarlo.

Si detectas un error, abre un *issue* o envía un *pull request* (ver más abajo).

## Cómo corregir o actualizar datos

Todo está en `index.html`. Los datos están al principio del bloque `<script>`, en el objeto `RAW`, con una línea por espacio y los campos separados por `|` en este orden:

```
aula | planta | cap. normal | cap. examen | puestos adaptados | fila del puesto adaptado |
posición del puesto adaptado | mobiliario | PC | cañón | megafonía | enchufes | tarima |
oscurecimiento | pizarra: posición | pizarra: tipo | cámara | ¿bloquea la pizarra? |
pantalla: posición | monitores | tipo de puertas | observaciones
```

Cada línea debe tener exactamente 22 campos (21 barras). Los campos sin dato se dejan vacíos. Los valores esperados en los campos filtrables son:

- `¿bloquea la pizarra?`: `Sí`, `No`, `Parcial`
- `pizarra: tipo`: `Tiza`, `Blanca`, `Tiza+Blanca`, `Digital`, `Movil`
- `mobiliario`: `Fijo`, `Móvil`

Los edificios E24 y E45 usan una función auxiliar para generar las filas porque casi todas comparten el mismo equipamiento; el orden de campos es el mismo.

## Créditos

Desarrollado por Enrique Mesa Pérez, Profesor Ayudante Doctor del Departamento de Economía Financiera y Contabilidad de la Universidad Pablo de Olavide. Más información en [enrisk.org](https://enrisk.org).

El logotipo de la Universidad Pablo de Olavide es propiedad de la universidad y se usa únicamente como identificación de la institución a la que se refieren los datos.

## Licencia

El código se distribuye bajo licencia MIT (ver `LICENSE`). Los datos pertenecen a la Universidad Pablo de Olavide y se reproducen a partir de su publicación pública.
