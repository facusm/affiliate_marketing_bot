# Affiliate Marketing Bot — Workflow Técnico

> **Versión del análisis:** 2026-08-22 (Actualizado post-refactorización v4.0)  
> **Propósito:** Mapa técnico exhaustivo del estado actual del proyecto.

---

## 1. Árbol de Directorios

```
affiliate_marketing_bot/
├── .env                          # Variables de entorno (API keys, DB, config)
├── .gitignore
├── Dockerfile                    # Docker build para la API y UI
├── docker-compose.yml            # Orquestación de servicios (api, ui, db)
├── README.md
├── requirements.txt              # Dependencias del proyecto
├── ui.py                         # Panel de control web (Streamlit)
├── migrate_db.py                 # Script manual de migración SQL (ALTER TABLE)
├── check_voices.py               # Script utilitario para verificar voces ElevenLabs
├── test_debug.py                 # Script de debug/testing
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # Entry point: FastAPI app, lifespan, router includes
│   ├── orchestrator.py           # Orquestador central: Pipeline AI multi-idioma
│   │
│   ├── api/                      # Capa de endpoints HTTP (FastAPI Routers)
│   │   ├── __init__.py
│   │   ├── pipeline.py           # POST /pipeline/run — Endpoint principal (multipart/form-data)
│   │   ├── products.py           # CRUD de productos + gestión de affiliate links
│   │   ├── llm.py                # POST /llm/generate-script/{id} — Generación de guion
│   │   ├── publish.py            # POST /publish/{id} — Publicación en Instagram (Meta Graph API)
│   │   └── webhook.py            # GET+POST /webhook — Webhook de Instagram (Meta Graph API)
│   │
│   ├── database/                 # Capa de persistencia
│   │   ├── __init__.py
│   │   ├── database.py           # Engine SQLAlchemy, SessionLocal, init_db(), get_db()
│   │   └── models.py             # Modelos ORM: Product, Video, ContentStatus (Enum)
│   │
│   ├── llm/                      # Generación de guiones con LLM
│   │   ├── __init__.py
│   │   └── script_generator.py   # generate_multilang_scripts()
│   │
│   ├── ai_engine/                # Motor de video IA
│   │   ├── __init__.py
│   │   ├── ai_prompt_engineer.py # LLM genera prompts hipnóticos para video IA
│   │   └── ai_video_generator.py # Cliente multi-provider (Kling con subida local, Runway, Luma)
│   │
│   ├── render/                   # Post-producción de video
│   │   ├── __init__.py
│   │   └── viral_renderer.py     # Renderer viral (dark overlay + subtítulos Hormozi)
│   │
│   └── utils/                    # Utilidades compartidas
│       ├── __init__.py
│       ├── elevenlabs.py         # TTS reutilizable + timestamps + voice mapping por idioma
│       └── moviepy_helpers.py    # Helpers MoviePy: overlays, subtítulos, export, font resolution
│
└── storage/                      # Archivos generados (no versionado en git)
    ├── audio/                    # Archivos .mp3 de ElevenLabs TTS
    ├── images/                   # Imágenes de producto subidas localmente
    ├── videos/                   # Clips IA (Kling, etc.)
    └── outputs/                  # Videos finales renderizados (.mp4)
```

---

### 1.1 Interfaz de Usuario (Streamlit)

El archivo `ui.py` provee un panel interactivo dividido en dos pestañas principales (`st.tabs`):
1. **🚀 Generar Reels**: Formulario para la ingesta de un producto nuevo (título, foto, descripción, etc.) y selección de idiomas para lanzar el pipeline completo.
2. **📦 Inventario de Productos**: Consume `GET /products/` para listar los productos generados, mostrando su ID, título, descripción/palabras clave (`features`), estado y cantidad de videos. Permite actualizar el link de afiliado en tiempo real consumiendo `PATCH /products/{id}/affiliate-link`.

---

## 2. Esquema de Base de Datos (SQLAlchemy ORM)

**Motor:** PostgreSQL (driver: `psycopg` v3)  
**ORM:** SQLAlchemy 2.0+ con `declarative_base()`  
**Sin Alembic:** Las migraciones se manejan con scripts SQL manuales (`migrate_db.py`).

