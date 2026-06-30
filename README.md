# Remnawave Telegram Bot

Бот для админов: поиск и управление пользователями Remnawave.

## Возможности
- Поиск по Telegram ID, email или `@username` (username ищется в `description`).
- Карточка юзера: статус, трафик, срок, контакты, UUID, подписка.
- Действия: вкл/выкл, продление (+30/+90/+180 или дата), сброс трафика,
  ревок подписки, детализация трафика по узлам.
- Доступ только для Telegram ID из белого списка.

## Установка
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить значения
python bot.py
```

## Переменные .env
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | токен бота от @BotFather |
| `REMNAWAVE_URL` | адрес панели, напр. `https://panel.example.com` |
| `REMNAWAVE_TOKEN` | API-токен Remnawave (Bearer) |
| `ALLOWED_ADMIN_IDS` | TG ID админов через запятую |
| `USERS_PAGE_SIZE` | размер страницы при поиске по описанию (по умолч. 250) |
| `REQUEST_TIMEOUT` | таймаут запросов к API, сек (по умолч. 20) |
| `LOG_LEVEL` | уровень логов (по умолч. INFO) |

## Тесты
```bash
python -m pytest -v
```

## Заметка по API
Пути actions/usage-эндпоинтов заданы под текущий Remnawave в
`remnawave/client.py`. Если панель отвечает 404 на действие или «📊 Детализация
недоступна», сверь путь со swagger `{REMNAWAVE_URL}/api/docs` и поправь в клиенте.
