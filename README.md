# IOL Cauciones Bot 🚀

Este proyecto es un bot de automatización financiera desarrollado en **Python** que monitorea en tiempo real las tasas de **Cauciones en Pesos** de la plataforma InvertirOnline (IOL).

El bot está diseñado para correr 24/7 en una **Raspberry Pi** mediante **Docker**, enviando alertas personalizadas a **Telegram** cuando la Tasa Nominal Anual (TNA) alcanza umbrales específicos (40%, 50%, 60%, etc.).

## ✨ Características

- **Monitoreo Automático:** Consulta la API oficial de IOL cada 5 minutos durante el horario de mercado (11:00 - 17:00 hs).
- **Alertas Inteligentes:** Notifica vía Telegram solo cuando se supera un nuevo umbral, evitando el spam de mensajes repetidos.
- **Comandos Interactivos:** Permite consultar la tasa en cualquier momento enviando `/tasa` al bot de Telegram.
- **Infraestructura Robusta:** Empaquetado en un contenedor Docker con políticas de reinicio automático.
- **Eficiencia Energética:** El script entra en modo de bajo consumo fuera del horario de mercado.

## 🛠️ Tecnologías utilizadas

- **Lenguaje:** Python 3.11
- **Librerías:** `requests`, `python-dotenv`
- **Infraestructura:** Docker & Docker Compose
- **Hardware:** Raspberry Pi (compatible con cualquier servidor Linux)
- **API:** InvertirOnline API (OAuth2 Authentication)

## 🚀 Instalación y Uso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/iol-cauciones-bot.git
   cd iol-cauciones-bot
   ```

2. **Configurar variables de entorno:** Crea un archivo `.env` en la raíz del proyecto:
   ```
   IOL_USERNAME=tu_usuario_iol
   IOL_PASSWORD=tu_password_iol
   TELEGRAM_TOKEN=tu_bot_token
   TELEGRAM_CHAT_ID=tu_chat_id
   ```

3. **Desplegar con Docker:**
   ```bash
   docker compose up -d --build
   ```

## 🤖 Comandos de Telegram

- `/tasa`: Devuelve la TNA actual de la caución a 1 día.
- `/status`: Verifica si el bot y el contenedor están operativos.

## ⚠️ Notas de Seguridad

Este proyecto utiliza un archivo `.env` para manejar credenciales sensibles. Nunca subas el archivo `.env` a un repositorio público. El archivo `.gitignore` ya está configurado para excluirlo.

---

### Un último consejo de seguridad

Antes de hacer tu primer `git commit`, asegurate de crear un archivo llamado `.gitignore` (con el punto adelante) y escribí esto adentro:

```text
.env
__pycache__/
*.pyc
```