### 2.1 Enum `ContentStatus`

```python
class ContentStatus(enum.Enum):
    PENDING            = "pending"
    SCRAPED            = "scraped"
    SCRIPT_GENERATED   = "script_generated"
    MEDIA_DOWNLOADED   = "media_downloaded"
    RENDERED           = "rendered"
    PUBLISHED          = "published"
    ERROR              = "error"
```

### 2.2 Tabla `products`

| Campo           | Tipo SQLAlchemy               | Constraints / Default              | Descripción                                       |
|-----------------|-------------------------------|-------------------------------------|---------------------------------------------------|
| `id`            | `Integer`                     | PK, index                          | ID autoincremental                                |
| `url`           | `String`                      | unique, index, NOT NULL             | URL original del producto en marketplace          |
| `title`         | `String`                      | nullable                            | Título del producto                               |
| `price`         | `Float`                       | nullable                            | Precio del producto                               |
| `features`      | `Text`                        | nullable                            | Descripción / características del producto        |
| `image_url`     | `String`                      | nullable                            | URL de la imagen principal del producto           |
| `rating`        | `Float`                       | nullable                            | Rating promedio (estrellas)                       |
| `reviews_count` | `Integer`                     | nullable                            | Cantidad de reseñas / opiniones                   |
| `status`        | `Enum(ContentStatus)`         | default=`PENDING`                   | Estado actual del pipeline para este producto     |
| `created_at`    | `DateTime`                    | default=`utcnow`                    | Fecha de creación                                 |
| `updated_at`    | `DateTime`                    | default=`utcnow`, onupdate=`utcnow`| Última actualización                              |

**Relaciones:**
- `videos` → `relationship("Video", back_populates="product", cascade="all, delete-orphan")`

### 2.3 Tabla `videos`

| Campo               | Tipo SQLAlchemy           | Constraints / Default  | Descripción                                              |
|----------------------|---------------------------|-------------------------|----------------------------------------------------------|
| `id`                 | `Integer`                 | PK, index               | ID autoincremental                                       |
| `product_id`         | `Integer`                 | FK→`products.id`, NOT NULL | Relación con el producto                              |
| `hook`               | `Text`                    | nullable                | Gancho inicial del guion (3 seg)                         |
| `script`             | `Text`                    | nullable                | Cuerpo/desarrollo del guion                              |
| `call_to_action`     | `Text`                    | nullable                | Llamado a la acción final                                |
| `cta_keyword`        | `String`                  | nullable                | Palabra clave del CTA en MAYÚSCULAS (ej: OFERTA, OFFER) |
| `keywords`           | `Text`                    | nullable                | JSON string con keywords de Pexels (inglés)              |
| `engine`             | `String`                  | default=`"pexels"`      | Motor usado: `"pexels"` (Pipeline A) o `"ai"` (Pipeline B)|
| `ai_video_prompt`    | `Text`                    | nullable                | Prompt usado para generar video IA (solo Pipeline B)     |
| `audio_path`         | `String`                  | nullable                | Ruta local al archivo de audio TTS (.mp3)                |
| `stock_videos_paths` | `Text`                    | nullable                | JSON string con rutas a clips de video                   |
| `final_video_path`   | `String`                  | nullable                | Ruta al video final renderizado (.mp4)                   |
| `ig_media_id`        | `String`                  | nullable                | ID de Instagram devuelto al publicar el Reel             |
| `affiliate_url`      | `String`                  | nullable                | Link de afiliado asociado a este idioma/video            |
| `status`             | `Enum(ContentStatus)`     | default=`PENDING`       | Estado del procesamiento de este video                   |
| `created_at`         | `DateTime`                | default=`utcnow`        | Fecha de creación                                        |
| `updated_at`         | `DateTime`                | default=`utcnow`, onupdate | Última actualización                                  |

**Relaciones:**
- `product` → `relationship("Product", back_populates="videos")`

*(Nota: Los campos `language` y `base_video_path` fueron sincronizados correctamente en el ORM en v4.0)*

### 2.4 Diagrama Entidad-Relación

