# Plan de Modificación: Webhook Multilingüe (6 Cuentas, 1 Token)

## Objetivo
Adaptar el bot para que pueda gestionar 6 cuentas de Instagram (una por idioma) utilizando una única aplicación de Meta y un único Token de Acceso (System User Token), respondiendo a los comentarios desde la cuenta correcta.

## Modificaciones Requeridas

### 1. Archivo `.env`
Mantener el webhook y token únicos, pero expandir los IDs de las cuentas:

```env
# Meta Graph API & Webhooks
META_VERIFY_TOKEN=tu_token_secreto_unico
META_ACCESS_TOKEN=tu_system_user_token_unico

# IDs de las 6 cuentas de Instagram
INSTAGRAM_ACCOUNT_ID_ES=111111111
INSTAGRAM_ACCOUNT_ID_EN=222222222
INSTAGRAM_ACCOUNT_ID_PT=333333333
INSTAGRAM_ACCOUNT_ID_DE=444444444
INSTAGRAM_ACCOUNT_ID_FR=555555555
INSTAGRAM_ACCOUNT_ID_IT=666666666
```

### 2. Archivo `app/api/webhook.py`
Se deben realizar 3 ajustes para que el enrutamiento sea dinámico:

**A. Capturar el ID de la cuenta receptora:**
En la ruta `POST /webhook` (aprox línea 176), cuando Meta envía el payload JSON, extraer el ID de la cuenta que recibió el comentario:
```python
ig_account_id_entrante = entry.get("id")
```

**B. Pasar el ID a la función asíncrona:**
Modificar la llamada a `process_instagram_comment` (aprox línea 188) para que reciba este nuevo parámetro:
```python
background_tasks.add_task(process_instagram_comment, comment_text, comment_id, ig_account_id_entrante)
```
*Nota: También hay que actualizar la firma de la función `process_instagram_comment` para que acepte este tercer parámetro.*

**C. Construir la URL de Meta de forma dinámica:**
Dentro de `process_instagram_comment` (aprox línea 127), reemplazar la variable global por el ID dinámico:
```python
url = f"https://graph.facebook.com/v19.0/{ig_account_id_entrante}/messages"
```

## ¿Por qué funciona esto?
Al enviar la petición HTTP POST a esta URL dinámica usando el `META_ACCESS_TOKEN` maestro, Meta verifica que el token tiene permisos de administrador sobre la aplicación que gestiona todas esas cuentas, autorizando el envío del Mensaje Directo (DM) exactamente desde la cuenta (`ig_account_id_entrante`) que originó la interacción.
