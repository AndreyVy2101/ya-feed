#!/usr/bin/env python3
"""
build_feed.py
─────────────
Собирает RSS‑ленту для раздела «Свежее и актуальное» Яндекса.

Что делает скрипт:
1. Скачивает исходный RSS, который генерирует Tilda.
2. Для каждого <item>:
   • копирует title, link, guid;
   • проставляет/проверяет pubDate;
   • вытаскивает ≥200 символов текста и кладёт в <yandex:full-text>.
3. Сохраняет результат в файл yandex.xml (его отдает GitHub Pages).

Запускать можно вручную: `python build_feed.py`
или через GitHub Actions (см. .github/workflows/rss.yml).

Требуются библиотеки: feedparser, requests, beautifulsoup4, lxml, pytz
"""

import datetime
import pathlib
import xml.etree.ElementTree as ET

import feedparser
import requests
import bs4
import pytz

# ───────────────────────────────────────────────
# НАСТРОЙКИ

SOURCE_RSS   = "https://artsoft.club/rss-feed-650873130041.xml"
OUTPUT_FILE  = pathlib.Path("yandex.xml")
TIMEZONE     = pytz.timezone("Europe/Moscow")
MIN_TEXT_LEN = 200          # минимальный объём <yandex:full-text>
MAX_ITEMS    = 1000         # максимум элементов в итоговой ленте

# ───────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

def strip_html(html_text: str) -> str:
    """Удаляем HTML‑теги, возвращаем чистый текст."""
    soup = bs4.BeautifulSoup(html_text, "lxml")
    return soup.get_text(" ", strip=True)

def extract_full_text(entry) -> str:
    """
    Пытаемся получить >200 символов текста:
      1) из <content> или <summary>;
      2) если мало — скачиваем саму страницу и чистим HTML.
    """
    # 1. turbo:content / content:encoded
    if entry.get("content"):
        txt = strip_html(entry.content[0].value)
    else:
        txt = strip_html(entry.get("summary", ""))

    if len(txt) >= MIN_TEXT_LEN:
        return txt

    # 2. fallback — берём текст со страницы
    try:
        resp = requests.get(entry.link, timeout=20)
        resp.raise_for_status()
        txt = strip_html(resp.text)
    except requests.RequestException:
        txt = ""

    return txt

# ───────────────────────────────────────────────
# СБОРКА ЛЕНТЫ

def build_feed() -> None:
    feed = feedparser.parse(SOURCE_RSS)
    if feed.bozo:
        raise RuntimeError(f"Не смог разобрать исходный RSS: {feed.bozo_exception}")

    # Заготовка каналa
    ET.register_namespace("yandex", "http://news.yandex.ru")
    rss     = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text       = "ArtSoft Blog — свежее и актуальное"
    ET.SubElement(channel, "link").text        = "https://artsoft.club/"
    ET.SubElement(channel, "description").text = "Последние статьи ArtSoft"
    ET.SubElement(channel, "language").text    = "ru"

    now = datetime.datetime.now(TIMEZONE)
    ET.SubElement(channel, "lastBuildDate").text = now.strftime("%a, %d %b %Y %H:%M:%S %z")

    added = 0
    for entry in feed.entries[:MAX_ITEMS]:
        title = entry.get("title", "").strip()
        link  = entry.get("link", "").strip()
        pub   = entry.get("published", "").strip()

        # пропускаем элементы без обязательных полей
        if not (title and link):
            continue

        # если pubDate отсутствует — ставим текущее время
        if not pub:
            pub = now.strftime("%a, %d %b %Y %H:%M:%S %z")

        full_text = extract_full_text(entry)
        if len(full_text) < MIN_TEXT_LEN:
            # пропускаем слишком короткие статьи — Яндекс будет ругаться «0 слов»
            continue

        # формируем <item>
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text  = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link
        ET.SubElement(item, "pubDate").text = pub
        ET.SubElement(item, "{http://news.yandex.ru}full-text").text = full_text

        added += 1

    # сохраняем
    tree = ET.ElementTree(rss)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    print(f"Готово: записано {added} items → {OUTPUT_FILE.absolute()}")

# ───────────────────────────────────────────────
# ТОЧКА ВХОДА

if __name__ == "__main__":
    build_feed()
