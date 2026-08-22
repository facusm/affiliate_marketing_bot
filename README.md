# 📝 Resumen del Proyecto: Affiliate Marketing Bot (v4.0.0)

## 🎯 Objetivo Principal
Un sistema automatizado que transforma la foto y los datos de un producto (ingresados mediante un panel web fácil de usar) en **6 Reels virales en distintos idiomas**. El bot publica los videos automáticamente usando la Meta Graph API y usa un Webhook oficial de Instagram para **enviar mensajes directos (DMs) automáticos** con un link de afiliado a los usuarios que comentan una palabra clave específica.

## 🧠 La Receta Viral (El "Efecto Adictivo")
El sistema no genera videos genéricos; está programado a nivel de código para maximizar la retención del usuario (watch-time) y forzar la interacción:
1. **Visuales Hipnóticas (Kling IA v3.0)**: El motor de IA no recibe prompts simples. Se inyectan comandos de *cinematografía, tomas macro e iluminación volumétrica* para que la foto del producto se transforme en un clip visualmente impactante.
2. **Subtítulos Estilo Hormozi**: El video procesa el audio palabra por palabra. Los subtítulos aparecen de forma agresiva y dinámica en el centro de la pantalla (de a 1 o 3 palabras). Esto obliga al ojo del usuario a seguir leyendo y evita que haga scroll.
3. **Voz Nativa Acelerada (ElevenLabs)**: Se utilizan locuciones en idiomas nativos que suenan naturales, dinámicas y sin pausas largas.
4. **Curiosity Gap (Vacío de Curiosidad)**: El LLM está programado bajo REGLA ESTRICTA para nunca mencionar el precio del producto, basando el "gancho" inicial en resolver un dolor o problema. Esto maximiza la necesidad del usuario de comentar para saber más.
5. **Contraste Visual Premium**: Un filtro oscuro sutil (15% de opacidad) asegura que los subtítulos blancos y brillantes resalten a la perfección.
6. **Fijación del CTA**: El llamado a la acción queda fijo en la pantalla, repitiéndole visualmente al cerebro qué palabra tiene que comentar.

## 🖥️ Interfaz de Usuario (Streamlit)
El sistema incluye un panel de control interactivo en `ui.py`.
- Levantá la interfaz con: `streamlit run ui.py` (o vía Docker)
- Cargá el título, características e imagen física del producto desde el navegador.
- Monitoreá la generación paralela de todos los idiomas directamente en la web.

## 🐳 Despliegue en Producción (Docker VPS)
La arquitectura está dockerizada para su rápido despliegue en un VPS (ej. DigitalOcean):
- **`docker-compose.yml`**: Levanta de manera orquestada la Base de Datos (PostgreSQL 15), la API (FastAPI) y la UI (Streamlit).
- **Publicación Automática**: El backend cuenta con un endpoint (`POST /publish/{id}`) que se comunica con la Meta Graph API para subir y publicar los Reels generados automáticamente.
- **Enrutamiento Inteligente Multi-Cuenta**: El webhook fue optimizado para rutear los comentarios usando el `ig_media_id` proveído por Meta tras la publicación, asociando las interacciones al Reel exacto. Además, soporta **6 cuentas de Instagram distintas** (una por idioma), utilizando un único token y respondiendo de forma dinámica desde la cuenta correcta.

## 🌍 Arquitectura Multi-Idioma (Eficiencia de Costos)
Para maximizar el alcance global minimizando el gasto en APIs:
- **Paso 1**: Se genera **1 solo video mudo** de alta calidad pagando la API de Kling una única vez.
- **Paso 2**: El LLM redacta 6 guiones adaptados culturalmente en 1 sola llamada (ES, EN, PT, DE, FR, IT). Cada idioma genera su propia palabra clave nativa (ej: OFERTA, OFFER, ANGEBOT).
- **Paso 3**: Se generan 6 audios distintos y se renderizan 6 Reels finales usando el mismo video base mudo.

## 🔗 Flujo de Trabajo Diferido (Añadir Links Después)
El sistema está diseñado para que puedas probar el contenido sin necesidad de tener las cuentas de afiliado aprobadas desde el día uno.

**Etapa 1: Generación de Pruebas**
- Llamás a la API de generación de videos y **dejás el campo del link de afiliado vacío**.
- El sistema crea los videos perfectamente. Si los publicás y alguien comenta, el Webhook se da cuenta de que no hay link y **no hace nada** (no manda mensajes rotos).

**Etapa 2: Obtención de IDs**
- Una vez que te aprueban en el programa de afiliados y tenés los links, consultás al bot (`GET /products/`) para ver la lista de tus productos generados y obtener el `ID` numérico de cada uno.

**Etapa 3: Activación Mágica**
- Enviás el link al producto específico mediante una actualización simple (`PATCH /products/{id}/affiliate-link`).
- **Resultado Inmediato**: En el milisegundo en que se guarda el link, el Webhook de Instagram se "despierta" para ese producto. El próximo comentario que entre recibirá el DM automático en su idioma nativo, sin que tengas que reiniciar el servidor ni regrabar los videos.
