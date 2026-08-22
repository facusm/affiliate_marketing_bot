"""
Affiliate Marketing Bot — Panel de Control (Streamlit)

Interfaz web para subir productos y lanzar el pipeline de generación
de Reels virales multi-idioma.

Ejecutar con:
  streamlit run ui.py
"""

import streamlit as st
import requests

# ─── Configuración ────────────────────────────────────────────────────────────

API_BASE_URL = "http://localhost:8000"

LANGUAGE_OPTIONS = {
    "es": "🇪🇸 Español (LATAM)",
    "en": "🇬🇧 English",
    "pt": "🇧🇷 Português",
    "de": "🇩🇪 Deutsch",
    "fr": "🇫🇷 Français",
    "it": "🇮🇹 Italiano",
}

# ─── Config de Página ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Affiliate Marketing Bot",
    page_icon="🎬",
    layout="centered",
)

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🎬 Affiliate Marketing Bot")
st.caption("Pipeline de generación de Reels virales multi-idioma con IA")
st.divider()

# ─── Formulario Principal ─────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["🚀 Generar Reels", "📦 Inventario de Productos"])

with tab1:
    with st.form("product_form", clear_on_submit=False):
        st.subheader("📦 Datos del Producto")

        title = st.text_input(
            "Título del Producto *",
            placeholder="Mandolina de Cocina Profesional 5 en 1",
        )

        rating = st.number_input(
            "Rating (estrellas)",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.1,
            format="%.1f",
        )

        features = st.text_area(
            "Características / Descripción",
            placeholder="Corta verduras en segundos. Acero inoxidable, 5 cuchillas intercambiables, base antideslizante.",
            height=100,
        )

        reviews_count = st.number_input(
            "Cantidad de Reseñas",
            min_value=0,
            value=0,
            step=10,
        )

        affiliate_url = st.text_input(
            "Link de Afiliado (opcional)",
            placeholder="https://tienda.mercadolibre.com.ar/...?aff=123",
        )

        st.divider()
        st.subheader("📸 Foto del Producto")

        image = st.file_uploader(
            "Subí la foto del producto *",
            type=["png", "jpg", "jpeg", "webp"],
            help="La foto se usará como referencia para generar el video IA con Kling.",
        )

        if image:
            st.image(image, caption="Vista previa", width=250)

        st.divider()
        st.subheader("🌍 Idiomas")

        languages = st.multiselect(
            "Seleccioná los idiomas para los Reels",
            options=list(LANGUAGE_OPTIONS.keys()),
            default=list(LANGUAGE_OPTIONS.keys()),
            format_func=lambda x: LANGUAGE_OPTIONS[x],
        )

        st.divider()
        submitted = st.form_submit_button(
            "🚀 Generar Reels",
            type="primary",
            use_container_width=True,
        )

    # ─── Procesamiento ────────────────────────────────────────────────────────────

    if submitted:
        # Validaciones
        errors = []
        if not title.strip():
            errors.append("El **título** es obligatorio.")
        if not image:
            errors.append("La **foto del producto** es obligatoria.")
        if not languages:
            errors.append("Seleccioná al menos un **idioma**.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            # Construir el request multipart/form-data
            form_data = {
                "title": title.strip(),
                # El precio se omite intencionalmente (Curiosity Gap)
                "description": features.strip(),
            }

            # Solo enviar campos opcionales si tienen valor
            if rating > 0:
                form_data["rating"] = str(rating)
            if reviews_count > 0:
                form_data["reviews_count"] = str(reviews_count)
            if affiliate_url.strip():
                form_data["affiliate_url"] = affiliate_url.strip()

            files = {
                "image": (image.name, image.getvalue(), image.type),
            }

            params = {
                "languages": ",".join(languages),
            }

            # Enviar request al backend
            with st.spinner("⏳ Generando reels... esto puede tomar varios minutos"):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/pipeline/run",
                        data=form_data,
                        files=files,
                        params=params,
                        timeout=900,  # 15 min timeout para pipeline completo
                    )

                    if response.status_code == 200:
                        result = response.json()
                        status = result.get("status", "unknown")

                        if status == "success":
                            st.success(f"✅ {result.get('message', '¡Reels generados!')}")
                        else:
                            st.warning(f"⚠️ {result.get('message', 'Pipeline completado con errores.')}")

                        # Mostrar resumen de resultados
                        data = result.get("data", {})

                        col_a, col_b, col_c = st.columns(3)
                        col_a.metric("Clips IA", data.get("ai_clips_count", 0))
                        col_b.metric("Reels OK", len(data.get("reels", [])))
                        col_c.metric("Errores", len(data.get("errors", [])))

                        if data.get("ai_prompt_used"):
                            with st.expander("🎨 Prompt de Video IA"):
                                st.write(data["ai_prompt_used"])
                                if data.get("camera_movement"):
                                    st.caption(f"📹 Cámara: {data['camera_movement']}")

                        # Detalle por idioma
                        reels = data.get("reels", [])
                        if reels:
                            st.subheader("🎬 Reels Generados")
                            for reel in reels:
                                with st.expander(
                                    f"{'✅' if 'error' not in reel else '❌'} "
                                    f"{reel.get('language_name', reel.get('language', '?'))} "
                                    f"(Video #{reel.get('video_id', '?')})"
                                ):
                                    st.json(reel)

                        # Errores
                        errs = data.get("errors", [])
                        if errs:
                            st.subheader("❌ Errores")
                            for err in errs:
                                st.error(str(err))

                    else:
                        st.error(f"❌ Error HTTP {response.status_code}")
                        try:
                            detail = response.json().get("detail", response.text)
                            st.code(detail)
                        except Exception:
                            st.code(response.text[:500])

                except requests.exceptions.ConnectionError:
                    st.error(
                        "🔌 No se pudo conectar al backend. "
                        "¿Está corriendo el servidor FastAPI?\n\n"
                        "Ejecutá: `uvicorn app.main:app --reload`"
                    )
                except requests.exceptions.Timeout:
                    st.error(
                        "⏰ Timeout: el pipeline tardó demasiado. "
                        "Verificá los logs del servidor."
                    )
                except Exception as e:
                    st.error(f"💥 Error inesperado: {str(e)}")


