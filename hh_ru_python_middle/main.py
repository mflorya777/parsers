import json
import time
import os

import requests


BASE_URL = "https://api.hh.ru/vacancies"
PROGRESS_FILE = "progress.json"

EXCLUDE_KEYWORDS = [
    "senior", "lead", "тимлид", "руководитель", "архитектор",
    "ml", "machine learning", "data science", "аналитик",
    "java", "c++", "c#", "php", "javascript", "node", "go",
    "ruby", "scala", "kotlin", "swift", "QA", "тестирование",
    "тестированию", "devops", "qa", "технической поддержки",
    "junior", "Специалист поддержки", "второй линии",
    "Системный администратор", "ai", "ai-developer",
    "Помощник системного администратора", "системного администратора",
    "Data Scientist", "тестировщик", "frontend", "Заместитель директора",
    "информационной безопасности", "Трейдер", "Старший администратор",
    "администратор", "админ", "Сетевой администратор", "директор",
    "стажер", "стажёр", "data scientist", "Инженер-сборщик", "трейдер",
    "Инженер-сборщик FPV дронов", "Marketing Data Analyst", "Математик-программист",
    "геофизик", "Геофизик – интерпретатор данных ГИС"
]

ALLOWED_EXPERIENCE = {"between1And3"}
MIN_SALARY = 140_000


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"area": 113, "page": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def is_relevant(vacancy: dict) -> bool:
    """
    Фильтруем вакансии: Python, 1-3 года опыта, ЗП >= 140к.
    """
    requirement = vacancy.get("snippet", {}).get("requirement") or ""
    responsibility = vacancy.get("snippet", {}).get("responsibility") or ""
    text = f"{vacancy.get('name', '')} {requirement} {responsibility}".lower()

    # проверка Python
    if "python" not in text:
        return False

    # исключаем лишние ключевые слова
    for word in EXCLUDE_KEYWORDS:
        if word in text:
            return False

    # проверка опыта
    exp_id = vacancy.get("experience", {}).get("id")
    if exp_id not in ALLOWED_EXPERIENCE:
        return False

    # проверка зарплаты
    salary = vacancy.get("salary")
    if not salary:  # если зарплата не указана — отбрасываем
        return False
    if salary.get("currency") != "RUR":  # оставляем только рубли
        return False
    if salary.get("from") is None:  # иногда "from" отсутствует
        return False
    if salary["from"] < MIN_SALARY:
        return False
    if salary["from"] >= MIN_SALARY:
        return True

    return True


def get_vacancies(text="python", area=113):
    vacancies = []
    progress = load_progress()
    page = progress.get("page", 0)
    per_page = 100

    while True:
        params = {
            "text": text,
            "area": area,
            "per_page": per_page,
            "page": page
        }
        resp = requests.get(BASE_URL, params=params)
        if resp.status_code == 400:  # достигли лимита страниц
            print(f"Достигнут лимит API на странице {page}")
            break
        resp.raise_for_status()

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if is_relevant(item):
                vacancies.append(item)

        page += 1
        save_progress({"area": area, "page": page})
        time.sleep(0.5)  # пауза, чтобы не перегружать сервер

    return vacancies


if __name__ == "__main__":
    vacancies = get_vacancies("python", area=113)
    for v in vacancies:
        area_name = v["area"]["name"] if "area" in v else "Неизвестно"
        print(f"{v['name']} | {v['employer']['name']} | {area_name} | {v['alternate_url']}")
