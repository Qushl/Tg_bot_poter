# Telegram-бот «Потеряшки»

Бот на Python 3.11+, aiogram 3.x и SQLite для публикации потерянных и найденных вещей.

## Запуск

1. Создайте виртуальное окружение и установите зависимости:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Скопируйте `.env.example` в `.env` и заполните переменные:

   ```env
   BOT_TOKEN=т...
   PROXY_URL=
   ```

   Пустое значение включает прямое подключение. Для работы через прокси укажите
   реальный адрес SOCKS5, например `socks5://user:pass@host:port`.

3. Запустите бота:

   ```bash
   python main.py
   ```

Файл базы `lost_found.db` и таблицы `users`, `items` создаются автоматически при первом запуске. Устанавливать сервер базы данных не нужно.
