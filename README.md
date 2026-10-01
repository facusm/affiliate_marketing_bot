# 📝 Resumen del Proyecto: Affiliate Marketing Bot (v5.0.0)

## 🎯 Objetivo Principal
Un sistema automatizado que transforma la foto y los datos de un producto (ingresados mediante un panel web fácil de usar) en **8 Reels virales en distintos idiomas** (incluyendo 3 variantes regionales de español). El bot publica los videos automáticamente usando la Meta Graph API y usa un Webhook oficial de Instagram para **enviar mensajes directos (DMs) automáticos** con un link de afiliado a los usuarios que comentan una palabra clave específica.

## 🏗️ Arquitectura y Tecnologías
Este proyecto es un pipeline end-to-end asíncrono construido con FastAPI, base de datos PostgreSQL, interfaz gráfica con Streamlit, e integración con LLMs (OpenAI), ElevenLabs (TTS) y MoviePy para el renderizado. Todo el entorno está 100% contenerizado en Docker, resolviendo dependencias complejas de sistema (ImageMagick). Adicionalmente, el entorno está preparado para pruebas locales gratuitas configurando `AI_VIDEO_PROVIDER=mock` en el archivo `.env`. Esto permite testear todo el pipeline de renderizado (MoviePy, subtítulos, audio) en segundos y sin consumir créditos de APIs externas (como Kling).

## 🧠 La Receta Viral (El "Efecto Adictivo")
El sistema no genera videos genéricos; está programado a nivel de código para maximizar la retención del usuario (watch-time) y forzar la interacción:
1. **Arquitectura Híbrida I2V + T2V (Kling v3.0)**: En lugar de repetir un solo clip en loop, el sistema genera **3 clips distintos en paralelo**: un Hero Shot estático del producto (Image-to-Video) + 2 B-Rolls dinámicos generados por Text-to-Video (escena sensorial + producto en uso en macro). Esto elimina el aburrimiento visual por repetición. Además, el usuario recorta manualmente la imagen a **9:16 en el frontend** con `streamlit-cropper`, y el backend solo fuerza el redimensionado a 1080x1920 para garantizar la resolución exigida por Kling sin distorsiones automáticas erróneas.
2. **Efecto Ken Burns (Zoom Digital)**: El clip estático del producto recibe un zoom suave progresivo (1.0→1.15) frame-a-frame en post-producción, aportando dinamismo sin que la IA deforme los píxeles originales.
3. **Subtítulos Estilo Hormozi**: El video procesa el audio palabra por palabra. Los subtítulos aparecen de forma agresiva y dinámica en el centro de la pantalla (de a 1 o 3 palabras). Esto obliga al ojo del usuario a seguir leyendo y evita que haga scroll.
4. **Voz Nativa Acelerada (ElevenLabs)**: Se utilizan locuciones en idiomas nativos que suenan naturales, dinámicas y sin pausas largas.
5. **Curiosity Gap (Vacío de Curiosidad) y Limitación Estricta**: El LLM genera un guion ultra-corto bajo una restricción absoluta de **máximo 30 palabras** (~12 segundos), asegurando que MoviePy nunca loopee videos. Hay REGLA ESTRICTA de nunca mencionar el precio, saltar introducciones educadas y basar el "gancho" inicial en resolver un dolor o problema. Esto maximiza la retención y la necesidad de comentar.
6. **Contraste Visual Premium**: Un filtro oscuro sutil (15% de opacidad) asegura que los subtítulos blancos y brillantes resalten a la perfección.
7. **Fijación del CTA**: El llamado a la acción queda fijo en la pantalla, repitiéndole visualmente al cerebro qué palabra tiene que comentar.

## 🖥️ Interfaz de Usuario (Streamlit)
El sistema incluye un panel de control interactivo en `ui.py`.
- Levantá la interfaz con: `streamlit run ui.py` (o vía Docker)
- **Paso 1:** Subí la foto del producto y recortala interactivamente a 9:16 desde el navegador.
- **Paso 2:** Completá los datos de texto (título, descripción, idiomas, etc.) y generá los Reels.
- Monitoreá la generación paralela de todos los idiomas directamente en la web.

## 🐳 Despliegue en Producción (Docker VPS)
La arquitectura está dockerizada para su rápido despliegue en un VPS (ej. DigitalOcean):
- **`docker-compose.yml`**: Levanta de manera orquestada la Base de Datos (PostgreSQL 15), la API (FastAPI) y la UI (Streamlit).
- **Publicación Automática**: El backend cuenta con un endpoint (`POST /publish/{id}`) que se comunica con la Meta Graph API para subir y publicar los Reels generados automáticamente.
- **Enrutamiento Inteligente Multi-Cuenta**: El webhook fue optimizado para rutear los comentarios usando el `ig_media_id` proveído por Meta tras la publicación, asociando las interacciones al Reel exacto. Además, soporta **8 cuentas de Instagram distintas** (una por idioma/variante regional), utilizando un único token y respondiendo de forma dinámica desde la cuenta correcta.

