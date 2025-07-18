#!/usr/bin/env python3
"""
build_feed.py ─ собирает RSS-ленту для раздела
«Свежее и актуальное» Яндекса из RSS Tilda.
"""

import datetime
import pathlib
import xml.etree.ElementTree as ET

import feedparser
import requests
import bs4
import pytz

# ─── НАСТРОЙКИ ─────────────────────────────────────────────────────────────
SOURCE_RSS   = "https://artsoft.club/rss-feed-650873130041.xml"
OUTPUT_FILE  = pathlib.Path("yandex.xml")
TIMEZONE     = pytz.timezone("Europe/Moscow")
MIN_TEXT_LEN = 200           # миним. длина <yandex:full-text>
MAX_ITEMS    = 1000
# ───────────────────────────────────────────────────────────────────────────


def strip_html(raw_html: str) -> str:
    """Удаляем все теги, возвращаем чистый текст одной строкой."""
    return bs4.BeautifulSoup(raw_html, "lxml").get_text(" ", strip=True)


def extract_full_text(entry) -> str:
    """
    Возвращает ≥ MIN_TEXT_LEN символов чистого текста
    (turbo:content → content:encoded → description → HTML-страница).
    """
    # 1. turbo:content  ─ feedparser кладёт как turbo_content или 'turbo:content'
    if entry.get("turbo_content"):
        txt = strip_html(entry["turbo_content"])
    elif entry.get("turbo:content"):
        txt = strip_html(entry["turbo:content"])

    # 2. content:encoded / <content>
    elif entry.get("content"):
        txt = strip_html(entry.content[0].value)

    # 3. description / summary
    else:
        txt = strip_html(entry.get("summary", ""))

    if len(txt) >= MIN_TEXT_LEN:
        return txt

    # 4. fallback – скачиваем саму страницу
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0)"}
        resp = requests.get(entry.link, headers=headers, timeout=20)
        resp.raise_for_status()
        txt = strip_html(resp.text)
    except requests.RequestException:
        txt = ""

    return txt


def build_feed() -> None:
    feed = feedparser.parse(SOURCE_RSS)
    if feed.bozo:
        raise RuntimeError(f"Не смог прочитать исходный RSS: {feed.bozo_exception}")

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
        pub   = entry.get("published", "").strip() or now.strftime("%a, %d %b %Y %H:%M:%S %z")

        # обязательные поля
        if not (title and link and pub):
            continue

        full_text = extract_full_text(entry)
        if len(full_text) < MIN_TEXT_LEN:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text  = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link
        ET.SubElement(item, "pubDate").text = pub
        ET.SubElement(item, "{http://news.yandex.ru}full-text").text = full_text

        added += 1

    ET.ElementTree(rss).write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Готово: записано {added} items → {OUTPUT_FILE.absolute()}")


if __name__ == "__main__":
    build_feed()
