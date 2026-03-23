# MAX Бот техподдержки — Velvet Mebel

Чат-бот для мессенджера MAX, техподдержка мебельного магазина Velvet Mebel (Wildberries). Выдаёт видеоинструкции по сборке (Комод, Обувница, Обувница с ящиком), через 24 часа спрашивает о результате; при «Да» — просьба отзыва на WB, при «Нет» — кнопка в чат техподдержки. Обращения пишутся в Google Таблицу.

## Возможности

- Приветствие и главное меню с inline-кнопками
- Выбор модели мебели (3 модели)
- Отправка видеоинструкции по сборке
- Автоматическое сообщение через 24 часа с вопросом о сборке
- Просьба оставить отзыв (при успешной сборке)
- Автоматическая запись всех обращений в Google Таблицу
- Локальная база данных SQLite
- **Веб-админка** (отдельный процесс): переписка с клиентами от имени бота, вкладки «Отзыв запрошен / получен», проблемы, быстрые ответы, статусы диалога. Документация MAX API: [POST /messages](https://dev.max.ru/docs-api/methods/POST/messages).

## Установка

### 1. Клонировать проект

```bash
git clone <repo_url>
cd evgesha20
```

### 2. Установить зависимости

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Тесты (разработка / CI)

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Каждый тест использует **отдельный временный файл SQLite** (не трогается `data/bot.db`).

### 3. Настроить переменные окружения

```bash
cp .env.example .env
```

Заполните `.env` файл (см. `.env.example`):
- `MAX_BOT_TOKEN` — токен бота из MasterBot в MAX
- `GOOGLE_SHEET_ID` — ID Google Таблицы
- `SUPPORT_CHAT_LINK` — ссылка на чат техподдержки в MAX (кнопки «Нет», «Написать в техподдержку» в меню)
- `MODEL_1_VIDEO`, `MODEL_2_VIDEO`, `MODEL_3_VIDEO` — ссылки на видеоинструкции
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` — вход в веб-админку (HTTP Basic). Без пароля админка не запускается (503).

### 4. Настроить Google Sheets

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com)
2. Включите Google Sheets API
3. Создайте Service Account и скачайте JSON ключ
4. Сохраните как `credentials.json` в корне проекта
5. Дайте доступ к Google Таблице email-у из service account

### 5. Запустить бота

```bash
python -m bot.main
```

На сервере нужны **два процесса**: бот и админка (общая SQLite `data/bot.db`, режим WAL).

### 6. Запустить веб-админку

Из корня проекта (тот же `.env`, что у бота):

```bash
python -m admin.main
# или явно:
uvicorn admin.main:app --host 0.0.0.0 --port 8000
```

Откройте в браузере `http://<сервер>:8000/` — появится запрос логина/пароля (значения из `ADMIN_USERNAME` / `ADMIN_PASSWORD`). **Закройте порт файрволом** от внешнего мира или поставьте reverse-proxy с HTTPS.

## Структура проекта

```
admin/
├── main.py              # FastAPI: API + раздача UI
└── templates/
    └── index.html       # Панель менеджера (Vue + Tailwind CDN)

bot/
├── main.py              # Точка входа бота
├── config.py            # Настройки из .env
├── texts.py             # ВСЕ тексты сообщений (редактировать тут!)
├── middlewares/
│   └── logging_mw.py    # Лог входящих сообщений в БД (для админки)
├── handlers/
│   ├── start.py         # Приветствие, /start
│   ├── instructions.py  # Выбор модели, видеоинструкции
│   ├── phone.py         # Номер телефона
│   └── feedback.py      # Ответы о сборке, просьба отзыва
├── keyboards/
│   └── inline.py        # Inline-клавиатуры
└── services/
    ├── database.py      # SQLite (users, requests, messages, templates)
    ├── scheduler.py     # Планировщик (отложенные сообщения)
    └── sheets.py        # Google Sheets интеграция

tests/                   # pytest: БД, админ-API, middleware, клавиатуры
pytest.ini
requirements-dev.txt     # pytest + pytest-asyncio (для тестов)
```

## Изменение текстов

Все тексты сообщений бота находятся в файле `bot/texts.py`. Для изменения просто отредактируйте нужную переменную и перезапустите бота.

## Деплой на VPS (systemd)

Файлы `deploy/maxbot.service` и `deploy/maxadmin.service` настроены под типовой VPS: **`User=root`**, каталог **`/root/VelvetMebel`**, venv **`/root/VelvetMebel/venv`**. Если проект в другом месте или под другим пользователем — отредактируйте `User`, `WorkingDirectory`, `ExecStart` и `EnvironmentFile` в обоих unit-файлах (или уже скопированных в `/etc/systemd/system/`).

Чтобы **бот и админка работали постоянно** (автозапуск после перезагрузки + перезапуск при падении):

```bash
sudo cp deploy/maxbot.service deploy/maxadmin.service /etc/systemd/system/
sudo nano /etc/systemd/system/maxbot.service
sudo nano /etc/systemd/system/maxadmin.service
sudo systemctl daemon-reload
sudo systemctl enable maxbot maxadmin
sudo systemctl start maxbot maxadmin
sudo systemctl status maxbot maxadmin
```

Порт админки задаётся в `.env` (`ADMIN_PORT`, по умолчанию 8000). Оба сервиса читают один `EnvironmentFile` с `ADMIN_PASSWORD`, `MAX_BOT_TOKEN` и остальным.
