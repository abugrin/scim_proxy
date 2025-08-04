# SCIM Proxy Service

Прокси-сервис для модернизации старых SCIM API, добавляющий поддержку современных фильтров и операций согласно RFC 7644.

## Проблема

Существующий SCIM API 2.0 сервис не поддерживает:
- Фильтрацию запросов (`?filter=userName eq "abc"`)
- Сложные логические операции в фильтрах
- Современные PATCH операции

## Решение

SCIM Proxy Service принимает полные SCIM 2.0 запросы с фильтрами и преобразует их для работы со старым API:

```
Клиент → SCIM Proxy → Старый SCIM API
GET /Users?filter=userName eq "abc" → GET /Users → фильтрация результата
```

## Ключевые возможности

- ✅ **Полная поддержка SCIM 2.0 фильтров** - все операторы и логические выражения
- ✅ **Правильная пагинация с фильтрацией** - корректная работа при загрузке более 100 записей
- ✅ **Высокая производительность** - async/await, connection pooling, кэширование
- ✅ **Проксирование аутентификации** - прозрачная передача всех заголовков
- ✅ **PATCH операции** - add, replace, remove согласно RFC
- ✅ **TLS/SSL поддержка** - Nginx прокси с современной SSL конфигурацией
- ✅ **Безопасность** - Rate limiting, security headers, HSTS
- ✅ **Docker развертывание** - простой запуск через docker-compose
- ✅ **Расширяемость** - модульная архитектура для добавления новых функций

## Архитектура

### С TLS (рекомендуется)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SCIM Client   │───▶│  Nginx (TLS)    │───▶│   SCIM Proxy    │───▶│  Legacy SCIM    │
│                 │    │                 │    │                 │    │      API        │
│ Modern filters  │    │ SSL Termination │    │ Filter Parser   │    │ Simple queries  │
│ PATCH ops       │    │ Rate Limiting   │    │ Filter Engine   │    │ Basic CRUD      │
│ Full RFC 7644   │    │ Security Headers│    │ Auth Proxy      │    │ Limited SCIM    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
     HTTPS                   HTTP                   HTTP                   HTTP/HTTPS
    Port 443                Port 80               Port 8000              Upstream API
```

### Без TLS (только для разработки)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   SCIM Client   │───▶│   SCIM Proxy    │───▶│  Legacy SCIM    │
│                 │    │                 │    │      API        │
│ Modern filters  │    │ Filter Parser   │    │ Simple queries  │
│ PATCH ops       │    │ Filter Engine   │    │ Basic CRUD      │
│ Full RFC 7644   │    │ Auth Proxy      │    │ Limited SCIM    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
     HTTP                    HTTP                   HTTP/HTTPS
    Port 8000              Port 8000              Upstream API
```

## Поддерживаемые фильтры

### Простые операторы
```
userName eq "user@example.com"
active eq true
displayName co "John"
name.givenName sw "J"
emails pr
```

### Логические операции
```
active eq true and name.givenName sw "A"
(active eq true) or (active eq false)
not (userName co "test")
```

### Сложные атрибуты (массивы)
```
emails[type eq "work"].value co "@company.com"
phoneNumbers[type eq "mobile"] pr
emails[primary eq true and type eq "work"].value
```

## Быстрый старт

Создайте папку `scim-proxy` и загрузите в нее `docker-compose.yml`
Скопировать папку с конфигурацией NGINX `/nginx/nginx.conf` в корень проекта
Создать папку `cert` и положить в нее сертификаты `certificate_full_chain.pem` и `private_key.pem`
Создать файл `.env` с настройками вашего scim-proxy (см. `.env.example`)

### Итоговая структура

scim_proxy/
├── .env
├── docker-compose.yml
├── nginx/
│   ├── nginx.conf
├── cert/
│   ├── certificate_full_chain.pem
│   ├── private_key.pem


### Вариант 1: Использование готового образа из Docker Hub

```bash
# Создайте .env файл с настройками
cat > .env << EOF
UPSTREAM_BASE_URL=https://your-legacy-scim-api.com/scim/v2
UPSTREAM_TIMEOUT=30
PROXY_HOST=0.0.0.0
PROXY_PORT=8000
EOF

# Запуск контейнера
docker run -d \
  --name scim-proxy \
  -p 8000:8000 \
  --env-file .env \
  abugrin/scim-proxy:latest
```

### Вариант 2: Клонирование и настройка

```bash
git clone <repository>
cd scim_proxy
cp .env.example .env
# Отредактируйте .env файл с настройками вашего upstream API
```

