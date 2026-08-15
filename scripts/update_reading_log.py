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


@dataclass
class Book:
    title: str
    author: str
    pages: int
    rating: int
    read_at: Optional[datetime]
    link: str


def get_text(item: ET.Element, tag: str) -> str:
    element = item.find(tag)

    if element is None or element.text is None:
        return ""

    return element.text.strip()


def parse_number(value: str) -> int:
    match = re.search(r"\d+", value.replace(",", ""))

    if match is None:
        return 0

    return int(match.group())


def parse_date(value: str) -> Optional[datetime]:
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
            "User-Agent": "Mozilla/5.0 GitHub-Reading-Log/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def find_first_text(item: ET.Element, tags: list[str]) -> str:
    for tag in tags:
        value = get_text(item, tag)

        if value:
            return value

    return ""


def parse_pages(item: ET.Element) -> int:
    direct_value = find_first_text(
        item,
        [
            "book_num_pages",
            "num_pages",
            "book_pages",
        ],
    )

    pages = parse_number(direct_value)

    if pages:
        return pages

    description = get_text(item, "description")

    patterns = [
        r"num_pages[^0-9]{0,40}(\d+)",
        r"number of pages[^0-9]{0,40}(\d+)",
        r"pages[^0-9]{0,20}(\d+)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            description,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

    return 0


def parse_books(xml_data: bytes) -> listroot = ET.fromstring(xml_data)
    books: list[Book] = []

    for item in root.findall(".//item"):
        title = find_first_text(
            item,
            [
                "book_title",
                "title",
            ],
        )

        author = find_first_text(
            item,
            [
                "author_name",
                "book_author",
            ],
        )

        rating = parse_number(
            find_first_text(
                item,
                [
                    "user_rating",
                    "rating",
                ],
            )
        )

        read_at = parse_date(
            find_first_text(
                item,
                [
                    "user_read_at",
                    "read_at",
                ],
            )
        )

        link = get_text(item, "link")

        books.append(
            Book(
                title=title or "untitled",
                author=author or "unknown author",
                pages=parse_pages(item),
                rating=rating,
                read_at=read_at,
                link=link,
            )
        )

    return books


def shorten(value: str, maximum: int = 20) -> str:
    cleaned = html.unescape(value).strip()

    if len(cleaned) <= maximum:
        return cleaned

    return cleaned[: maximum - 1].rstrip() + "…"


def box_row(label: str, value: str) -> str:
    content = f"  {label:<17}{value}"
    return f"│{content:<40}│"


def progress_bar(completed: int, goal: int) -> str:
    units = 10

    if goal <= 0:
        filled = 0
    else:
        filled = round(min(completed / goal, 1) * units)

    symbols = ["■"] * filled + ["□"] * (units - filled)

    return " ".join(symbols)


def choose_favourite(
    books: list[Book],
) -> Optionalrated_books = [
        book
        for book in books
        if book.rating > 0
    ]

    if not rated_books:
        return None

    def sorting_key(book: Book) -> tuple[int, str]:
        read_date = (
            book.read_at.isoformat()
            if book.read_at is not None
            else ""
        )

        return book.rating, read_date

    return max(rated_books, key=sorting_key)


def current_book_text(books: list[Book]) -> str:
    if not books:
        return "between books"

    if len(books) == 1:
        return shorten(books[0].title)

    first_book = shorten(books[0].title, 16)
    additional_books = len(books) - 1

    return f"{first_book} +{additional_books}"


def build_reading_log(
    read_books: list[Book],
    current_books: list[Book],
) -> str:
    current_year = datetime.now().year

    yearly_books = [
        book
        for book in read_books
        if book.read_at is not None
        and book.read_at.year == current_year
    ]

    yearly_books.sort(
        key=lambda book: book.read_at or datetime.min,
        reverse=True,
    )

    books_read = len(yearly_books)
    pages_read = sum(
        book.pages
        for book in yearly_books
        if book.pages > 0
    )

    favourite = choose_favourite(yearly_books)

    favourite_title = (
        shorten(favourite.title)
        if favourite is not None
        else "not rated yet"
    )

    current_title = current_book_text(current_books)

    rows = [
        "╭────────────────────────────────────────╮",
        "│              READING LOG               │",
        "│                                        │",
        box_row("year", str(current_year)),
        box_row("books read", str(books_read)),
        box_row(
            "pages read",
            f"{pages_read:,}" if pages_read else "unavailable",
        ),
        box_row("favourite", favourite_title),
        box_row("currently", current_title),
        "│                                        │",
        box_row(
            "progress",
            progress_bar(books_read, ANNUAL_GOAL),
        ),
        box_row(
            "goal",
            f"{books_read} / {ANNUAL_GOAL} books",
        ),
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


def update_readme(new_section: str) -> bool:
    if not README_PATH.exists():
        raise FileNotFoundError("README.md was not found.")

    readme = README_PATH.read_text(encoding="utf-8")

    pattern = re.compile(
        re.escape(START_MARKER)
        + r".*?"
        + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if pattern.search(readme) is None:
        raise RuntimeError(
            "READING-LOG markers were not found in README.md."
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


def main() -> int:
    try:
        print("Fetching Goodreads read shelf...")
        read_xml = fetch_feed("read")

        print("Fetching Goodreads currently-reading shelf...")
        current_xml = fetch_feed("currently-reading")

        read_books = parse_books(read_xml)
        current_books = parse_books(current_xml)

        print(f"Read shelf entries found: {len(read_books)}")
        print(
            "Currently-reading entries found: "
            f"{len(current_books)}"
        )

        new_section = build_reading_log(
            read_books,
            current_books,
        )

        changed = update_readme(new_section)

        if changed:
            print("README.md reading log updated.")
        else:
            print("README.md already contains the latest data.")

        return 0

    except Exception as error:
        print(
            f"Reading log update failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
