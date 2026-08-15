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
START_MARKER = LEFT_ANGLE + "!-- READING-LOG:START --" + RIGHT_ANGLE
END_MARKER = LEFT_ANGLE + "!-- READING-LOG:END --" + RIGHT_ANGLE
PRE_START = LEFT_ANGLE + 'pre align="center"' + RIGHT_ANGLE
PRE_END = LEFT_ANGLE + "/pre" + RIGHT_ANGLE
BASE_FEED_URL = "https://www.goodreads.com/review/list_rss/" + GOODREADS_USER_ID


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


def parse_number(value):
    match = re.search(r"\d+", value.replace(",", ""))
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
            parsed_date = datetime.strptime(value.strip(), date_format)
            if parsed_date.tzinfo is not None:
                parsed_date = parsed_date.replace(tzinfo=None)
            return parsed_date
        except ValueError:
            continue
    return None


def fetch_feed(shelf):
    query = urllib.parse.urlencode(
        {
            "shelf": shelf,
            "sort": "date_read",
            "order": "d",
            "per_page": "200",
        }
    )
    feed_url = BASE_FEED_URL + "?" + query
    print("Requesting Goodreads shelf: " + shelf)
    request = urllib.request.Request(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 GitHub-Reading-Log/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_pages(item):
    direct_value = find_first_text(
        item,
        ["book_num_pages", "num_pages", "book_pages"],
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
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 0


def parse_books(xml_data):
    root = ET.fromstring(xml_data)
    books = []

    for item in root.findall(".//item"):
        title = find_first_text(item, ["book_title", "title"])
        author = find_first_text(item, ["author_name", "book_author"])
        rating_text = find_first_text(item, ["user_rating", "rating"])
        read_date_text = find_first_text(item, ["user_read_at", "read_at"])

        books.append(
            {
                "title": title or "untitled",
                "author": author or "unknown author",
                "pages": parse_pages(item),
                "rating": parse_number(rating_text),
                "read_at": parse_date(read_date_text),
                "link": get_text(item, "link"),
            }
        )
    return books


def shorten(value, maximum=20):
    cleaned = html.unescape(value).strip()
    shortened = cleaned[:maximum]
    if shortened != cleaned:
        shortened = shortened.rstrip() + "..."
    return shortened


def box_row(label, value):
    content = "  " + label.ljust(17) + value
    return "|" + content.ljust(40) + "|"


def progress_bar(completed, goal):
    units = 10
    safe_goal = goal or 1
    filled = round(min(completed / safe_goal, 1) * units)
    empty = units - filled
    return " ".join((["#"] * filled) + (["."] * empty))


def choose_favourite(books):
    rated_books = []
    for book in books:
        if book["rating"]:
            rated_books.append(book)

    if not rated_books:
        return None

    def sorting_key(book):
        return book["rating"], book["read_at"] or datetime.min

    return max(rated_books, key=sorting_key)


def current_book_text(books):
    if not books:
        return "between books"

    first_title = shorten(books[0]["title"], 18)
    additional_books = len(books) - 1
    if additional_books:
        return first_title + " +" + str(additional_books)
    return first_title


def books_from_current_year(books):
    current_year = datetime.now().year
    yearly_books = []
    for book in books:
        read_date = book["read_at"]
        if read_date is None:
            continue
        if read_date.year == current_year:
            yearly_books.append(book)

    yearly_books.sort(
        key=lambda book: book["read_at"] or datetime.min,
        reverse=True,
    )
    return yearly_books


def calculate_pages(books):
    total_pages = 0
    for book in books:
        if book["pages"]:
            total_pages += book["pages"]
    return total_pages


def build_reading_log(read_books, current_books):
    current_year = datetime.now().year
    yearly_books = books_from_current_year(read_books)
    books_read = len(yearly_books)
    pages_read = calculate_pages(yearly_books)
    favourite = choose_favourite(yearly_books)

    if favourite is None:
        favourite_title = "not rated yet"
    else:
        favourite_title = shorten(favourite["title"], 20)

    current_title = current_book_text(current_books)
    pages_text = format(pages_read, ",") if pages_read else "unavailable"

    rows = [
        "+----------------------------------------+",
        "|              READING LOG               |",
        "|                                        |",
        box_row("year", str(current_year)),
        box_row("books read", str(books_read)),
        box_row("pages read", pages_text),
        box_row("favourite", favourite_title),
        box_row("currently", current_title),
        "|                                        |",
        box_row("progress", progress_bar(books_read, ANNUAL_GOAL)),
        box_row("goal", str(books_read) + " / " + str(ANNUAL_GOAL) + " books"),
        "|                                        |",
        "+----------------------------------------+",
    ]

    return "\n".join([START_MARKER, PRE_START] + rows + [PRE_END, END_MARKER])


def update_readme(new_section):
    if not README_PATH.exists():
        raise FileNotFoundError("README.md was not found.")

    readme = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if pattern.search(readme) is None:
        raise RuntimeError("The READING-LOG markers were not found in README.md.")

    updated_readme = pattern.sub(lambda match: new_section, readme, count=1)
    if updated_readme == readme:
        return False

    README_PATH.write_text(updated_readme, encoding="utf-8")
    return True


def main():
    try:
        print("Fetching Goodreads read shelf...")
        read_xml = fetch_feed("read")
        print("Fetching Goodreads currently-reading shelf...")
        current_xml = fetch_feed("currently-reading")

        read_books = parse_books(read_xml)
        current_books = parse_books(current_xml)
        print("Read shelf entries found: " + str(len(read_books)))
        print("Currently-reading entries found: " + str(len(current_books)))

        changed = update_readme(build_reading_log(read_books, current_books))
        if changed:
            print("README.md reading log updated.")
        else:
            print("README.md already contains the latest reading data.")
        return 0
    except Exception as error:
        print("Reading log update failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
