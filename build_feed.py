#!/usr/bin/env python3
"""
Собирает Yandex‑совместимый RSS:
* читает исходный RSS от Tilda (или любой другой),
* гарантирует наличие <pubDate>,
* вытаскивает ≥200 символов чистого текста в <yandex:full-text>,
* сохраняет в yandex.xml (тот же путь, что публикует GitHub Pages).
"""
import datetime, pytz, html
import xml.etree.ElementTree as ET
import feedparser, requests, bs4, re, pathlib

# 1. НАСТРОЙКИ --------------------------------------------------------------
SOURCE_RSS = "https://artsoft.club/rss-feed-650873130041.xml"   # ← правильный адрес
OUTPUT_FILE = pathlib.Path("yandex.xml")
TIMEZONE    = pytz.timezone("Europe/Moscow")
MIN_TEXT    = 200
MAX_ITEMS   = 1000

# 2. ЧИТАЕМ ИСХОДНЫЙ RSS ----------------------------------------------------
feed = feedparser.parse(SOURCE_RSS)
if feed.bozo:
    raise SystemExit(f"Не смог прочитать {SOURCE_RSS}: {feed.bozo_exception}")

# 3. ГОТОВИМ XML‑КАРКАС ------------------------------------------------------
ET.register_namespace("yandex", "http://news.yandex.ru")
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")
ET.SubElement(channel, "title").text       = "ArtSoft Blog — свежее и актуальное"
ET.SubElement(channel, "link").text        = "https://artsoft.club"
ET.SubElement(channel, "description").text = "Последние статьи ArtSoft"
ET.SubElement(channel, "language").text    = "ru"
now = datetime.datetime.now(TIMEZONE)
ET.SubElement(channel, "lastBuildDate").text = now.strftime("%a, %d %b %Y %H:%M:%S %z")

# 4. ОБРАБАТЫВАЕМ КАЖДЫЙ ЭЛЕМЕНТ -------------------------------------------
def clean_html(text):
    return bs4.BeautifulSoup(text, "lxml").get_text(" ", strip=True)

for entry in feed.entries[:MAX_ITEMS]:
    title = entry.title
    link  = entry.link

    # ---- pubDate ----
    if "published" in entry:
        pub_iso = entry.published
    else:
        pub_iso = now.strftime("%a, %d %b %Y %H:%M:%S %z")   # fallback: сейчас
    # ---- full text ----
    full = ""
    if "content" in entry:                     # у Tilda это <turbo:content>
        full = clean_html(entry.content[0].value)
    elif "summary" in entry:
        full = clean_html(entry.summary)
    if len(full) < MIN_TEXT:                   # пытаемся добрать с сайта
        try:
            html_page = requests.get(link, timeout=10).text
            full = clean_html(html_pag)
try:
    html_page = requests.get(link, timeout=10).text
    full = clean_html(html_page)
except requests.RequestException:
    # если страница недоступна – не падаем, а просто пропускаем
    pass
