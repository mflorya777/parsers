import json
import time
import os

import requests
import pandas as pd


BASE_URL = "https://api.hh.ru/vacancies"
AREAS_URL = "https://api.hh.ru/areas/113"
PROGRESS_FILE = "progress.json"
OUTPUT_FILE = "vacancies.xlsx"

EXCLUDE_KEYWORDS = [
    "senior", "lead", "тимлид", "руководитель", "архитектор",
    "ml", "machine learning", "data science", "аналитик",
    "java", "c++", "c#", "php", "javascript", "node", "go", "js",
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
    "геофизик", "Геофизик – интерпретатор данных ГИС",
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


def get_regions():
    """Получаем все регионы России (id и name)."""
    resp = requests.get(AREAS_URL)
    resp.raise_for_status()
    data = resp.json()
    regions = []

    # В API структура: 'areas' содержит регионы и подрегионы
    def extract_regions(area):
        if "areas" in area and area["areas"]:
            for sub in area["areas"]:
                extract_regions(sub)
        else:
            regions.append({"id": area["id"], "name": area["name"]})

    extract_regions(data)
    return regions


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


def get_vacancies_all_regions(text="python"):
    all_vacancies = []
    regions = get_regions()
    progress = load_progress()
    start_index = progress.get("area_index", 0)
    page = progress.get("page", 0)
    per_page = 100

    for idx in range(start_index, len(regions)):
        region = regions[idx]
        print(f"Парсим регион {region['name']} ({region['id']})")

        while True:
            params = {
                "text": text,
                "area": region["id"],
                "per_page": per_page,
                "page": page
            }

            try:
                resp = requests.get(BASE_URL, params=params, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 400:
                    print(f"Достигнут лимит API на странице {page} региона {region['name']}")
                    break
                if resp.status_code == 403:
                    print(f"Пропускаем регион {region['name']} ({region['id']}) — доступ запрещён")
                    break
                resp.raise_for_status()

                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    try:
                        if is_relevant(item):
                            vacancy_data = {
                                "name": item.get("name"),
                                "employer": item.get("employer", {}).get("name"),
                                "area": item.get("area", {}).get("name"),
                                "experience": item.get("experience", {}).get("name"),
                                "salary_from": item.get("salary", {}).get("from"),
                                "salary_to": item.get("salary", {}).get("to"),
                                "salary_currency": item.get("salary", {}).get("currency"),
                                "url": item.get("alternate_url")
                            }
                            all_vacancies.append(vacancy_data)
                    except Exception as e:
                        print(f"Ошибка обработки вакансии: {e}")
                        continue

            except requests.exceptions.RequestException as e:
                print(f"Ошибка запроса страницы {page} региона {region['name']}: {e}")
                break
            finally:
                save_progress({"area_index": idx, "page": page})

            page += 1
            time.sleep(0.5)

        page = 0

    # Записываем в Excel
    if all_vacancies:
        df = pd.DataFrame(all_vacancies)
        df.to_excel(OUTPUT_FILE, index=False)
        print(f"Сохранено {len(all_vacancies)} вакансий в {OUTPUT_FILE}")

    return all_vacancies


if __name__ == "__main__":
    get_vacancies_all_regions("python")
