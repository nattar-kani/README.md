from __future__ import annotations

import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


GOODREADS_USER_ID = "192787859"
ANNUAL_GOAL = 50
README_PATH = Path("README.md")

START_MARKER = "<!-- READING-LOG:START -->"
END_MARKER = "<!-- READING-LOG:END -->"

BASE_FEED_URL = (
    f"https://www.goodreads.com/review/list_rss/{GOODREADS_USER_ID}"
)

USER_AGENT = (
    "Mozilla/5.0 GitHub-Profile-Reading-Log/1.0 "
    "(https://github.com/nattar-kani)"
)


@dataclass
class Book:
    title: str
    author: str
    pages: int
    rating: int
    read_at: Optional[datetime]
    link: str


def text_of(item: ET.Element, tag: str) -> str:
    element = item.find(tag)

    if element is None or element.text is None:
        return ""

    return element.text.strip()


def parse_integer(value: str) -> int:
    match = re.search(r"\d+", value.replace(",", ""))

    if not match:
        return 0

    return int(match.group())


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None

    formats = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d",
        "%a %b %d %H:%M:%S %z %Y",
ate_format in formats:
        try:
            return datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue

    return None


def fetch_feed(shelf: str) -> bytes:
    query = urllib.parse.urlencode(
        {
            "shelf": shelf,
            "sort": "date_read",
            "order": "d",
            "per_page": "200",
        }
    )

    url = f"{BASE_FEED_URL}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/xml;q=0.9,"
                "text/xml;q=0.8"
            ),
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_books(xml_data: bytes) -> listroot = ET.fromstring(xml_data)
    books: list[Book] = []

    for item in root.findall(".//item"):
        title = (
            text_of(item, "book_title")
            or text_of(item, "title")
            or "untitled"
        )

        author = (
            text_of(item, "author_name")
            or text_of(item, "book_author")
            or "unknown author"
        )

        pages = parse_integer(
            text_of(item, "book")
            or text_of(item, "num_pages")
            or text_of(item, "book_num_pages")
        )

        if pages == 0:
            description = text_of(item, "description")

            page_match = re.search(
                r"(?:num_pages|pages)[^0-9]{0,30}(\d+)",
                description,
                flags=re.IGNORECASE,
            )

            if page_match:
                pages = int(page_match.group(1))

        rating = parse_integer(
            text_of(item, "user_rating")
            or text_of(item, "rating")
        )

        read_at = parse_date(
            text_of(item, "user_read_at")
            or text_of(item, "read_at")
        )

        link = (
            text_of(item, "link")
            or "https://www.goodreads.com/"
        )

        books.append(
            Book(
                title=title,
                author=author,
                pages=pages,
                rating=rating,
                read_at=read_at,
                link=link,
            )
        )

    return books


def shorten(value: str, maximum: int = 20) -> str:
    value = html.unescape(value).strip()

    if len(value) <= maximum:
        return value

    return value[: maximum - 1].rstrip() + "…"


def pad_row(label: str, value: str) -> str:
    content = f"  {label:<17}{value}"
    return f"│{content:<40}│"


def progress_bar(completed: int, goal: int, units: int = 12) -> str:
    if goal <= 0:
        return "▱ " * units

    ratio = min(completed / goal, 1)
    filled = round(ratio * units)

    symbols = ["▰"] * filled + ["▱"] * (units - filled)

    return " ".join(symbols)


def select_favourite(books: list[Book]) -> Optional[Book]:
    rated_books = [book for book in booksing > 0]

    if not rated_books:
        return None

    minimum_date = datetime.min.replace(tzinfo=None)

    def sort_key(book: Book):
        read_at = book.read_at

        if read_at and read_at.tzinfo is not None:
            read_at = read_at.replace(tzinfo=None)

        return (
            book.rating,
            read_at or minimum_date,
        )

    return max(rated_books, key=sort_key)


def currently_reading_text(books: list[Book]) -> str:
    if not books:
        return "between books"

    if len(books) == 1:
        return shorten(books[0].title)

    first_title = shorten(books[0].title, 17)
    remaining = len(books) - 1

    return f"{first_title} +{remaining}"


def build_reading_log(
    read_books: list[Book],
    current_books: list[Book],
) -> str:
    year = datetime.now().year

    books_this_year = [
        book
        for book in read_books
        if book.read_at is not None
        and book.read_at.year == year
    ]

    books_this_year.sort(
        key=lambda book: book.read_at or datetime.min,
        reverse=True,
    )

    number_read = len(books_this_year)

    known_pages = [
        book.pages
        for book in books_this_year
        if book.pages > 0
    ]

    total_pages = sum(known_pages)
    favourite = select_favourite(books_this_year)

    favourite_title = (
        shorten(favourite.title)
        if favourite
        else "not rated yet"
    )

    current_title = currently_reading_text(current_books)
    bar = progress_bar(number_read, ANNUAL_GOAL)

    rows = [
        "╭────────────────────────────────────────╮",
        "│              READING LOG               │",
        "│                                        │",
        pad_row("year", str(year)),
        pad_row("books read", str(number_read)),
        pad_row(
            "pages read",
            f"{total_pages:,}" if known_pages else "unavailable",
        ),
        pad_row("favourite", favourite_title),
        pad_row("currently", current_title),
        "│                                        │",
        pad_row("progress", bar),
        pad_row("goal", f"{number_read} / {ANNUAL_GOAL} books"),
        "│                                        │",
        "╰────────────────────────────────────────╯",
    ]

    return "\n".join(
        [
            START_MARKER,
            '<pre align="center">',
            *rows,
            "</pre>",
            END_MARKER,
        ]
    )


def update_readme(new_section: str) -> None:
    if not README_PATH.exists():
        raise FileNotFoundError("README.md was not found.")

    readme = README_PATH.read_text(encoding="utf-8")

    pattern = re.compile(
        re.escape(START_MARKER)
        + r".*?"
        + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if not pattern.search(readme):
        raise RuntimeError(
            "Reading log markers were not found in README.md."
        )

    updated_readme = pattern.sub(
        lambda _: new_section,
        readme,
        count=1,
    )

    README_PATH.write_text(updated_readme, encoding="utf-8")


def main() -> int:
    try:
        read_feed = fetch_feed("read")
        current_feed = fetch_feed("currently-reading")

        read_books = parse_books(read_feed)
        current_books = parse_books(current_feed)

        reading_log = build_reading_log(
            read_books=read_books,
            current_books=current_books,
        )

        update_readme(reading_log)

        print(
            "Reading log updated successfully. "
            f"Read shelf entries: {len(read_books)}. "
            f"Currently-reading entries: {len(current_books)}."
        )

        return 0

    except Exception as error:
        print(f"Reading log update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
`
