# VEGA AI Assistant

A voice-controlled AI assistant for Windows that automates daily laptop tasks, powered by Google Gemini AI.

## Architecture

VEGA has been refactored into a modular, extensible structure:
- **Core Engine:** Handles Wake Word (Porcupine), Speech I/O (SAPI), and Conversation (Gemini 2.5 Flash with memory).
- **Commands:** A plugin-based command registry that loads modular command classes (web search, wikipedia, apps, system controls, etc).
- **Utilities & Config:** Handles robust settings parsing (`.env`) and comprehensive logging (`logs/vega.log`).

## Setup

1. **Clone the repository**
2. **Install requirements:** `pip install -r requirements.txt`
3. **Set up `.env`:** Copy `.env.example` to `.env` and fill in your API keys:
   - `GOOGLE_AI_API_KEY` (Gemini AI)
   - `PICOVOICE_ACCESS_KEY` (Hey Vega wake word)
   - `OPENWEATHER_API_KEY` (Weather)
   - `GNEWS_API_KEY` (News headlines)
   - Gmail App Password for email commands.
4. **Run VEGA:** `python main.py`

## Features

- Context-aware conversation with Google Gemini
- System Control (volume, brightness, screenshot, sleep, lock, etc.)
- Dynamic Application Launching (Notepad, Calculator, VS Code, Browser etc.)
- Task automation (Web Search, Wikipedia, Weather, News, YouTube)
- WhatsApp desktop automation and Email sending.