```mermaid
erDiagram
    PRODUCTS ||--o{ VIDEOS : "has many"
    
    PRODUCTS {
        int id PK
        string url UK
        string title
        float price
        text features
        string image_url
        float rating
        int reviews_count
        enum status
        datetime created_at
        datetime updated_at
    }
    
    VIDEOS {
        int id PK
        int product_id FK
        text hook
        text script
        text call_to_action
        string cta_keyword
        text keywords "(JSON)"
        string engine
        text ai_video_prompt
        string language
        string base_video_path "(JSON)"
        string audio_path
        text stock_videos_paths "(JSON)"
        string final_video_path
        string affiliate_url
        enum status
        datetime created_at
        datetime updated_at
    }
```

---

## 3. Endpoints de FastAPI

**Base URL:** `http://localhost:8000`  
**Versión API:** 4.0.0  
**Lifespan:** Ejecuta `init_db()` (crea tablas si no existen) al arrancar.

### 3.1 Health Check

| Método | Ruta | Tags | Descripción |
|--------|------|------|-------------|
| `GET`  | `/`  | —    | Health check básico → `{"status": "ok", "message": "..."}` |

### 3.2 Router: Pipeline (`/pipeline`)

#### `POST /pipeline/run` — Ingesta Directa (Endpoint Principal)

> Crea un `Product` en DB a partir de datos directos (subidos mediante un formulario de Streamlit o app web) y ejecuta el pipeline completo.

**Formato:** `multipart/form-data`

**Campos de Formulario (`Form`):**
| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `title` | `str` | *Requerido* | Título del producto |
| `price` | `float` | `0.0` | Precio (omitido/ignorado por estrategia de *Curiosity Gap*) |
| `description` | `str` | `""` | Características y detalles |
| `rating` | `float` | `null` | Rating en estrellas |
| `reviews_count`| `int` | `null` | Cantidad de reseñas |

**Archivo Subido (`File`):**
- `image`: Archivo físico de la imagen (PNG, JPG, WEBP). Se guarda localmente y se pasa en Base64 a Kling.

**Query Params:**
| Param      | Tipo   | Default                       | Descripción                                          |
|------------|--------|-------------------------------|------------------------------------------------------|
| `languages`| `str`  | `"es,es_latam,es_mx,en,pt,de,fr,it"` | Códigos de idioma separados por coma (incluye 3 variantes de español) |

---

#### `POST /pipeline/run/{product_id}` — Desde Producto Existente (Legacy)

> Ejecuta el pipeline sobre un producto previamente cargado.

**Path Params:** `product_id: int`  
**Query Params:** `languages` (igual que el anterior).  
**Body:** Ninguno.

---

### 3.3 Router: Products (`/products`)

| Método   | Ruta                                    | Body                                        | Descripción                                     |
|----------|-----------------------------------------|---------------------------------------------|--------------------------------------------------|
| `GET`    | `/products/`                            | —                                           | Lista todos los productos con conteo de videos   |
| `GET`    | `/products/{product_id}`                | —                                           | Detalle de un producto + lista de videos por idioma |
| `PATCH`  | `/products/{product_id}/affiliate-link` | `{"links": {"es": "...", "es_latam": "..."}}` | Agregar/actualizar link de afiliado por idioma    |
| `DELETE` | `/products/{product_id}/affiliate-link` | —                                           | Eliminar links de afiliado                        |

**Modelo `AffiliateLinkUpdate`:**
```json
{
    "links": {
        "es": "https://amazon.es/...",
        "es_latam": "https://amazon.com/...?tag=ar",
        "es_mx": "https://amazon.com.mx/...",
        "en": "https://amazon.com/..."
    }
}
```

---

### 3.4 Router: Publish (`/publish`)

| Método | Ruta | Body | Descripción |
|--------|------|------|-------------|
| `POST` | `/publish/{video_id}` | — | Sube y publica un único video generado en Instagram Reels. |
| `POST` | `/publish/product/{product_id}` | — | Sube y publica *todos* los videos (`RENDERED`) asociados al producto. Encola tareas asíncronas en bloque. |

---

### 3.4 Router: LLM (`/llm`)

| Método | Ruta                              | Body | Descripción                                          |
|--------|-----------------------------------|------|------------------------------------------------------|
| `POST` | `/llm/generate-script/{product_id}` | —  | Genera guion con OpenAI y crea registro `Video` en DB |

---

