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
    print("Requesting Goodreads read shelf")

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
        read_date_text = find_first_text(
            item,
            ["user_read_at", "read_at"],
        )
        books.append(
            {
                "title": find_first_text(item, ["book_title", "title"]),
                "read_at": parse_date(read_date_text),
            }
        )

    return books


def count_this_year(books):
    current_year = datetime.now().year
    total = 0

    for book in books:
        read_date = book["read_at"]
        if read_date is not None and read_date.year == current_year:
            total = total + 1

    return total


def box_row(label, value):
    content = "  " + label.ljust(17) + value
    return "|" + content.ljust(40) + "|"


def build_reading_log(books):
    current_year = datetime.now().year
    this_year_total = count_this_year(books)
    all_time_total = len(books)

    rows = [
        "+----------------------------------------+",
        "|              READING LOG               |",
        "|                                        |",
        box_row(str(current_year), str(this_year_total) + " books"),
        box_row("all time", str(all_time_total) + " books"),
        "|                                        |",
        "+----------------------------------------+",
    ]

    return "\n".join(
        [START_MARKER, PRE_START] + rows + [PRE_END, END_MARKER]
    )


def update_readme(new_section):
    if not README_PATH.exists():
        raise FileNotFoundError("README.md was not found")

    readme = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        flags=re.DOTALL,
    )

    if pattern.search(readme) is None:
        raise RuntimeError("READING-LOG markers were not found in README.md")

    updated_readme = pattern.sub(lambda match: new_section, readme, count=1)

    if updated_readme == readme:
        return False

    README_PATH.write_text(updated_readme, encoding="utf-8")
    return True


def main():
    try:
        read_xml = fetch_read_shelf()
        books = parse_books(read_xml)
        print("Read shelf entries returned: " + str(len(books)))

        changed = update_readme(build_reading_log(books))
        if changed:
            print("README.md reading log updated")
        else:
            print("README.md already contains the latest reading data")
        return 0
    except Exception as error:
        print("Reading log update failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
