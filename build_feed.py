#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_feed.py — собирает RSS-ленту «Свежее и актуальное» из RSS Tilda.
Адаптировано под переезд на домен атомсофт.рф (IDN) и стабильный GUID.
"""

import datetime
import pathlib
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import feedparser
import requests
import bs4
import pytz
from email.utils import format_datetime

# ─── НАСТРОЙКИ ─────────────────────────────────────────────────────────────
# Безопаснее указывать IDN в punycode, HTTP-клиенты гарантированно дружат с ASCII.
SOURCE_RSS   = "https://xn--80ayfbodep.xn--p1ai/rss-feed-650873130041.xml"
OUTPUT_FILE  = pathlib.Path("yandex.xml")
TIMEZONE     = pytz.timezone("Europe/Moscow")
MIN_TEXT_LEN = 200           # миним. длина <yandex:full-text>
MAX_ITEMS    = 1000
SITE_URL     = "https://атомсофт.рф/"   # можно оставить в Unicode — в XML это ок
BRAND_TITLE  = "Атомсофт — свежее и актуальное"
BRAND_DESC   = "Последние статьи Атомсофт"
UA           = "Mozilla/5.0 (compatible; AtomsoftRSS/1.0; +https://атомсофт.рф/)"
# ───────────────────────────────────────────────────────────────────────────


def strip_html(raw_html: str) -> str:
    """Удаляем все теги, возвращаем чистый текст одной строкой."""
    return bs4.BeautifulSoup(raw_html or "", "lxml").get_text(" ", strip=True)


def format_rfc2822(dt: datetime.datetime) -> str:
    """RFC 2822/5322 для lastBuildDate/pubDate."""
    if dt.tzinfo is None:
        dt = TIMEZONE.localize(dt)
    return format_datetime(dt)


def extract_full_text(entry) -> str:
    """
    Возвращает ≥ MIN_TEXT_LEN символов чистого текста
    (turbo:content → content:encoded → description → HTML-страница).
    """
    # 1) turbo:content (feedparser кладёт как turbo_content или 'turbo:content')
    if entry.get("turbo_content"):
        txt = strip_html(entry["turbo_content"])
    elif entry.get("turbo:content"):
        txt = strip_html(entry["turbo:content"])

    # 2) content:encoded / <content>
    elif entry.get("content"):
        txt = strip_html(entry.content[0].value)

    # 3) description / summary
    else:
        txt = strip_html(entry.get("summary", ""))

    if len(txt) >= MIN_TEXT_LEN:
        return txt

    # 4) fallback — качаем саму страницу
    try:
        headers = {"User-Agent": UA}
        resp = requests.get(entry.link, headers=headers, timeout=20)
        resp.raise_for_status()
        txt = strip_html(resp.text)
    except requests.RequestException:
        txt = ""

    return txt


def pick_pub_date(entry, now_dt: datetime.datetime) -> str:
    """Нормализуем pubDate к RFC форматам, стараясь взять дату из исходного RSS."""
    if entry.get("published_parsed"):
        # published_parsed — это time.struct_time
        ts = time.mktime(entry.published_parsed)
        dt = datetime.datetime.fromtimestamp(ts, tz=TIMEZONE)
        return format_rfc2822(dt)
    if entry.get("updated_parsed"):
        ts = time.mktime(entry.updated_parsed)
        dt = datetime.datetime.fromtimestamp(ts, tz=TIMEZONE)
        return format_rfc2822(dt)
    # как fallback берём то, что пришло строкой
    if entry.get("published"):
        return entry.get("published")
    return format_rfc2822(now_dt)


def make_guid(entry) -> str:
    """
    Делаем стабильный GUID, независимый от домена.
    Приоритет:
    1) GUID/ID из исходного RSS (если есть) — самый стабильный вариант.
    2) Доменно-независимая форма на основе path?query#fragment.
    """
    eid = entry.get("id") or entry.get("guid")
    if eid:
        return eid

    link = entry.get("link", "")
    if link:
        p = urlparse(link)
        raw = p.path or "/"
        if p.query:
            raw += "?" + p.query
        if p.fragment:
            raw += "#" + p.fragment
        return f"atomsoft:{raw}"

    # крайний случай — хэш от заголовка + даты публикации
    base = (entry.get("title", "") + "|" + entry.get("published", "")).strip() or "atomsoft:item"
    return f"atomsoft:{abs(hash(base))}"


def build_feed() -> None:
    # Парсим источник
    feed = feedparser.parse(SOURCE_RSS)
    if feed.bozo:
        raise RuntimeError(f"Не смог прочитать исходный RSS: {feed.bozo_exception}")

    # Подготавливаем XML
    ET.register_namespace("yandex", "http://news.yandex.ru")
    rss     = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text       = BRAND_TITLE
    ET.SubElement(channel, "link").text        = SITE_URL
    ET.SubElement(channel, "description").text = BRAND_DESC
    ET.SubElement(channel, "language").text    = "ru"

    now = datetime.datetime.now(TIMEZONE)
    ET.SubElement(channel, "lastBuildDate").text = format_rfc2822(now)

    added = 0
    for entry in feed.entries[:MAX_ITEMS]:
        title = entry.get("title", "").strip()
        link  = entry.get("link", "").strip()
        pub   = pick_pub_date(entry, now)

        # обязательные поля
        if not (title and link and pub):
            continue

        full_text = extract_full_text(entry)
        if len(full_text) < MIN_TEXT_LEN:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text  = link
        ET.SubElement(item, "guid", isPermaLink="false").text = make_guid(entry)
        ET.SubElement(item, "pubDate").text = pub
        ET.SubElement(item, "{http://news.yandex.ru}full-text").text = full_text

        added += 1

    ET.ElementTree(rss).write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Готово: записано {added} items → {OUTPUT_FILE.absolute()}")


if __name__ == "__main__":
    build_feed()

