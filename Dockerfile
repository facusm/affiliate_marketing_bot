FROM python:3.10-slim

# Instalar dependencias del sistema requeridas por MoviePy y OpenCV
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    imagemagick \
    fonts-liberation \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick security policy for MoviePy to allow TextClip
RUN sed -i '/<policy domain="path" rights="none" pattern="@\*"/d' /etc/ImageMagick-*/policy.xml || true

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Exponer el puerto de la API y de Streamlit (opcional aquí, se maneja en docker-compose)
EXPOSE 8000
EXPOSE 8501

# El comando por defecto será ejecutar la API (se sobreescribirá en docker-compose para el servicio ui)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
