# Cribado bursátil semanal

Cribado de unas 150 acciones (IBEX 35, Euro Stoxx 50 y resto del Mercado Continuo) con indicadores de rentabilidad, PER, payout y deuda neta/EBITDA. Cada sábado se ejecuta solo en GitHub Actions y publica un dashboard en GitHub Pages.

## Puesta en marcha (unos 10 minutos)

1. **Crea un repositorio** en GitHub (p. ej. `cribado-bolsa`). GitHub Pages es gratis si el repositorio es público; si es privado necesitas GitHub Pro.
2. **Sube el contenido de esta carpeta**, incluida la carpeta oculta `.github`. Lo más fácil es usar «Add file → Upload files» y arrastrar todo.
3. **Da permiso de escritura al workflow:** *Settings → Actions → General → Workflow permissions → Read and write permissions*.
4. **Activa Pages:** *Settings → Pages → Source: Deploy from a branch → Branch `main`, carpeta `/docs`*.
5. **Lanza la primera ejecución:** *Actions → Cribado semanal → Run workflow*. Tarda unos 5 minutos. A partir de entonces se ejecuta cada sábado a las 07:17 UTC.
6. El dashboard queda en `https://TU-USUARIO.github.io/cribado-bolsa/`. Hasta la primera ejecución muestra datos de demostración, marcados con un aviso.

## Archivos

| Archivo | Qué hace |
|---|---|
| `tickers.csv` | Universo de valores. **Revísalo tras cada revisión trimestral de índices** (BME y STOXX). |
| `screener.py` | Descarga, calcula indicadores, puntúa y genera alertas. Los umbrales están en `UMBRALES`, al principio del archivo. |
| `.github/workflows/semanal.yml` | Programación semanal. |
| `docs/index.html` | Dashboard (HTML estático). |
| `docs/data/latest.json` | Foto de la semana. |
| `docs/data/history/*.csv` | Histórico semanal, útil también para docencia o investigación. |

## Ejecución local

```bash
pip install -r requirements.txt
python screener.py          # datos reales
python screener.py --demo   # datos sintéticos, sin red
```

## Avisos

- **Yahoo puede bloquear las IP de GitHub Actions.** Si el workflow falla con menos de la mitad de valores descargados, ejecútalo en tu ordenador (`python screener.py`) y sube `docs/data` con un commit.
- **Datos no oficiales.** Contrasta cualquier cifra relevante con las cuentas anuales o la CNMV. El aviso «revisar moneda» señala empresas que cotizan en euros pero reportan en otra divisa (p. ej. ArcelorMittal, en USD), donde Yahoo a veces calcula mal P/VC o PER.
- **Herramienta de cribado, no asesoramiento financiero.**
