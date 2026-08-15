import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path


GOODREADS_USER_ID = "192787859"
ANNUAL_GOAL = 50

README_PATH = Path("README.md")

LEFT_ANGLE = chr(60)
RIGHT_ANGLE = chr(62)

START_MARKER = (
    LEFT_ANGLE
    + "!-- READING-LOG:START --"
    + RIGHT_ANGLE
)

END_MARKER = (
    LEFT_ANGLE
    + "!-- READING-LOG:END --"
    + RIGHT_ANGLE
)

PRE_START = (
    LEFT_ANGLE
    + 'pre align="center"'
    + RIGHT_ANGLE
)

PRE_END = (
    LEFT_ANGLE
    + "/pre"
    + RIGHT_ANGLE
)

BASE_FEED_URL = (
    "https://www.goodreads.com/review/list_rss/"
    + GOODREADS_USER_ID
)


def get_text(item, tag):
    element = item.find(tag)

    if element is None:
        return ""

    if element.text is None:
        return ""

    return element.text.strip()


def find_first_text(item, tags):
    for tag in tags:
        value = get_text(item, tag)

        if value:
            return value

    return ""


def parse_number(value):
    cleaned_value = value.replace(",", "")
    match = re.search(r"\d+", cleaned_value)

    if match is None:
        return 0

    return int(match.group())


def parse_date(value):
    if not value:
        return None

    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d",
    ]

    for date_format in formats:
        try:
            parsed_date = datetime.strptime(
                value.strip(),
                date_format,
            )

            if parsed_date.tzinfo is not None:
                parsed_date = parsed_date.replace(
                    tzinfo=None
                )

            return parsed_date

        except ValueError:
            continue

    return None


def fetch_feed(shelf):
    
