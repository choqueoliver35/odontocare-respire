# OdontoCare Respire v2 - DeepSeek/Ollama

Versión renovada con soporte real para DeepSeek mediante Ollama, dashboard con datos demo y menú lateral fijo.

## Ejecutar sin IA local

```powershell
python main.py
```

En este modo usa el motor interno.

## Ejecutar con DeepSeek

Primero asegúrate de tener Ollama y el modelo descargado:

```powershell
ollama --version
ollama list
ollama pull deepseek-r1:1.5b
```

Luego ejecuta:

```powershell
$env:USE_OLLAMA="1"
$env:OLLAMA_MODEL="deepseek-r1:1.5b"
$env:OLLAMA_URL="http://localhost:11434/api/generate"
python main.py
```

Al iniciar debe aparecer en consola:

```text
USE_OLLAMA: True
OLLAMA_MODEL: deepseek-r1:1.5b
```

## Credenciales

Administrador:

```text
admin@odontocare.edu.bo
admin123
```

Estudiante demo:

```text
demo@odontocare.edu.bo
demo123
```

## Pruebas sugeridas

- ¿Qué es historia clínica odontológica?
- ¿Qué es endodoncia?
- ¿Qué es prótesis dental?
- ¿Qué es caries?
- ¿Cuántos dientes tiene un humano?
- ¿Cuál es la diferencia entre gingivitis y periodontitis?
- Estoy estresado porque no sé hacer una historia clínica.
- Me falta el aire, siento que me voy a desmayar y no puedo continuar.
- Resuelve una integral.

## Cambios v2

- Integración real con Ollama / DeepSeek.
- Respuestas forzadas en español mediante prompt.
- Limpieza de razonamiento tipo `<think>` o `Thinking...`.
- Indicador visual “Pensando...” mientras espera respuesta.
- Menú lateral fijo para no perder el botón de cerrar sesión.
- `model_used` guardado en base de datos.
- Dashboard conserva datos demo precargados.

## Versión documental local

Esta variante permite desplegar el sistema sin Ollama ni DeepSeek. El chat usa:

1. Motor interno de reglas para detección de estrés emocional.
2. Motor de búsqueda documental local sobre PDFs/TXT cargados.
3. SQLite FTS5 para indexar fragmentos, buscar por términos odontológicos y devolver fuente + página.

### Subir libros o apuntes

Desde la sección **Temario y biblioteca local** se puede subir un archivo PDF o TXT. El sistema extrae texto, lo divide en fragmentos e indexa el contenido. Si el PDF es una imagen escaneada, no podrá leerlo sin OCR.

### Alcance de las respuestas

Las respuestas se basan únicamente en la biblioteca cargada. No generan análisis clínico profundo fuera de los documentos ni reemplazan la validación de un docente u odontólogo.

### Despliegue gratuito recomendado

Puede subirse a Render, Railway, PythonAnywhere u otro hosting Flask porque ya no necesita cargar modelos locales. En Render, usar:

```bash
Build command: pip install -r requirements.txt
Start command: gunicorn main:app
```
