import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

GOODREADS_USER_ID = "192787859"
README_PATH = Path("README.md")

LEFT_ANGLE = chr(60)
RIGHT_ANGLE = chr(62)

START_MARKER = LEFT_ANGLE + "!-- READING-LOG:START --" + RIGHT_ANGLE
END_MARKER = LEFT_ANGLE + "!-- READING-LOG:END --" + RIGHT_ANGLE

PRE_START = LEFT_ANGLE + 'pre align="center"' + RIGHT_ANGLE
PRE_END = LEFT_ANGLE + "/pre" + RIGHT_ANGLE

BASE_FEED_URL = (
    "https://www.goodreads.com/review/list_rss/" + GOODREADS_USER_ID
)


def get_text(item, tag):
    element = item.find(tag)

    if element is None or element.text is None:
        return ""

    return element.text.strip()


def find_first_text(item, tags):
    for tag in tags:
        value = get_text(item, tag)

        if value:
            return value

    return ""


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
                parsed_date = parsed_date.replace(tzinfo=None)

            return parsed_date

        except ValueError:
            continue

    return None


def fetch_read_shelf():
    query = urllib.parse.urlencode(
        {
            "shelf": "read",
            "sort": "date_read",
            "order": "d",
            "per_page": "200",
        }
    )

    feed_url = BASE_FEED_URL + "?" + query

    print("Requesting Goodreads read shelf...")

    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 GitHub-Reading-Log/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_books(xml_data):
    root = ET.fromstring(xml_data)

    books = []

    for item in root.findall(".//item"):
        title = find_first_text(
            item,
            ["book_title", "title"],
        )

        read_date_text = find_first_text(
            item,
            ["user_read_at", "read_at"],
        )

        books.append(
            {
                "title": title or "untitled",
                "read_at": parse_date(read_date_text),
            }
        )

    return books


def count_books_this_year(books):
    current_year = datetime.now().year

    return sum(
        1
        for book in books
        if book["read_at"] is not None
        and book["read_at"].year == current_year
    )


def build_reading_log(books):
    books_this_year = count_books_this_year(books)
    books_all_time = len(books)

    reading_log = [
        START_MARKER,
        PRE_START,
        "READING LOG",
        "────────────────────────",
        f"this year       {books_this_year} books",
        f"all time        {books_all_time} books",
        PRE_END,
        END_MARKER,
    ]

    return "\n".join(reading_log)


def update_readme(new_section):
    if not README_PATH.exists():
        raise FileNotFoundError(
            "README.md was not found."
        )

    readme = README_PATH.read_text(
        encoding="utf-8"
    )

    pattern = re.compile(
        re.escape(START_MARKER)
        + r".*?"
        + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if pattern.search(readme) is None:
        raise RuntimeError(
            "The READING-LOG markers were not found in README.md."
        )

    updated_readme = pattern.sub(
        lambda match: new_section,
        readme,
        count=1,
    )

    if updated_readme == readme:
        return False

    README_PATH.write_text(
        updated_readme,
        encoding="utf-8",
    )

    return True


def main():
    try:
        print("Fetching Goodreads read shelf...")

        read_xml = fetch_read_shelf()
        read_books = parse_books(read_xml)

        print(
            "Read shelf entries found: "
            + str(len(read_books))
        )

        books_this_year = count_books_this_year(
            read_books
        )

        print(
            "Books read this year: "
            + str(books_this_year)
        )

        print(
            "Books read all time: "
            + str(len(read_books))
        )

        changed = update_readme(
            build_reading_log(read_books)
        )

        if changed:
            print("README.md reading log updated.")
        else:
            print(
                "README.md already contains "
                "the latest reading data."
            )

        return 0

    except Exception as error:
        print(
            "Reading log update failed: "
            + str(error),
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