### 3.8 Router: Webhook (`/webhook`)

| Método | Ruta        | Body / Params                               | Descripción                                      |
|--------|-------------|---------------------------------------------|--------------------------------------------------|
| `GET`  | `/webhook`  | QP: `hub.mode`, `hub.verify_token`, `hub.challenge` | Verificación del webhook por Meta        |
| `POST` | `/webhook`  | JSON event body de Meta Graph API            | Recibe eventos de Instagram (comentarios → DM automático) |

**Flujo del Webhook POST:**
1. Meta envía un evento de comentario de Instagram.
2. Se limpia el texto del comentario (quita puntuación, pasa a UPPERCASE).
3. Se verifica si hay coincidencia con `Video.cta_keyword` o si contiene **intención de compra universal** (por ejemplo: "precio", "info", "quiero", "link" para español).
4. Si hay match → se obtiene `Product.affiliate_url` del producto asociado.
5. Se selecciona el template de DM según `Video.language`.
6. Se realiza un `POST` público para responder al comentario del usuario (ej: "¡Te envié el link por privado! 🚀").
7. Se envía el DM privado vía Meta Graph API (`POST /v19.0/{ACCOUNT_ID}/messages`).
8. El procesamiento corre en `BackgroundTasks` para devolver `200 OK` rápido.

---

## 4. Flujo del Pipeline AI

*(Desde v4.0, el Pipeline A/Pexels fue eliminado por completo, consolidando la app únicamente en videos generados por IA)*

### 4.1 Arquitectura de Alto Nivel

```mermaid
flowchart TD
    A["📥 POST /pipeline/run (multipart)"] --> B["Guardar imagen local"]
    B --> PB1["LLM: generate_video_prompt()"]
    
    PB1 --> PB2["Paso 2+3 en PARALELO"]
    
    subgraph PB2["asyncio.gather()"]
        PB2A["Kling API: image-to-video → 1 video mudo"]
        PB2B["LLM: generate_multilang_scripts() → N guiones"]
    end
    
    PB2 --> PB3["Para cada idioma (en PARALELO, SessionLocal aislada)"]
    
    subgraph PB3["asyncio.gather() × N idiomas"]
        PB3A["ElevenLabs TTS con timestamps (voz nativa)"]
        PB3A --> PB3B["Viral Renderer: video mudo + audio + subtítulos"]
        PB3B --> PB3C["Video DB registro + actualización"]
    end
    
    PB3 --> PB4["N Reels Finales (.mp4)"]
```

### 4.2 Pipeline AI Video Multi-Idioma

**Archivo principal:** `app/orchestrator.py` → `_run_pipeline_ai()`

| Paso | Módulo | Función | Input | Output |
|------|--------|---------|-------|--------|
| 0 | `app/orchestrator.py` | `_preflight_checks()` | (Variables de entorno) | *Ping a OpenAI, ElevenLabs, y Kling. Corta la ejecución si hay fallos o falta de saldo.* |
| 1 | `app/ai_engine/ai_prompt_engineer.py` | `generate_video_prompt()` | Título, features, image_url, price, num_clips=2 | `AIVideoPrompt` (video_prompt, clip_prompts[], scene_description, duration, camera_movement) |
| 2 ‖ | `app/ai_engine/ai_video_generator.py` | `generate_ai_video_batch()` | clip_prompts[], image_url (local filepath), aspect_ratio="9:16" | paths[] (`.mp4` descargados) |
| 3 ‖ | `app/llm/script_generator.py` | `generate_multilang_scripts()` | Título, precio, features, rating, reviews, languages[] | `LangScript[]` (hook, body, cta, cta_keyword, keywords × N idiomas) |
| 4 ‖×N | `app/utils/elevenlabs.py` | `generate_tts_with_timestamps()` | text, voice_id (nativo del idioma) | (audio_path, word_timestamps[]) |
| 5 ‖×N | `app/render/viral_renderer.py` | `render_viral_video()` | ai_clips_paths, audio_path, hook_text, word_timestamps, cta_keyword | `.mp4` viral en `storage/outputs/` |

