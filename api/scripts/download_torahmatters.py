#!/usr/bin/env python3
"""
Download PDFs from Torah Matters resource catalog.
Source: https://www.torahmatters.com/
Curated by David Wilber, CEO of Pronomian Publishing LLC
"""

import os
import re
import time
import requests
from pathlib import Path
from urllib.parse import unquote

# Target directory
OUTPUT_DIR = Path("/mnt/library/religious/torahmatters")

# All PDF URLs from the Torah Matters catalog
# Format: (url, author_hint, title_hint, category)
PDF_SOURCES = [
    # === MATTHEW ===
    ("https://www.torahmatters.com/s/Charles-Garnishing-with-the-Greater-Righteousness.pdf",
     "Charles, J. D.", "Garnishing with the Greater Righteousness", "Matthew"),
    ("https://www.torahmatters.com/s/what-does-to-fulfill-mean-in-matt-5-17.pdf",
     "Hegg, Tim", "What Does plēroō Mean in Matthew 5:17", "Matthew"),
    ("https://www.torahmatters.com/s/Lavender-Jesus-Against-Oral-Torah-in-Matthew.pdf",
     "Lavender, Logan", "Jesus Against Oral Torah in Matthew", "Matthew"),
    ("https://www.torahmatters.com/s/Nguyen-Matthew-5v17-18.pdf",
     "Nguyen, Vien V.", "Matthew and the Torah - Analysis of Matthew 5:17-20", "Matthew"),
    ("https://www.torahmatters.com/s/Snodgrass-Matthews-understanding-of-law.pdf",
     "Snodgrass, Klyne R.", "Matthew's Understanding of the Law", "Matthew"),
    ("https://www.torahmatters.com/s/Abolishers_of_the_Law_in_Early_Judaism_a.pdf",
     "Thiessen, Matthew", "Abolishers of the Law in Early Judaism and Matthew 5:17-20", "Matthew"),
    ("https://www.torahmatters.com/s/Oliver-torah-praxis-after-70CE.pdf",
     "Oliver, Isaac", "Torah Praxis after 70 CE (Dissertation)", "Matthew-Luke"),
    ("https://www.torahmatters.com/s/Ethan-Lunik.pdf",
     "Lunik, Ethan", "I Came to Fulfill the Law - plēroō in Jesus' Discourses (MA Thesis)", "Matthew"),

    # === MARK ===
    ("https://www.torahmatters.com/s/Defilement_Penetrating_the_Body_A_New_Un.pdf",
     "Furstenberg, Yair", "Defilement Penetrating the Body - Mark 7:15", "Mark"),
    ("https://www.torahmatters.com/s/Hillel-A-Post-Supersessionist-Reading-of-Mark.pdf",
     "Hillel, Vered", "A Post-Supersessionist Reading of Temple and Torah in Mark", "Mark"),
    ("https://www.torahmatters.com/s/van_maaren_-_does_marks_jesus_abrogate_torah.pdf",
     "Van Maaren, John", "Does Mark's Jesus Abrogate Torah", "Mark"),
    ("https://www.torahmatters.com/s/williams-the-stomach-purifies-all-foods-jesus-anatomical-argument-in-mark-718-19.pdf",
     "Williams, Logan", "The Stomach Purifies All Foods - Mark 7:18-19", "Mark"),
    ("https://www.torahmatters.com/s/Van_Maaren_John_R_finalsubmission2019June_PhD.pdf",
     "Van Maaren, John R.", "The Gospel of Mark Within Judaism (PhD Dissertation)", "Mark"),

    # === LUKE ===
    ("https://www.torahmatters.com/s/David-Wilber-Sabbath-Observance-in-Luke-Acts-Situating-the-Earliest-Followers-of-Jesus-within-Judais.pdf",
     "Wilber, David", "Sabbath Observance in Luke-Acts", "Luke-Acts"),

    # === JOHN ===
    ("https://www.torahmatters.com/s/John-5_18_-Jesus-and-Sabbath-Law-A-Fresh-Look-at-a-Challenging-Te.pdf",
     "Papaioannou, Kim", "John 5:18 - Jesus and Sabbath Law", "John"),

    # === ACTS ===
    ("https://www.torahmatters.com/s/staples-acts10.pdf",
     "Staples, Jason A.", "Rise Kill and Eat - Animals as Nations in Acts 10", "Acts"),
    ("https://www.torahmatters.com/s/McKenzie-Dissertation.pdf",
     "McKenzie, G. S.", "Pronomian Paradigm (PhD Dissertation)", "Acts"),
    ("https://www.torahmatters.com/s/Frostad_he-made-no-distinction.pdf",
     "Frostad, Benjamin", "He Made No Distinction - Gentiles and Torah in Acts 15 (MA Thesis)", "Acts"),

    # === ROMANS ===
    ("https://www.torahmatters.com/s/When-Law-Came-to-Adam.pdf",
     "Kozman, Rony", "When Law Came to Adam - Romans 5", "Romans"),
    ("https://www.torahmatters.com/s/Jewish-Law-Observance-in-Paul.pdf",
     "Sloan, Paul T.", "Jewish Law-Observance in Paul", "Romans-Galatians"),
    ("https://www.torahmatters.com/s/Snodgrass-Spheres-of-Influence.pdf",
     "Snodgrass, Klyne", "Spheres of Influence - Paul and the Law", "Romans"),

    # === 1-2 CORINTHIANS ===
    ("https://www.torahmatters.com/s/David-Wilber-Following-the-Law-of-Moses-in-a-Christlike-Way-a-Pronomian-Reading-of-Law-of-Christ-in.pdf",
     "Wilber, David", "Following the Law of Moses in a Christlike Way - Law of Christ", "Corinthians-Galatians"),

    # === GALATIANS ===
    ("https://www.torahmatters.com/s/Gal-410-Col-218_Troy-Martin.pdf",
     "Martin, Troy W.", "Pagan and Judeo-Christian Time-Keeping in Gal 4:10 and Col 2:16", "Galatians-Colossians"),
    ("https://www.torahmatters.com/s/nanos_pauls_non-jews.pdf",
     "Nanos, Mark", "Paul's Non-Jews Do Not Become Jews But Do They Become Jewish", "Galatians"),
    ("https://www.torahmatters.com/s/nanos_re-framing_pauls_opposition__2_.pdf",
     "Nanos, Mark", "Re-Framing Paul's Opposition to Erga Nomou", "Galatians"),
    ("https://www.torahmatters.com/s/Law-of-Christ-Todd-Wilsdon.pdf",
     "Wilson, Todd A.", "The Law of Christ and the Law of Moses", "Galatians"),
    ("https://www.torahmatters.com/s/Under-Law-in-Galatians.pdf",
     "Wilson, Todd A.", "Under Law in Galatians - A Pauline Abbreviation", "Galatians"),

    # === EPHESIANS ===
    ("https://www.torahmatters.com/s/Windsor-Colossians-Ephesians.pdf",
     "Windsor, Lionel J.", "Israel and the Apostolic Mission - Ephesians and Colossians", "Ephesians-Colossians"),

    # === COLOSSIANS ===
    ("https://www.torahmatters.com/s/Allen-Removing_an_Arrow_from_the_Supersession.pdf",
     "Allen, Brian L.", "Removing an Arrow from the Supersessionist Quiver - Colossians 2:16-17", "Colossians"),

    # === HEBREWS ===
    ("https://www.torahmatters.com/s/Strengthened-by-Grace-and-Not-by-Foods.pdf",
     "Martin and Whitlark", "Strengthened by Grace and Not by Foods - Hebrews 13:7-14", "Hebrews"),
    ("https://www.torahmatters.com/s/Moffitt-weak-and-useless-purity-law-perfection.pdf",
     "Moffitt, David M.", "Weak and Useless - Purity Law and Perfection in Hebrews", "Hebrews"),
    ("https://www.torahmatters.com/s/Hebrews_and_the_Jewish_Law.pdf",
     "Thiessen, Matthew", "Hebrews and the Jewish Law", "Hebrews"),

    # === HISTORY & THEOLOGY ===
    ("https://www.torahmatters.com/s/Jesus-Oriented-Groups-and-the-Emergence-of-a-Rabbinic-Jewish-Identity.pdf",
     "Zetterholm, Karin H.", "Jesus-Oriented Groups and Rabbinic Jewish Identity", "History"),
    ("https://www.torahmatters.com/s/from_Sabbath_to_Sunday_samuele_bacchiocchi.pdf",
     "Bacchiocchi, Samuele", "From Sabbath to Sunday (Book)", "History"),
    ("https://www.torahmatters.com/s/An-Analysis-of-the-Methods-of-Interpretation-of-the-Leviticus-11.pdf",
     "Constantin, Ani I.", "Analysis of Leviticus 11 Dietary Laws Interpretation (MA Thesis)", "History"),
    ("https://www.torahmatters.com/s/For-Who-Has-Known-the-Mind-of-the-Apostle-Ryan-Collman.pdf",
     "Collman, Ryan D.", "For Who Has Known the Mind of the Apostle - Paul and the Law", "Paul"),
    ("https://www.torahmatters.com/s/Nanos-the-myth-of-the-law-free-paul.pdf",
     "Nanos, Mark D.", "The Myth of the Law-Free Paul", "Paul"),
    ("https://www.torahmatters.com/s/The-Role-of-the-Law-in-the-Sanctification-of-the-Believer-Today.pdf",
     "Szumskyj, Benjamin J. S.", "The Role of the Law in Sanctification - Intro to Pronomianism (PhD)", "Theology"),
]