## 🌍 Arquitectura Multi-Idioma (Eficiencia de Costos)
Para maximizar el alcance global minimizando el gasto en APIs:
- **Paso 1**: El LLM genera un **paquete híbrido**: un guion guía estricto (< 30 palabras) + 2 prompts de B-Roll para Text-to-Video.
- **Paso 2**: Se generan **3 clips mudos en paralelo** pagando la API de Kling: 1 I2V (foto del producto con cámara estática) + 2 T2V (B-Rolls dinámicos generados desde los prompts del LLM).
- **Paso 3**: El LLM redacta 8 guiones adaptados culturalmente en 1 sola llamada, usando el guion guía como referencia de estructura (ES 🇪🇸, ES_LATAM 🇦🇷, ES_MX 🇲🇽, EN, PT, DE, FR, IT). Cada idioma genera su propia palabra clave nativa (ej: OFERTA, OFFER, ANGEBOT).
- **Paso 4**: Se generan 8 audios distintos con voces nativas por variante y se renderizan 8 Reels finales concatenando los 3 clips (con Ken Burns en el I2V) + audio + subtítulos.

## 🔗 Flujo de Trabajo Diferido (Añadir Links Después)
El sistema está diseñado para que puedas probar el contenido sin necesidad de tener las cuentas de afiliado aprobadas desde el día uno.

**Etapa 1: Generación de Pruebas**
- Llamás a la API de generación de videos y **dejás el campo del link de afiliado vacío**.
- El sistema crea los videos perfectamente. Si los publicás y alguien comenta, el Webhook se da cuenta de que no hay link y **no hace nada** (no manda mensajes rotos).

**Etapa 2: Obtención de IDs**
- Una vez que te aprueban en el programa de afiliados y tenés los links, consultás al bot (`GET /products/`) para ver la lista de tus productos generados y obtener el `ID` numérico de cada uno.

**Etapa 3: Activación Mágica**
- Desde el **Inventario de Productos** en la UI web, agregás los links correspondientes a cada idioma (ej. `amazon.es/..` para ES y `amazon.com/..` para EN). Internamente, esto actualiza los links individuales vía `PATCH /products/{id}/affiliate-link`.
- **Resultado Inmediato**: En el milisegundo en que se guardan los links, el Webhook de Instagram se "despierta" para esos idiomas específicos del producto. El próximo comentario que entre recibirá el DM automático con el link de afiliado correcto para su país, sin que tengas que reiniciar el servidor ni regrabar los videos.

## 🚀 Flujo de Publicación Controlada
Para mantener el control absoluto, la publicación en Meta no se hace sin tu permiso.
Desde el panel web de Streamlit, dentro del **Inventario de Productos**, podés revisar cuántos videos ya están renderizados. Cuando estés listo, apretás el botón **"🚀 Publicar Videos en Meta"**.
El sistema se encarga de subir automáticamente los 8 videos a sus cuentas correspondientes de Instagram, vinculando internamente el `ig_media_id` para que el Webhook sepa a quién responder.

## 🤖 Webhook Inteligente (Intents y Respuestas Públicas)
El Webhook no solo reacciona a la palabra clave exacta generada por el bot. Incorpora **Intención de Compra Universal**: si un usuario dice "precio", "info", "quiero" o "link" en su idioma nativo, el sistema lo reconoce y actúa.
Además, el bot no solo manda el DM en privado, sino que hace un `POST` público respondiendo al comentario del usuario (ej: "¡Te envié el link por privado! 🚀"), lo que incrementa el engagement del posteo.

## 🛡️ Pre-Flight Checks y Resiliencia (Checkpoints)
El orquestador de IA cuenta con validaciones estrictas antes de gastar saldo en las APIs:
- Verifica el balance de caracteres en ElevenLabs.
- Valida los tokens de OpenAI y Kling AI mediante endpoints ligeros.
- **Sistema de Checkpoints**: Si un producto ya generó los 3 clips mudos en Kling AI y el proceso se interrumpió, al volver a lanzar el pipeline, el orquestador recuperará los clips existentes desde la base de datos saltándose la generación y evitando cobros dobles, retomando la ejecución desde la fase de doblaje (ElevenLabs).

## 🧹 Sistema de Almacenamiento y Limpieza (Deep Delete)
- **Agrupación Física**: Todo el contenido generado (imágenes, audios TTS, clips crudos Kling y videos virales finales) se guarda y aísla en subcarpetas nombradas con el `ID` único del producto dentro de la carpeta `storage/`.
- **Eliminación Profunda (Deep Delete)**: Si eliminas un producto desde la interfaz de usuario, el sistema no solo lo remueve de la base de datos (y elimina todos sus videos asociados en cascada), sino que **borra físicamente** todos los archivos locales que ese producto haya generado (imágenes, audios y videos), previniendo fugas de memoria o acumulación de archivos huérfanos a largo plazo.

## 🗺️ Roadmap / Próximos Pasos
- [ ] Integración de Webhooks con Meta Graph API para la escucha activa de comentarios en cuentas de Instagram (_es, _en, _pt, etc).
- [ ] Despliegue de la arquitectura contenerizada en DigitalOcean (VPS) con túneles HTTPS seguros para la recepción de eventos.
- [ ] Implementación de tareas programadas (CRON) para la ejecución autónoma del pipeline de generación de contenido.