> **Sistema de Resumption (Checkpoints)**: Antes de iniciar el Paso 1, el orquestador verifica si ya hay videos persistidos en la base de datos con un `base_video_path` existente (ej: Kling AI ya fue ejecutado en un run previo pero falló el TTS). En tal caso, se **saltan** los pasos 1 y 2, y se procede directo al Paso 3, ahorrando créditos de API.

> **Nota:** `‖` indica ejecución en paralelo con `asyncio.gather()`.
> Los pasos 2 y 3 corren en paralelo. El paso 4+5 corre en paralelo para cada idioma. Para evitar conflictos de base de datos concurrente, el paso 4 crea su propia `SessionLocal()`.

**Composición del Reel viral (MoviePy, `viral_renderer.py`):**
- Capa 0: Video IA base (clips Kling concatenados, resize a 1080×1920)
- Capa 1: Dark overlay (ColorClip negro, opacity 15%)
- Capa 2: Hook/CTA text fijo (amarillo, stroke negro, tercio superior, toda la duración)
- Capa 3: Subtítulos dinámicos estilo Hormozi (grupos de 3 palabras, sincronizados con timestamps, centro)
- Codec: libx264, audio_codec: aac, fps: 30, preset: fast

### 4.4 Detalle del AI Video Generator (Multi-Provider)

**Archivo:** `app/ai_engine/ai_video_generator.py`

```mermaid
flowchart LR
    A["generate_ai_video()"] --> B{"AI_VIDEO_PROVIDER?"}
    B -->|"kling"| C["_generate_kling()"]
    B -->|"runway"| D["_generate_runway()"]
    B -->|"luma"| E["_generate_luma()"]
    B -->|"replicate"| F["_generate_replicate()"]
    
    C --> G["API Key Auth (Bearer)"]
    G --> H{"image_url?"}
    H -->|"sí"| I["POST /v1/videos/image2video (kling-v3.0)"]
    H -->|"no"| J["POST /v1/videos/text2video (kling-v1-6)"]
    I --> K["_poll_and_download()"]
    J --> K
    K --> L[".mp4 descargado en storage/videos/{id}/"]
```

**Patrón async común a todos los providers:**
1. **Enviar job** → POST con el prompt → recibir `task_id`/`job_id`
2. **Polling** → GET status cada 10s (max 300s) hasta `succeeded`/`failed`
3. **Download** → GET streaming del video → guardar en disco

**Auth de Kling:** API Key enviada en el header Authorization como Bearer token.

> [!IMPORTANT]
> Los providers Runway, Luma y Replicate están implementados pero **referencian una variable `AI_VIDEO_API_KEY`** que **no existe** en el código ni en `.env`. Solo Kling tiene sus claves correctamente configuradas (`KLING_API_KEY`).

### 4.5 Detalle del LLM (OpenAI)

**Modelo utilizado:** `gpt-4o-mini`  
**Técnica:** Structured Outputs via `client.beta.chat.completions.parse()` con `response_format` Pydantic.

| Función | Modelo Pydantic de respuesta | Prompt | Uso |
|---------|------------------------------|--------|-----|
| `generate_multilang_scripts()` | `MultiLangScriptResponse` → `list[LangScript]` | System prompt en inglés + reglas estrictas de *Curiosity Gap* (sin mencionar precio) + datos del producto + lista de idiomas | Generar guiones en varios idiomas |
| `generate_video_prompt()` | `AIVideoPrompt` | `VIRAL_VIDEO_SYSTEM_PROMPT` (reglas de cinematografía hipnótica) + datos del producto | Prompt de video IA para Kling |

**Modelos Pydantic del LLM:**

```python
# Pipeline B — por idioma
class LangScript(BaseModel):
    language_code: str  # Código: es, es_latam, es_mx, en, pt, de, fr, it
    hook: str
    body: str
    cta_keyword: str    # Keyword nativa (OFERTA, OFFER, ANGEBOT...)
    cta: str
    keywords: list[str] # Siempre en inglés, iguales entre idiomas

# Pipeline B — wrapper
class MultiLangScriptResponse(BaseModel):
    scripts: list[LangScript]

# Pipeline B — prompt de video
class AIVideoPrompt(BaseModel):
    video_prompt: str       # Prompt completo para API de video
    scene_description: str  # Descripción legible (español, para logs)
    suggested_duration: float  # 3-5 seg
    camera_movement: str    # Movimiento de cámara principal
    num_clips: int          # 2-3 clips distintos
    clip_prompts: list[str] # Prompts individuales por clip
```

