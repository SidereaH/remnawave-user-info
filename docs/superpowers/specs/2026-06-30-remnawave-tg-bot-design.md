# Remnawave Telegram Bot — Design

**Дата:** 2026-06-30
**Стек:** Python 3.11+, aiogram 3, httpx, pydantic-settings

## Цель

Telegram-бот для администраторов Remnawave: быстрый поиск пользователя панели
по TG ID / email / TG username и управление им (вкл/выкл, продление, сброс
трафика, ревок подписки, детализация трафика). Доступ к боту ограничен
белым списком Telegram ID. Конфигурация — через `.env`.

## Ограничения и факты о Remnawave API

- База: `{REMNAWAVE_URL}/api`, авторизация `Authorization: Bearer {REMNAWAVE_TOKEN}`.
- Поиск по TG ID — нативный эндпоинт `GET /api/users/by-telegram-id/{telegramId}`
  (возвращает массив).
- Поиск по email — нативный `GET /api/users/by-email/{email}` (возвращает массив).
- **TG username отдельного поля не имеет.** Username хранится как `@username`
  где-то внутри поля `description`. Поиск — постраничный скан всех юзеров
  (`GET /api/users?size=&start=`) с проверкой `@username` как подстроки
  без учёта регистра.
- Точные пути actions-эндпоинтов (enable/disable/reset-traffic/revoke/usage)
  и форма ответов **сверяются с реальной панелью (swagger `/api/docs`) на этапе
  реализации**. Все они инкапсулированы в `RemnawaveClient`, поэтому правка
  пути — одна строка.

Ответы API оборачиваются в `{ "response": ... }` — клиент разворачивает.

## Структура проекта

```
kot/
├── bot.py                  # точка входа: Dispatcher, роутеры, polling
├── config.py               # pydantic-settings из .env
├── remnawave/
│   ├── __init__.py
│   ├── client.py           # async httpx-клиент ко всем эндпоинтам
│   └── models.py           # dataclass-обёртки ответа (RemnaUser и т.п.)
├── middlewares/
│   ├── __init__.py
│   └── access.py           # AccessMiddleware: фильтр по ALLOWED_ADMIN_IDS
├── handlers/
│   ├── __init__.py
│   ├── search.py           # приём текста, детект типа, поиск, выбор из списка
│   └── actions.py          # callback-кнопки действий + FSM продления
├── keyboards.py            # инлайн-клавиатуры карточки и подтверждений
├── formatting.py           # рендер карточки юзера и детализации трафика
├── states.py               # FSM StatesGroup для ввода даты продления
├── .env.example
├── requirements.txt
└── README.md
```

## Компоненты

### config.py
`Settings(BaseSettings)` с полями:
- `bot_token: str`
- `remnawave_url: str`
- `remnawave_token: str`
- `allowed_admin_ids: set[int]` (парсится из строки `"111,222"`)
- `users_page_size: int = 250`
- `request_timeout: int = 20`
- `log_level: str = "INFO"`

Невалидная/пустая обязательная переменная → падение на старте с понятной ошибкой.

### remnawave/client.py — `RemnawaveClient`
Async-обёртка над `httpx.AsyncClient` (один общий клиент, base_url, заголовок
авторизации, таймаут). Методы:
- `get_by_telegram_id(tg_id) -> list[RemnaUser]`
- `get_by_email(email) -> list[RemnaUser]`
- `search_by_description(substring) -> list[RemnaUser]` — постраничный скан
  с лимитом страниц (защита от бесконечного цикла), фильтр по подстроке без регистра.
- `get_user(uuid) -> RemnaUser`
- `enable_user(uuid)` / `disable_user(uuid)`
- `reset_traffic(uuid)`
- `revoke_subscription(uuid) -> RemnaUser` (новый subscription URL)
- `update_expire(uuid, expire_at: datetime) -> RemnaUser` (PATCH)
- `get_usage(uuid, ...) -> usage data` (детализация трафика)

Все методы ловят `httpx.HTTPStatusError` / таймауты и поднимают
`RemnawaveError` с человекочитаемым сообщением; хендлеры показывают его юзеру.

### middlewares/access.py — `AccessMiddleware`
`BaseMiddleware`, проверяет `event.from_user.id in settings.allowed_admin_ids`.
Не в списке → краткий отказ + лог `WARNING`, событие не пропускается дальше.

### handlers/search.py
Хендлер на любой текст. Детект типа:
1. email-регекс (`есть @ и домен с точкой`) → `get_by_email`
2. начинается с `@` → strip `@` → `search_by_description`
3. только цифры → `get_by_telegram_id`
4. иначе → `search_by_description`

- 0 совпадений → «не найдено».
- 1 совпадение → карточка.
- >1 → инлайн-кнопки выбора (username + email на кнопке), callback открывает карточку.

### handlers/actions.py
Callback-хендлеры для кнопок карточки. `callback_data` несёт `uuid` и действие
(используется фабрика `CallbackData`). Деструктивные действия (ревок, сброс
трафика) — двухшаговое подтверждение. Продление: кнопки `+30/+90/+180` сразу;
`Ввести дату` → FSM (`states.py`), бот ждёт дату `YYYY-MM-DD`, валидирует,
вызывает `update_expire`. После любого действия — перерисовка карточки
(edit_message) с актуальными данными.

### keyboards.py / formatting.py
Сборка инлайн-клавиатур и текста карточки (HTML parse_mode). Трафик в
человекочитаемых единицах (ГБ), даты в локальном формате, безлимит/0 — обработаны.

### states.py
`ExtendStates.waiting_for_date` для ввода произвольной даты продления.

## Поток данных

```
User text ─▶ AccessMiddleware ─▶ search handler ─▶ детект типа
   ─▶ RemnawaveClient.<метод> ─▶ list[RemnaUser]
   ─▶ 0 / 1 / N ─▶ formatting.render_card ─▶ message + inline keyboard
Callback ─▶ AccessMiddleware ─▶ actions handler ─▶ (confirm?) ─▶ client.<action>
   ─▶ refetch ─▶ edit карточки
```

## Обработка ошибок

- Сетевые/HTTP-ошибки API → `RemnawaveError` → юзеру «⚠️ Ошибка обращения к
  панели», детали в лог.
- Скан description ограничен числом страниц (по `total` из ответа + хард-кап),
  без бесконечных циклов.
- Невалидный ввод даты → подсказка формата, FSM не сбрасывается.
- Пустой/мусорный запрос → подсказка как искать.

## .env.example

```
BOT_TOKEN=
REMNAWAVE_URL=https://panel.example.com
REMNAWAVE_TOKEN=
ALLOWED_ADMIN_IDS=111111111,222222222
USERS_PAGE_SIZE=250
REQUEST_TIMEOUT=20
LOG_LEVEL=INFO
```

## Тестирование

- Юнит-тесты на: детект типа запроса, парсинг `ALLOWED_ADMIN_IDS`, форматирование
  карточки/трафика, фильтр description (подстрока без регистра).
- `RemnawaveClient` тестируется с замоканным httpx (respx или monkeypatch).
- Ручная проверка против реальной панели на этапе сверки эндпоинтов.

## Вне области (YAGNI)

- Создание/удаление юзеров, массовые операции.
- Webhooks (используем polling).
- БД/персистентное состояние (состояние только в callback_data и FSM-памяти).
- Мультиязычность (UI на русском).
```