with tab2:
    st.subheader("📦 Inventario de Productos")
    if st.button("🔄 Actualizar Lista"):
        pass
        
    try:
        res = requests.get(f"{API_BASE_URL}/products/", timeout=10)
        if res.status_code == 200:
            data = res.json()
            products = data.get("products", [])
            if not products:
                st.info("No hay productos registrados aún.")
            else:
                for p in products:
                    with st.expander(f"🛒 {p['title']} (ID: {p['id']}) - Estado: {p['status']}"):
                        if p.get('features'):
                            st.caption(f"📝 {p['features']}")
                        st.write(f"**Videos generados:** {p.get('videos_count', 0)}")
                        
                        with st.form(f"update_aff_{p['id']}"):
                            new_aff = st.text_input("Link de Afiliado", value=p.get("affiliate_url") or "")
                            if st.form_submit_button("Guardar Link"):
                                patch_res = requests.patch(
                                    f"{API_BASE_URL}/products/{p['id']}/affiliate-link",
                                    json={"affiliate_url": new_aff.strip()}
                                )
                                if patch_res.status_code == 200:
                                    st.success("Link actualizado. ¡Recargá la lista para ver los cambios!")
                                else:
                                    st.error("Error al actualizar el link.")
        else:
            st.error("No se pudo obtener la lista de productos.")
    except Exception as e:
        st.error(f"Error de conexión: {e}")

# ─── Sidebar: Estado del Servidor ─────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Estado")

    if st.button("🔄 Verificar conexión", use_container_width=True):
        try:
            r = requests.get(f"{API_BASE_URL}/", timeout=5)
            if r.status_code == 200:
                st.success("Backend conectado ✅")
                st.json(r.json())
            else:
                st.error(f"HTTP {r.status_code}")
        except Exception:
            st.error("Backend no disponible ❌")

    st.divider()
    st.caption(
        "**Cómo usar:**\n"
        "1. Iniciá el backend: `uvicorn app.main:app --reload`\n"
        "2. Completá el formulario y subí la foto\n"
        "3. Hacé clic en **Generar Reels**\n"
        "4. Esperá a que el pipeline termine"
    )
