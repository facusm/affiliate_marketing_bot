# Walkthrough — Refactorización v4.0

## Resumen

Refactorización profunda del Affiliate Marketing Bot: se eliminó Pipeline A (Pexels/stock), se corrigió el ORM desincronizado, se solucionó el race condition en operaciones concurrentes de DB, se refactorizó el endpoint principal para aceptar subida física de imágenes, y se creó un frontend Streamlit.

## Cambios Realizados

### 1. Arreglo Crítico de ORM (`models.py`)
- **Agregado** `affiliate_url: String` a la tabla `Product`
- **Agregado** `language: String` a la tabla `Video`
- **Agregado** `base_video_path: Text` a la tabla `Video`
- **Cambiado** default de `engine` de `"pexels"` a `"ai"`

### 2. Eliminación de Pipeline A (6 archivos borrados)
| Archivo eliminado | Razón |
|---|---|
| `app/scraper/meli_scraper.py` | Scraper de MercadoLibre ya no es necesario (ingesta directa) |
| `app/media/media_manager.py` | Lógica duplicada de TTS + Pexels stock download |
| `app/render/video_renderer.py` | Renderer de Pipeline A reemplazado por `viral_renderer.py` |
| `app/api/scraper.py` | Router endpoint eliminado |
| `app/api/media.py` | Router endpoint eliminado |
| `app/api/render.py` | Router endpoint eliminado |

### 3. Limpieza de dependencias (`requirements.txt`)
- **Eliminado:** `playwright`, `anthropic`, `elevenlabs` (SDK)
- **Agregado:** `python-multipart` (Form/File uploads), `streamlit` (frontend)

### 4. Solución de Race Condition (`orchestrator.py`)
- Cada tarea paralela de idioma en `_process_language()` ahora instancia su propia `SessionLocal()` 
- Los datos del producto se capturan como valores simples (`product_data: dict`) antes de entrar al paralelismo
- Cada sesión se cierra en un bloque `finally`

### 5. Refactorización del Endpoint (`pipeline.py`)
- `POST /pipeline/run` ahora acepta `multipart/form-data`
- Campos de producto via `Form(...)`: title, price, description, rating, reviews_count, affiliate_url
- Imagen via `File(...)` / `UploadFile` → guardada en `storage/images/`
- Eliminada la selección de engine (solo Pipeline B)

### 6. Soporte de imágenes locales (`ai_video_generator.py`)
- Nueva función `_resolve_image_ref()`: detecta si la imagen es URL o ruta local
- Rutas locales se convierten a base64 data URI para compatibilidad con la API de Kling
- Default de `AI_VIDEO_PROVIDER` cambiado de `"runway"` a `"kling"`

### 7. Frontend Streamlit (`ui.py`)
- Panel de control web con formulario de producto
- File uploader con vista previa de imagen
- Selector multi-idioma con banderas
- Envío HTTP multipart/form-data al backend FastAPI
- Visualización de resultados: métricas, detalle por idioma, errores
- Sidebar con health check del backend

### 8. Archivos auxiliares actualizados
- `main.py` — Eliminados imports de routers borrados, versión bumpeada a 4.0.0
- `migrate_db.py` — Actualizado para cubrir todas las columnas faltantes

## Verificación
- Imports del proyecto verificados con `from app.main import app`
- Requiere `python-multipart` y `streamlit` instalados en el venv