def clean_filename(author: str, title: str) -> str:
    """Create clean filename: Author - Title.pdf"""
    # Remove special characters, keep alphanumeric and basic punctuation
    def sanitize(s: str) -> str:
        s = re.sub(r'[<>:"/\\|?*]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s[:80]  # Limit length

    author_clean = sanitize(author.split(',')[0])  # First part of author name
    title_clean = sanitize(title)

    return f"{author_clean} - {title_clean}.pdf"

def download_pdf(url: str, output_path: Path, timeout: int = 60) -> bool:
    """Download a PDF file with error handling."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()

        # Check if it's actually a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not url.endswith('.pdf'):
            print(f"  Warning: Content-Type is {content_type}")

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except requests.exceptions.RequestException as e:
        print(f"  Error: {e}")
        return False

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Torah Matters PDF Downloader")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Total PDFs to download: {len(PDF_SOURCES)}")
    print("=" * 60)

    success = 0
    failed = []
    skipped = 0

    for i, (url, author, title, category) in enumerate(PDF_SOURCES, 1):
        filename = clean_filename(author, title)
        output_path = OUTPUT_DIR / filename

        print(f"\n[{i}/{len(PDF_SOURCES)}] {filename}")
        print(f"  Category: {category}")
        print(f"  URL: {url[:70]}...")

        if output_path.exists():
            print(f"  SKIPPED (already exists)")
            skipped += 1
            continue

        if download_pdf(url, output_path):
            size_kb = output_path.stat().st_size / 1024
            print(f"  SUCCESS ({size_kb:.1f} KB)")
            success += 1
        else:
            failed.append((url, filename))

        # Be polite to the server
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print(f"Download complete!")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {len(failed)}")

    if failed:
        print("\nFailed downloads:")
        for url, filename in failed:
            print(f"  - {filename}")
            print(f"    {url}")

    print(f"\nFiles saved to: {OUTPUT_DIR}")
    print(f"Next step: Run library ingest")

if __name__ == "__main__":
    main()
