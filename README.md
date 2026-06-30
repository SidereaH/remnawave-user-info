# Remnawave Telegram Bot

Бот для админов: поиск и управление пользователями Remnawave.

## Возможности
- Поиск по Telegram ID, email или `@username` (username ищется в `description`).
- Карточка юзера: статус, трафик, срок, контакты, UUID, подписка.
- Действия: вкл/выкл, продление (+1/+30/+90/+180 или дата в формате ДД.ММ.ГГ),
  сброс трафика, сброс HWID-устройств, ревок подписки, статистика потребления
  за период (неделя / 30 / 60 дней).
- Дата окончания подписки в европейском формате ДД.ММ.ГГ ЧЧ:ММ.
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

## Запуск в Docker
```bash
cp .env.example .env   # заполнить значения
docker compose up -d   # собрать образ и запустить в фоне
docker compose logs -f # смотреть логи
docker compose down    # остановить
```
Бот работает на long polling — входящие порты не нужны. Переменные читаются из
`.env` через `env_file`. Логи ограничены ротацией (3 файла по 10 МБ).

## Тесты
```bash
python -m pytest -v
```

## Заметка по API
Рассчитано на Remnawave **2.8.0** (сверено с официальной OpenAPI-спекой).
Учтённые отличия 2.8.0 от 2.7.x:
- использованный трафик переехал в `userTraffic.usedTrafficBytes`
  (клиент поддерживает и старый верхнеуровневый вариант);
- `POST /api/users/{uuid}/actions/revoke` теперь требует тело
  (`{"revokeOnlyPasswords": false}`);
- статистика: основной `GET /api/bandwidth-stats/users/{uuid}?start=&end=&topNodesLimit=10`,
  запасной при 404 — `GET /api/bandwidth-stats/users/{uuid}/legacy`.

Все пути собраны в `remnawave/client.py`. При расхождениях сверяйся со swagger
`{REMNAWAVE_URL}/api/docs`.