### 3. Запуск через Docker Compose

```bash
# Получение последней версии образов
docker compose pull

# Запуск с TLS (рекомендуется)
docker compose up -d

# Или только SCIM Proxy без TLS
docker compose up scim-proxy -d

# Просмотр логов
docker compose logs -f scim-proxy

# Остановка сервисов
docker compose down
```

### 3. Проверка работы

```bash
# Health check (HTTPS с TLS)
curl https://localhost/health -k

# Health check (HTTP, только если без TLS)
curl http://localhost:8000/health

# Тест фильтрации (HTTPS)
curl "https://localhost/Users?filter=active eq true" -k \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Конфигурация

### Основные переменные окружения

```bash
# Upstream SCIM API
UPSTREAM_BASE_URL=https://your-legacy-scim-api.com/scim/v2
UPSTREAM_TIMEOUT=30

# Прокси настройки
PROXY_HOST=0.0.0.0
PROXY_PORT=8000
PROXY_WORKERS=4

# Производительность
CACHE_TTL=300
CACHE_MAX_SIZE=1000
MAX_FILTER_COMPLEXITY=50

# Пагинация с фильтрацией
MAX_FILTER_FETCH_SIZE=2000
FILTER_FETCH_MULTIPLIER=20
```

### Настройки пагинации с фильтрацией

- `MAX_FILTER_FETCH_SIZE` - максимальное количество записей для загрузки при фильтрации (по умолчанию: 2000)
- `FILTER_FETCH_MULTIPLIER` - множитель для определения количества загружаемых записей (по умолчанию: 20)

При запросе N записей с фильтром система загружает `min(N * FILTER_FETCH_MULTIPLIER, MAX_FILTER_FETCH_SIZE)` записей для обеспечения корректных результатов.

## API Endpoints

### Users Resource

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/v2/Users` | Список пользователей с поддержкой фильтров |
| GET | `/v2/Users/{id}` | Получение пользователя по ID |
| POST | `/v2/Users` | Создание пользователя |
| PUT | `/v2/Users/{id}` | Полное обновление пользователя |
| PATCH | `/v2/Users/{id}` | Частичное обновление пользователя |
| DELETE | `/v2/Users/{id}` | Удаление пользователя |

### Groups Resource

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/v2/Groups` | Список групп с поддержкой фильтров |
| GET | `/v2/Groups/{id}` | Получение группы по ID |
| POST | `/v2/Groups` | Создание группы |
| PUT | `/v2/Groups/{id}` | Полное обновление группы |
| PATCH | `/v2/Groups/{id}` | Частичное обновление группы |
| DELETE | `/v2/Groups/{id}` | Удаление группы |

### SCIM Discovery

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/v2/ServiceProviderConfig` | Конфигурация SCIM сервера |
| GET | `/v2/ResourceTypes` | Список поддерживаемых типов ресурсов |
| GET | `/v2/ResourceTypes/User` | Информация о User ресурсе |
| GET | `/v2/ResourceTypes/Group` | Информация о Group ресурсе |

### Обратная совместимость

Все endpoints также доступны без префикса `/v2` для обратной совместимости:
- `/Users`, `/Groups`, `/ServiceProviderConfig`, `/ResourceTypes`

### Поддерживаемые параметры запроса

- `filter` - SCIM фильтр
- `attributes` - Список возвращаемых атрибутов
- `excludedAttributes` - Список исключаемых атрибутов
- `sortBy` - Атрибут для сортировки
- `sortOrder` - Порядок сортировки (ascending/descending)
- `startIndex` - Индекс начала пагинации
- `count` - Количество записей на странице

## Примеры использования

### Фильтрация пользователей

```bash
# Активные пользователи
curl "http://localhost:8000/v2/Users?filter=active eq true"

# Пользователи с рабочим email
curl "http://localhost:8000/v2/Users?filter=emails[type eq \"work\"] pr"

# Сложный фильтр
curl "http://localhost:8000/v2/Users?filter=active eq true and name.givenName sw \"A\""

# Поиск конкретного пользователя
curl "http://localhost:8000/v2/Users?filter=displayName eq \"Vasili Pupkin\""
```

### Фильтрация групп

```bash
# Все группы
curl "http://localhost:8000/v2/Groups"

# Группы с определенным именем
curl "http://localhost:8000/v2/Groups?filter=displayName eq \"Administrators\""

# Группы содержащие определенного пользователя
curl "http://localhost:8000/v2/Groups?filter=members[value eq \"user123\"]"

# Группы с именем содержащим "Admin"
curl "http://localhost:8000/v2/Groups?filter=displayName co \"Admin\""
```