### 4.6 Detalle de ElevenLabs TTS

**Archivo:** `app/utils/elevenlabs.py`

| Función | Endpoint ElevenLabs | Output | Uso |
|---------|---------------------|--------|-----|
| `generate_tts()` | `POST /v1/text-to-speech/{voice_id}` | `.mp3` (bytes directos) | Pipeline A (via `media_manager.py`) |
| `generate_tts_with_timestamps()` | `POST /v1/text-to-speech/{voice_id}/with-timestamps` | `.mp3` (base64 decoded) + `word_timestamps[]` | Pipeline B (subtítulos sincronizados) |

**Modelo de voz:** `eleven_multilingual_v2`  
**Voice settings:** `stability: 0.5`, `similarity_boost: 0.75`

**Mapeo de voces nativas por idioma** (`resolve_voice_for_language()`):
```
es      → ELEVENLABS_VOICE_ES     (fallback: ELEVENLABS_VOICE_ID)
es_latam → ELEVENLABS_VOICE_LATAM  (fallback: ELEVENLABS_VOICE_ID)
es_mx   → ELEVENLABS_VOICE_MX     (fallback: ELEVENLABS_VOICE_ID)
en      → ELEVENLABS_VOICE_EN
pt      → ELEVENLABS_VOICE_PT
de      → ELEVENLABS_VOICE_DE
fr      → ELEVENLABS_VOICE_FR
it      → ELEVENLABS_VOICE_IT
```

**Formato de `word_timestamps`:**
```json
[
    {"word": "Hola", "start": 0.0, "end": 0.35},
    {"word": "esto", "start": 0.40, "end": 0.58},
    ...
]
```
Generados internamente por `_chars_to_word_timestamps()` a partir de la alineación caracter-por-caracter de ElevenLabs.

---

## 5. Variables de Entorno (`.env`)

| Variable                 | Requerida | Descripción                                                    |
|--------------------------|-----------|----------------------------------------------------------------|
| `OPENAI_API_KEY`         | ✅        | API key de OpenAI (gpt-4o-mini)                                |
| `ELEVENLABS_API_KEY`     | ✅        | API key de ElevenLabs TTS                                      |
| `ELEVENLABS_VOICE_ID`    | ✅        | Voice ID default (fallback global)                             |
| `ELEVENLABS_VOICE_ES`    | ❌        | Voice ID nativo para español (España)                          |
| `ELEVENLABS_VOICE_LATAM` | ❌        | Voice ID nativo para español (Argentina / Rioplatense)         |
| `ELEVENLABS_VOICE_MX`    | ❌        | Voice ID nativo para español (México)                          |
| `ELEVENLABS_VOICE_EN`    | ❌        | Voice ID nativo para inglés                                    |
| `ELEVENLABS_VOICE_PT`    | ❌        | Voice ID nativo para portugués                                 |
| `ELEVENLABS_VOICE_DE`    | ❌        | Voice ID nativo para alemán                                    |
| `ELEVENLABS_VOICE_FR`    | ❌        | Voice ID nativo para francés                                   |
| `ELEVENLABS_VOICE_IT`    | ❌        | Voice ID nativo para italiano                                  |
| `PEXELS_API_KEY`         | ❌        | Obsoleto                                                       |
| `DATABASE_URL`           | ✅        | Connection string PostgreSQL (`postgresql://user:pass@host/db`) |
| `AI_VIDEO_PROVIDER`      | ❌        | Provider de video IA (default: `kling`)                        |
| `KLING_API_KEY`          | ✅**      | API Key estándar de Kling                                      |
| `META_VERIFY_TOKEN`      | ❌***     | Token de verificación del webhook de Instagram                 |
| `META_ACCESS_TOKEN`      | ❌***     | Access Token de Meta Graph API (long-lived)                    |
| `INSTAGRAM_ACCOUNT_ID_ES`      | ❌*** | ID de la cuenta de Instagram Business (Español — España)     |
| `INSTAGRAM_ACCOUNT_ID_ES_LATAM`| ❌*** | ID de la cuenta de Instagram Business (Español — Argentina)  |
| `INSTAGRAM_ACCOUNT_ID_ES_MX`  | ❌*** | ID de la cuenta de Instagram Business (Español — México)     |
| `INSTAGRAM_ACCOUNT_ID_EN`| ❌***     | ID de la cuenta de Instagram Business (Inglés)                 |
| `INSTAGRAM_ACCOUNT_ID_PT`| ❌***     | ID de la cuenta de Instagram Business (Portugués)              |
| `INSTAGRAM_ACCOUNT_ID_DE`| ❌***     | ID de la cuenta de Instagram Business (Alemán)                 |
| `INSTAGRAM_ACCOUNT_ID_FR`| ❌***     | ID de la cuenta de Instagram Business (Francés)                |
| `INSTAGRAM_ACCOUNT_ID_IT`| ❌***     | ID de la cuenta de Instagram Business (Italiano)               |
| `PUBLIC_BASE_URL`        | ❌***     | URL pública base (ej: `http://ip-del-vps:8000`) para Meta      |

