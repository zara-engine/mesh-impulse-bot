"""
Сетевой слой бота «МЭШ.Импульс».

⚠️ ДЕМО-ВЕРСИЯ.
В этой публичной версии функции возвращают пример данных (mock) той же
структуры, что и реальный сервер. Рабочие эндпоинты API, заголовки
запросов и механизм авторизации в открытый репозиторий НЕ включены —
проект носит образовательный, исследовательский характер и не должен
использоваться для доступа к чужим персональным данным.

Полная рабочая реализация хранится в приватной версии проекта.
"""

# Примерные данные, имитирующие ответ сервера
MOCK_PROFILE = {
    "profile": {"id": "000000"},
    "children": [{"contingent_guid": "demo-person-id"}],
}

MOCK_EVENTS = {
    "response": [
        {
            "source": "PLAN",
            "subject_name": "Алгебра",
            "room_number": "404",
            "room_name": "Каб. математики",
            "start_at": "2026-06-05T09:00:00",
            "finish_at": "2026-06-05T09:45:00",
            "marks": [{
                "value": "2", "is_point": False, "is_exam": False,
                "control_form_name": "Самостоятельная работа",
                "date": "2026-06-03", "comment": "Пересдать тему §12",
            }],
        },
        {
            "source": "PLAN",
            "subject_name": "История",
            "room_number": "210",
            "room_name": "",
            "start_at": "2026-06-05T10:00:00",
            "finish_at": "2026-06-05T10:45:00",
            "marks": [{
                "value": "НВ", "is_point": False, "is_exam": False,
                "control_form_name": "Доклад",
                "date": "2026-06-04", "comment": "",
            }],
        },
        {
            "source": "PLAN",
            "subject_name": "Физика",
            "room_number": "315",
            "room_name": "Лаборатория",
            "start_at": "2026-06-05T11:00:00",
            "finish_at": "2026-06-05T11:45:00",
            "marks": [{
                "value": "5", "is_point": False, "is_exam": False,
                "control_form_name": "Ответ на уроке",
                "date": "2026-06-05", "comment": "",
            }],
        },
    ]
}


async def fetch_profile(raw_token: str):
    """
    Проверка токена и получение профиля ученика.
    DEMO: возвращает фиктивный профиль. Возврат None означал бы
    ошибку авторизации (в рабочей версии — ответ сервера != 200).
    """
    return MOCK_PROFILE


async def fetch_events(token, profile_id, person_id, begin_date, end_date):
    """
    Получение событий календаря (расписание и оценки) за период.
    DEMO: возвращает пример структуры вместо реального запроса к API.
    """
    return MOCK_EVENTS