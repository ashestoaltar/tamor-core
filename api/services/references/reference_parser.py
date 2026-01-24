# api/services/references/reference_parser.py
"""
Robust scripture reference parser.

Handles many common formats for Bible references including:
- Full names: "Genesis 1:1"
- Abbreviations: "Gen 1:1", "Gen. 1:1"
- Numbered books: "1 John 3:16", "1John 3:16", "I John 3:16"
- Verse ranges: "Genesis 1:1-3"
- Chapter-only: "Psalm 23" (returns verse_start=1, verse_end=None, is_chapter=True)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedReference:
    """
    A parsed scripture reference.

    Attributes:
        book: Normalized book name (e.g., "Genesis", "1 John")
        chapter: Chapter number
        verse_start: Starting verse (1 for chapter-only references)
        verse_end: Ending verse (None for single verse or chapter)
        original: Original input string
        is_chapter: True if this is a chapter-only reference
    """
    book: str
    chapter: int
    verse_start: int
    verse_end: Optional[int] = None
    original: str = ""
    is_chapter: bool = False

    @property
    def normalized(self) -> str:
        """Return normalized reference string."""
        if self.is_chapter:
            return f"{self.book} {self.chapter}"
        if self.verse_end and self.verse_end != self.verse_start:
            return f"{self.book} {self.chapter}:{self.verse_start}-{self.verse_end}"
        return f"{self.book} {self.chapter}:{self.verse_start}"

    @property
    def verse_count(self) -> int:
        """Return number of verses in this reference."""
        if self.is_chapter:
            return 0  # Unknown without verse count data
        if self.verse_end:
            return self.verse_end - self.verse_start + 1
        return 1

    def to_sefaria_format(self) -> str:
        """Convert to Sefaria API format: Genesis.1.1-3"""
        if self.is_chapter:
            return f"{self.book}.{self.chapter}"
        if self.verse_end:
            return f"{self.book}.{self.chapter}.{self.verse_start}-{self.verse_end}"
        return f"{self.book}.{self.chapter}.{self.verse_start}"

    def to_osis_format(self) -> str:
        """Convert to OSIS format: Gen.1.1-Gen.1.3"""
        # Get OSIS abbreviation
        osis = BOOK_TO_OSIS.get(self.book, self.book[:3])
        if self.is_chapter:
            return f"{osis}.{self.chapter}"
        if self.verse_end:
            return f"{osis}.{self.chapter}.{self.verse_start}-{osis}.{self.chapter}.{self.verse_end}"
        return f"{osis}.{self.chapter}.{self.verse_start}"


# Book name mapping - abbreviations to full names
# Keys are lowercase, values are canonical names
BOOK_NAMES = {
    # Torah/Pentateuch
    "gen": "Genesis",
    "genesis": "Genesis",
    "gn": "Genesis",
    "exod": "Exodus",
    "ex": "Exodus",
    "exodus": "Exodus",
    "exo": "Exodus",
    "lev": "Leviticus",
    "leviticus": "Leviticus",
    "lv": "Leviticus",
    "num": "Numbers",
    "numbers": "Numbers",
    "nm": "Numbers",
    "nu": "Numbers",
    "deut": "Deuteronomy",
    "deuteronomy": "Deuteronomy",
    "dt": "Deuteronomy",
    "deu": "Deuteronomy",

    # Historical Books
    "josh": "Joshua",
    "joshua": "Joshua",
    "jos": "Joshua",
    "judg": "Judges",
    "judges": "Judges",
    "jdg": "Judges",
    "jg": "Judges",
    "ruth": "Ruth",
    "ru": "Ruth",
    "rth": "Ruth",
    "1sam": "1 Samuel",
    "1 sam": "1 Samuel",
    "1 samuel": "1 Samuel",
    "1samuel": "1 Samuel",
    "i sam": "1 Samuel",
    "i samuel": "1 Samuel",
    "1sa": "1 Samuel",
    "2sam": "2 Samuel",
    "2 sam": "2 Samuel",
    "2 samuel": "2 Samuel",
    "2samuel": "2 Samuel",
    "ii sam": "2 Samuel",
    "ii samuel": "2 Samuel",
    "2sa": "2 Samuel",
    "1kgs": "1 Kings",
    "1 kgs": "1 Kings",
    "1 kings": "1 Kings",
    "1kings": "1 Kings",
    "i kings": "1 Kings",
    "i kgs": "1 Kings",
    "1ki": "1 Kings",
    "2kgs": "2 Kings",
    "2 kgs": "2 Kings",
    "2 kings": "2 Kings",
    "2kings": "2 Kings",
    "ii kings": "2 Kings",
    "ii kgs": "2 Kings",
    "2ki": "2 Kings",
    "1chr": "1 Chronicles",
    "1 chr": "1 Chronicles",
    "1 chronicles": "1 Chronicles",
    "1chronicles": "1 Chronicles",
    "i chronicles": "1 Chronicles",
    "i chr": "1 Chronicles",
    "1ch": "1 Chronicles",
    "2chr": "2 Chronicles",
    "2 chr": "2 Chronicles",
    "2 chronicles": "2 Chronicles",
    "2chronicles": "2 Chronicles",
    "ii chronicles": "2 Chronicles",
    "ii chr": "2 Chronicles",
    "2ch": "2 Chronicles",
    "ezra": "Ezra",
    "ezr": "Ezra",
    "neh": "Nehemiah",
    "nehemiah": "Nehemiah",
    "ne": "Nehemiah",
    "esth": "Esther",
    "esther": "Esther",
    "est": "Esther",
    "es": "Esther",

    # Wisdom/Poetry
    "job": "Job",
    "jb": "Job",
    "ps": "Psalms",
    "psalm": "Psalms",
    "psalms": "Psalms",
    "psa": "Psalms",
    "pss": "Psalms",
    "prov": "Proverbs",
    "proverbs": "Proverbs",
    "pr": "Proverbs",
    "prv": "Proverbs",
    "eccl": "Ecclesiastes",
    "ecclesiastes": "Ecclesiastes",
    "ecc": "Ecclesiastes",
    "ec": "Ecclesiastes",
    "qoh": "Ecclesiastes",
    "qoheleth": "Ecclesiastes",
    "song": "Song of Solomon",
    "song of solomon": "Song of Solomon",
    "song of songs": "Song of Solomon",
    "sos": "Song of Solomon",
    "ss": "Song of Solomon",
    "canticles": "Song of Solomon",
    "cant": "Song of Solomon",
    "sg": "Song of Solomon",

    # Major Prophets
    "isa": "Isaiah",
    "isaiah": "Isaiah",
    "is": "Isaiah",
    "jer": "Jeremiah",
    "jeremiah": "Jeremiah",
    "je": "Jeremiah",
    "lam": "Lamentations",
    "lamentations": "Lamentations",
    "la": "Lamentations",
    "ezek": "Ezekiel",
    "ezekiel": "Ezekiel",
    "eze": "Ezekiel",
    "ez": "Ezekiel",
    "dan": "Daniel",
    "daniel": "Daniel",
    "dn": "Daniel",
    "da": "Daniel",

    # Minor Prophets
    "hos": "Hosea",
    "hosea": "Hosea",
    "ho": "Hosea",
    "joel": "Joel",
    "jl": "Joel",
    "joe": "Joel",
    "amos": "Amos",
    "am": "Amos",
    "obad": "Obadiah",
    "obadiah": "Obadiah",
    "ob": "Obadiah",
    "jonah": "Jonah",
    "jon": "Jonah",
    "jnh": "Jonah",
    "mic": "Micah",
    "micah": "Micah",
    "mi": "Micah",
    "nah": "Nahum",
    "nahum": "Nahum",
    "na": "Nahum",
    "hab": "Habakkuk",
    "habakkuk": "Habakkuk",
    "hb": "Habakkuk",
    "zeph": "Zephaniah",
    "zephaniah": "Zephaniah",
    "zep": "Zephaniah",
    "hag": "Haggai",
    "haggai": "Haggai",
    "hg": "Haggai",
    "zech": "Zechariah",
    "zechariah": "Zechariah",
    "zec": "Zechariah",
    "zc": "Zechariah",
    "mal": "Malachi",
    "malachi": "Malachi",
    "ml": "Malachi",

    # New Testament - Gospels
    "matt": "Matthew",
    "matthew": "Matthew",
    "mt": "Matthew",
    "mat": "Matthew",
    "mark": "Mark",
    "mk": "Mark",
    "mr": "Mark",
    "luke": "Luke",
    "lk": "Luke",
    "lu": "Luke",
    "john": "John",
    "jn": "John",
    "joh": "John",

    # Acts
    "acts": "Acts",
    "ac": "Acts",
    "act": "Acts",

    # Pauline Epistles
    "rom": "Romans",
    "romans": "Romans",
    "ro": "Romans",
    "rm": "Romans",
    "1cor": "1 Corinthians",
    "1 cor": "1 Corinthians",
    "1 corinthians": "1 Corinthians",
    "1corinthians": "1 Corinthians",
    "i corinthians": "1 Corinthians",
    "i cor": "1 Corinthians",
    "1co": "1 Corinthians",
    "2cor": "2 Corinthians",
    "2 cor": "2 Corinthians",
    "2 corinthians": "2 Corinthians",
    "2corinthians": "2 Corinthians",
    "ii corinthians": "2 Corinthians",
    "ii cor": "2 Corinthians",
    "2co": "2 Corinthians",
    "gal": "Galatians",
    "galatians": "Galatians",
    "ga": "Galatians",
    "eph": "Ephesians",
    "ephesians": "Ephesians",
    "ep": "Ephesians",
    "phil": "Philippians",
    "philippians": "Philippians",
    "php": "Philippians",
    "pp": "Philippians",
    "col": "Colossians",
    "colossians": "Colossians",
    "co": "Colossians",
    "1thess": "1 Thessalonians",
    "1 thess": "1 Thessalonians",
    "1 thessalonians": "1 Thessalonians",
    "1thessalonians": "1 Thessalonians",
    "i thessalonians": "1 Thessalonians",
    "i thess": "1 Thessalonians",
    "1th": "1 Thessalonians",
    "2thess": "2 Thessalonians",
    "2 thess": "2 Thessalonians",
    "2 thessalonians": "2 Thessalonians",
    "2thessalonians": "2 Thessalonians",
    "ii thessalonians": "2 Thessalonians",
    "ii thess": "2 Thessalonians",
    "2th": "2 Thessalonians",
    "1tim": "1 Timothy",
    "1 tim": "1 Timothy",
    "1 timothy": "1 Timothy",
    "1timothy": "1 Timothy",
    "i timothy": "1 Timothy",
    "i tim": "1 Timothy",
    "1ti": "1 Timothy",
    "2tim": "2 Timothy",
    "2 tim": "2 Timothy",
    "2 timothy": "2 Timothy",
    "2timothy": "2 Timothy",
    "ii timothy": "2 Timothy",
    "ii tim": "2 Timothy",
    "2ti": "2 Timothy",
    "titus": "Titus",
    "tit": "Titus",
    "ti": "Titus",
    "philem": "Philemon",
    "philemon": "Philemon",
    "phlm": "Philemon",
    "phm": "Philemon",
    "pm": "Philemon",

    # General Epistles
    "heb": "Hebrews",
    "hebrews": "Hebrews",
    "he": "Hebrews",
    "jas": "James",
    "james": "James",
    "jm": "James",
    "ja": "James",
    "1pet": "1 Peter",
    "1 pet": "1 Peter",
    "1 peter": "1 Peter",
    "1peter": "1 Peter",
    "i peter": "1 Peter",
    "i pet": "1 Peter",
    "1pe": "1 Peter",
    "1pt": "1 Peter",
    "2pet": "2 Peter",
    "2 pet": "2 Peter",
    "2 peter": "2 Peter",
    "2peter": "2 Peter",
    "ii peter": "2 Peter",
    "ii pet": "2 Peter",
    "2pe": "2 Peter",
    "2pt": "2 Peter",
    "1john": "1 John",
    "1 john": "1 John",
    "1 jn": "1 John",
    "i john": "1 John",
    "i jn": "1 John",
    "1jn": "1 John",
    "1jo": "1 John",
    "2john": "2 John",
    "2 john": "2 John",
    "2 jn": "2 John",
    "ii john": "2 John",
    "ii jn": "2 John",
    "2jn": "2 John",
    "2jo": "2 John",
    "3john": "3 John",
    "3 john": "3 John",
    "3 jn": "3 John",
    "iii john": "3 John",
    "iii jn": "3 John",
    "3jn": "3 John",
    "3jo": "3 John",
    "jude": "Jude",
    "jd": "Jude",
    "jud": "Jude",

    # Revelation
    "rev": "Revelation",
    "revelation": "Revelation",
    "re": "Revelation",
    "apoc": "Revelation",
    "apocalypse": "Revelation",
    "rv": "Revelation",
}

# Canonical book name to OSIS abbreviation
BOOK_TO_OSIS = {
    "Genesis": "Gen",
    "Exodus": "Exod",
    "Leviticus": "Lev",
    "Numbers": "Num",
    "Deuteronomy": "Deut",
    "Joshua": "Josh",
    "Judges": "Judg",
    "Ruth": "Ruth",
    "1 Samuel": "1Sam",
    "2 Samuel": "2Sam",
    "1 Kings": "1Kgs",
    "2 Kings": "2Kgs",
    "1 Chronicles": "1Chr",
    "2 Chronicles": "2Chr",
    "Ezra": "Ezra",
    "Nehemiah": "Neh",
    "Esther": "Esth",
    "Job": "Job",
    "Psalms": "Ps",
    "Proverbs": "Prov",
    "Ecclesiastes": "Eccl",
    "Song of Solomon": "Song",
    "Isaiah": "Isa",
    "Jeremiah": "Jer",
    "Lamentations": "Lam",
    "Ezekiel": "Ezek",
    "Daniel": "Dan",
    "Hosea": "Hos",
    "Joel": "Joel",
    "Amos": "Amos",
    "Obadiah": "Obad",
    "Jonah": "Jonah",
    "Micah": "Mic",
    "Nahum": "Nah",
    "Habakkuk": "Hab",
    "Zephaniah": "Zeph",
    "Haggai": "Hag",
    "Zechariah": "Zech",
    "Malachi": "Mal",
    "Matthew": "Matt",
    "Mark": "Mark",
    "Luke": "Luke",
    "John": "John",
    "Acts": "Acts",
    "Romans": "Rom",
    "1 Corinthians": "1Cor",
    "2 Corinthians": "2Cor",
    "Galatians": "Gal",
    "Ephesians": "Eph",
    "Philippians": "Phil",
    "Colossians": "Col",
    "1 Thessalonians": "1Thess",
    "2 Thessalonians": "2Thess",
    "1 Timothy": "1Tim",
    "2 Timothy": "2Tim",
    "Titus": "Titus",
    "Philemon": "Phlm",
    "Hebrews": "Heb",
    "James": "Jas",
    "1 Peter": "1Pet",
    "2 Peter": "2Pet",
    "1 John": "1John",
    "2 John": "2John",
    "3 John": "3John",
    "Jude": "Jude",
    "Revelation": "Rev",
}


class ReferenceParseError(Exception):
    """Raised when a reference cannot be parsed."""
    pass


def normalize_book_name(name: str) -> str:
    """
    Normalize book name to standard form.

    Args:
        name: Book name in any format

    Returns:
        Canonical book name (e.g., "Genesis", "1 John")
    """
    # Remove periods, extra whitespace, lowercase
    key = name.lower().replace(".", "").strip()
    # Normalize multiple spaces
    key = re.sub(r'\s+', ' ', key)

    if key in BOOK_NAMES:
        return BOOK_NAMES[key]

    # Try without the number prefix for numbered books
    # e.g., "1 john" might be stored as "1john"
    key_no_space = key.replace(" ", "")
    if key_no_space in BOOK_NAMES:
        return BOOK_NAMES[key_no_space]

    # Return title-cased original if not found
    return name.title()


def parse_reference(ref_string: str) -> Optional[ParsedReference]:
    """
    Parse a scripture reference string.

    Handles many formats:
    - "Genesis 1:1"
    - "Gen 1:1"
    - "Gen. 1:1"
    - "Genesis 1:1-3"
    - "1 John 3:16"
    - "1John 3:16"
    - "I John 3:16"
    - "Psalm 23" (chapter only)
    - "1 Cor. 13:4-7"

    Args:
        ref_string: The reference string to parse

    Returns:
        ParsedReference object or None if parsing fails
    """
    if not ref_string:
        return None

    ref_string = ref_string.strip()

    # Normalize whitespace
    ref_string = re.sub(r'\s+', ' ', ref_string)

    # Pattern for numbered books with chapter:verse
    # Matches: "1 John 3:16", "1John 3:16", "I John 3:16", "2 Cor. 13:4-7"
    numbered_verse_pattern = r'^([123]|I{1,3})\s*([A-Za-z]+)\.?\s+(\d+):(\d+)(?:\s*[-–—]\s*(\d+))?$'

    # Pattern for numbered books with chapter only
    # Matches: "1 John 3", "2 Peter 1"
    numbered_chapter_pattern = r'^([123]|I{1,3})\s*([A-Za-z]+)\.?\s+(\d+)$'

    # Pattern for regular books with chapter:verse
    # Matches: "Genesis 1:1", "Gen. 1:1-3", "Psalm 23:1"
    regular_verse_pattern = r'^([A-Za-z][A-Za-z\s]*?)\.?\s+(\d+):(\d+)(?:\s*[-–—]\s*(\d+))?$'

    # Pattern for regular books with chapter only
    # Matches: "Psalm 23", "Genesis 1"
    regular_chapter_pattern = r'^([A-Za-z][A-Za-z\s]*?)\.?\s+(\d+)$'

    # Try numbered book with verse first
    match = re.match(numbered_verse_pattern, ref_string, re.IGNORECASE)
    if match:
        num, book, chapter, verse_start, verse_end = match.groups()
        # Convert Roman numerals
        num = num.upper()
        if num == "III":
            num = "3"
        elif num == "II":
            num = "2"
        elif num == "I":
            num = "1"
        book_name = f"{num} {book}"
        return ParsedReference(
            book=normalize_book_name(book_name),
            chapter=int(chapter),
            verse_start=int(verse_start),
            verse_end=int(verse_end) if verse_end else None,
            original=ref_string,
            is_chapter=False,
        )

    # Try numbered book with chapter only
    match = re.match(numbered_chapter_pattern, ref_string, re.IGNORECASE)
    if match:
        num, book, chapter = match.groups()
        num = num.upper()
        if num == "III":
            num = "3"
        elif num == "II":
            num = "2"
        elif num == "I":
            num = "1"
        book_name = f"{num} {book}"
        return ParsedReference(
            book=normalize_book_name(book_name),
            chapter=int(chapter),
            verse_start=1,
            verse_end=None,
            original=ref_string,
            is_chapter=True,
        )

    # Try regular book with verse
    match = re.match(regular_verse_pattern, ref_string, re.IGNORECASE)
    if match:
        book_name, chapter, verse_start, verse_end = match.groups()
        return ParsedReference(
            book=normalize_book_name(book_name),
            chapter=int(chapter),
            verse_start=int(verse_start),
            verse_end=int(verse_end) if verse_end else None,
            original=ref_string,
            is_chapter=False,
        )

    # Try regular book with chapter only
    match = re.match(regular_chapter_pattern, ref_string, re.IGNORECASE)
    if match:
        book_name, chapter = match.groups()
        return ParsedReference(
            book=normalize_book_name(book_name),
            chapter=int(chapter),
            verse_start=1,
            verse_end=None,
            original=ref_string,
            is_chapter=True,
        )

    return None


def find_references(text: str) -> list[ParsedReference]:
    """
    Find all scripture references in a text block.

    Args:
        text: Text to search for references

    Returns:
        List of ParsedReference objects found
    """
    # Known book names and abbreviations for matching
    book_pattern = (
        r'(?:'
        # Numbered books
        r'(?:[123]|I{1,3})\s*(?:Sam(?:uel)?|Kgs|Kings|Chr(?:on(?:icles)?)?|'
        r'Cor(?:inthians)?|Thess(?:alonians)?|Tim(?:othy)?|Pet(?:er)?|'
        r'Jn|John|Joh)|'
        # Regular books - full names
        r'Genesis|Exodus|Leviticus|Numbers|Deuteronomy|'
        r'Joshua|Judges|Ruth|Ezra|Nehemiah|Esther|Job|'
        r'Psalms?|Proverbs?|Ecclesiastes|Song(?:\s+of\s+(?:Solomon|Songs))?|'
        r'Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|'
        r'Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|'
        r'Zephaniah|Haggai|Zechariah|Malachi|'
        r'Matthew|Mark|Luke|John|Acts|Romans|'
        r'Galatians|Ephesians|Philippians|Colossians|'
        r'Titus|Philemon|Hebrews|James|Jude|Revelation|'
        # Common abbreviations
        r'Gen|Exod?|Lev|Num|Deut?|Josh|Judg|'
        r'Neh|Esth?|Psa?|Prov?|Eccl?|Isa|Jer|Lam|Ezek?|Dan|'
        r'Hos|Mic|Nah|Hab|Zeph|Hag|Zech?|Mal|'
        r'Matt?|Mk|Lk|Jn|Rom|Gal|Eph|Phil|Col|Heb|Jas|Rev'
        r')'
    )

    # Pattern: book name followed by chapter:verse(-verse)?
    verse_pattern = rf'\b{book_pattern}\.?\s+\d+:\d+(?:\s*[-–—]\s*\d+)?'

    # Pattern: book name followed by chapter only (for specific books)
    chapter_only_books = (
        r'(?:Psalms?|Psalm|Genesis|Exodus|Proverbs?|Isaiah|Matthew|Mark|Luke|John|Acts|Romans|'
        r'Revelation|Hebrews|James)'
    )
    chapter_pattern = rf'\b{chapter_only_books}\s+\d+(?!\s*:|\d)'

    refs = []
    seen = set()

    # Find verse references first (more specific)
    for match in re.finditer(verse_pattern, text, re.IGNORECASE):
        match_text = match.group().strip()
        parsed = parse_reference(match_text)
        if parsed and parsed.normalized not in seen:
            refs.append(parsed)
            seen.add(parsed.normalized)

    # Find chapter-only references
    for match in re.finditer(chapter_pattern, text, re.IGNORECASE):
        match_text = match.group().strip()
        parsed = parse_reference(match_text)
        if parsed and parsed.normalized not in seen:
            refs.append(parsed)
            seen.add(parsed.normalized)

    return refs


def to_sefaria_format(ref: ParsedReference) -> str:
    """
    Convert ParsedReference to Sefaria API format.

    Args:
        ref: ParsedReference object

    Returns:
        Sefaria format string (e.g., "Genesis.1.1-3")
    """
    return ref.to_sefaria_format()


def to_osis_format(ref: ParsedReference) -> str:
    """
    Convert ParsedReference to OSIS format.

    Args:
        ref: ParsedReference object

    Returns:
        OSIS format string (e.g., "Gen.1.1-Gen.1.3")
    """
    return ref.to_osis_format()


def is_valid_reference(ref_string: str) -> bool:
    """
    Check if a string is a valid scripture reference.

    Args:
        ref_string: String to check

    Returns:
        True if valid reference, False otherwise
    """
    return parse_reference(ref_string) is not None