### SCIM Discovery

```bash
# Получение конфигурации сервера
curl "http://localhost:8000/v2/ServiceProviderConfig"

# Список поддерживаемых ресурсов
curl "http://localhost:8000/v2/ResourceTypes"

# Информация о User ресурсе
curl "http://localhost:8000/v2/ResourceTypes/User"
```

### PATCH операции

```bash
# Обновление пользователя
curl -X PATCH http://localhost:8000/v2/Users/123 \
  -H "Content-Type: application/scim+json" \
  -d '{
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
    "Operations": [
      {
        "op": "replace",
        "path": "active",
        "value": false
      }
    ]
  }'

# Добавление члена в группу
curl -X PATCH http://localhost:8000/v2/Groups/456 \
  -H "Content-Type: application/scim+json" \
  -d '{
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
    "Operations": [
      {
        "op": "add",
        "path": "members",
        "value": [
          {
            "value": "user123",
            "type": "User",
            "display": "John Doe"
          }
        ]
      }
    ]
  }'
```

## Производительность

### Бенчмарки

- **Простые фильтры**: < 50ms время ответа
- **Сложные фильтры**: < 100ms время ответа
- **Пропускная способность**: > 1000 RPS
- **Использование памяти**: < 512MB на воркер

### Оптимизации

- Async/await для неблокирующих операций
- Connection pooling для HTTP клиентов
- Кэширование ответов upstream API
- Ранний выход в логических операциях
- Ленивая оценка выражений

## Разработка

### Структура проекта

```
scim_proxy/
├── app/                    # Основное приложение
│   ├── models/            # Pydantic модели
│   ├── services/          # Бизнес-логика
│   ├── routers/           # FastAPI роутеры
│   └── utils/             # Утилиты
├── tests/                 # Тесты
├── docker-compose.yml     # Docker Compose конфигурация
└── Dockerfile            # Docker образ
```

### Запуск для разработки

```bash
# Установка зависимостей
pip install -r requirements-dev.txt

# Запуск в режиме разработки
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Запуск тестов
pytest tests/ -v

# Линтинг
flake8 app/
black app/
```

## Мониторинг

### Health Check

```bash
curl http://localhost:8000/health
```

### Метрики

- Время ответа по endpoint'ам
- Количество запросов к upstream API
- Эффективность кэша
- Ошибки фильтрации

### Логирование

Структурированные JSON логи с полями:
- `timestamp` - время события
- `level` - уровень логирования
- `message` - сообщение
- `request_id` - ID запроса
- `user_id` - ID пользователя (если доступен)
- `filter` - примененный фильтр
- `upstream_time` - время запроса к upstream API

## Безопасность

- Проксирование всех заголовков аутентификации
- Валидация входящих данных
- Ограничение сложности фильтров
- Защита от injection атак в фильтрах
- HTTPS поддержка

## Ограничения

- Максимальная сложность фильтра: 50 операций
- Максимальный размер ответа: 10MB
- Таймаут upstream запросов: 30 секунд
- TTL кэша: 5 минут

## Roadmap

### v1.0 - Базовая функциональность ✅
- [x] Архитектурный план
- [x] Парсер SCIM фильтров
- [x] Движок фильтрации
- [x] HTTP прокси сервис
- [x] Docker контейнеризация

### v1.1 - PATCH операции ✅
- [x] Парсинг PATCH операций
- [x] Применение операций add/replace/remove
- [x] Валидация изменений

### v1.2 - Производственная готовность ✅
- [x] TLS/SSL поддержка с Nginx
- [x] Security headers и rate limiting
- [x] Структурированное логирование
- [x] Docker Hub образ
- [x] Документация API

### v2.0 - Расширенные возможности ✅
- [x] Groups resource поддержка
- [x] SCIM Discovery endpoints
- [x] Универсальный фильтр движок
- [x] Современные Docker Compose команды

### v2.1 - Улучшения пагинации ✅
- [x] Правильная пагинация с фильтрацией
- [x] Загрузка всех данных для корректной фильтрации
- [x] Оптимизация производительности при больших объемах данных
- [x] Тестирование и документация улучшений

### v2.2 - Будущие улучшения
- [ ] Bulk operations
- [ ] WebHooks для синхронизации
- [ ] Admin UI
- [ ] Метрики и мониторинг

## Поддержка

- **Документация**: [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- **Issues**: GitHub Issues для багов и feature requests
- **Discussions**: GitHub Discussions для вопросов

## Лицензия

MIT License - см. [LICENSE](LICENSE) файл для деталей.