> `*` Solo necesario si `engine=pexels`.  
> `**` Solo necesario si `AI_VIDEO_PROVIDER=kling` (o default).  
> `***` Necesario para que el webhook de Instagram funcione. Marcados como "FALTA MODIFICAR" en el `.env` actual.

---

## 6. Dependencias del Proyecto

```
fastapi>=0.103.1        # Framework web
uvicorn>=0.23.2         # ASGI server
sqlalchemy>=2.0.20      # ORM
psycopg[binary]>=3.1.0  # PostgreSQL driver (v3, evita bug de cp1252 en Windows)
pydantic>=2.3.0         # Validación de datos + Structured Outputs de OpenAI
pydantic-settings>=2.0.3
beautifulsoup4>=4.12.2  # Parsing HTML
moviepy>=2.0.0          # Post-producción de video
openai>=1.3.0           # Cliente OpenAI (async, Structured Outputs)
python-dotenv>=1.0.0    # Carga de .env
httpx>=0.25.0           # Cliente HTTP async (TTS, Kling)
python-multipart>=0.0.6 # Procesamiento multipart/form-data y upload
streamlit>=1.28.0       # Panel de control web
```

---

## 7. Observaciones Arquitectónicas (v4.0.0)

### 7.1 Panel de Control (Streamlit)
El proyecto incluye ahora un frontend en `ui.py` ejecutado con `streamlit run ui.py`. Este frontend se comunica con el endpoint FastAPI `POST /pipeline/run` pasándole la imagen subida físicamente a través de multipart form-data.

### 7.2 Manejo de Concurrencia en DB
Dado que las iteraciones de la generación de reels por idioma se procesan mediante `asyncio.gather()` de manera concurrente (en `orchestrator.py`), cada rutina de idioma instancia su propia conexión y sesión a la base de datos `SessionLocal()` temporalmente aislada en vez de usar la compartida del endpoint. Esto previene un *race condition* en SQLAlchemy.

### 7.3 Mapa de Dependencias entre Módulos

```mermaid
flowchart BT
    subgraph Frontend
        ui["ui.py (Streamlit)"]
    end

    subgraph API["app/api/"]
        pipeline["pipeline.py (multipart)"]
        products["products.py"]
        llm_api["llm.py"]
        webhook["webhook.py"]
    end
    
    subgraph Core["Core"]
        orch["orchestrator.py"]
        db["database/"]
    end
    
    subgraph Services["Servicios"]
        llm_svc["llm/script_generator.py"]
        ai_prompt["ai_engine/ai_prompt_engineer.py"]
        ai_video["ai_engine/ai_video_generator.py"]
        vir_render["render/viral_renderer.py"]
    end
    
    subgraph Utils["utils/"]
        eleven["elevenlabs.py"]
        moviepy_h["moviepy_helpers.py"]
    end
    
    ui --> pipeline
    pipeline --> orch
    orch --> llm_svc
    orch --> ai_prompt
    orch --> ai_video
    orch --> vir_render
    orch --> eleven
    orch --> db
    
    vir_render --> moviepy_h
    
    llm_api --> llm_svc
    webhook --> db
    products --> db
    
    pipeline --> db
    llm_api --> db
```
