// ui/src/utils/referenceParser.js
/**
 * Scripture reference parsing utility.
 * Detects and normalizes Bible references in text.
 */

// Book name mappings (abbreviations to full names)
const BOOK_NAMES = {
  // Torah
  'gen': 'Genesis', 'genesis': 'Genesis',
  'exod': 'Exodus', 'ex': 'Exodus', 'exodus': 'Exodus',
  'lev': 'Leviticus', 'leviticus': 'Leviticus',
  'num': 'Numbers', 'numbers': 'Numbers',
  'deut': 'Deuteronomy', 'deuteronomy': 'Deuteronomy', 'dt': 'Deuteronomy',

  // Historical
  'josh': 'Joshua', 'joshua': 'Joshua',
  'judg': 'Judges', 'judges': 'Judges',
  'ruth': 'Ruth',
  '1sam': '1 Samuel', '1 sam': '1 Samuel', '1 samuel': '1 Samuel',
  '2sam': '2 Samuel', '2 sam': '2 Samuel', '2 samuel': '2 Samuel',
  '1kgs': '1 Kings', '1 kings': '1 Kings',
  '2kgs': '2 Kings', '2 kings': '2 Kings',
  '1chr': '1 Chronicles', '1 chronicles': '1 Chronicles',
  '2chr': '2 Chronicles', '2 chronicles': '2 Chronicles',
  'ezra': 'Ezra',
  'neh': 'Nehemiah', 'nehemiah': 'Nehemiah',
  'esth': 'Esther', 'esther': 'Esther',

  // Poetry/Wisdom
  'job': 'Job',
  'ps': 'Psalms', 'psalm': 'Psalms', 'psalms': 'Psalms', 'psa': 'Psalms',
  'prov': 'Proverbs', 'proverbs': 'Proverbs', 'pr': 'Proverbs',
  'eccl': 'Ecclesiastes', 'ecclesiastes': 'Ecclesiastes',
  'song': 'Song of Solomon', 'song of solomon': 'Song of Solomon',

  // Major Prophets
  'isa': 'Isaiah', 'isaiah': 'Isaiah',
  'jer': 'Jeremiah', 'jeremiah': 'Jeremiah',
  'lam': 'Lamentations', 'lamentations': 'Lamentations',
  'ezek': 'Ezekiel', 'ezekiel': 'Ezekiel',
  'dan': 'Daniel', 'daniel': 'Daniel',

  // Minor Prophets
  'hos': 'Hosea', 'hosea': 'Hosea',
  'joel': 'Joel',
  'amos': 'Amos',
  'obad': 'Obadiah', 'obadiah': 'Obadiah',
  'jonah': 'Jonah',
  'mic': 'Micah', 'micah': 'Micah',
  'nah': 'Nahum', 'nahum': 'Nahum',
  'hab': 'Habakkuk', 'habakkuk': 'Habakkuk',
  'zeph': 'Zephaniah', 'zephaniah': 'Zephaniah',
  'hag': 'Haggai', 'haggai': 'Haggai',
  'zech': 'Zechariah', 'zechariah': 'Zechariah',
  'mal': 'Malachi', 'malachi': 'Malachi',

  // NT Gospels
  'matt': 'Matthew', 'matthew': 'Matthew', 'mt': 'Matthew',
  'mark': 'Mark', 'mk': 'Mark',
  'luke': 'Luke', 'lk': 'Luke',
  'john': 'John', 'jn': 'John',

  // Acts
  'acts': 'Acts',

  // Pauline
  'rom': 'Romans', 'romans': 'Romans',
  '1cor': '1 Corinthians', '1 cor': '1 Corinthians', '1 corinthians': '1 Corinthians',
  '2cor': '2 Corinthians', '2 cor': '2 Corinthians', '2 corinthians': '2 Corinthians',
  'gal': 'Galatians', 'galatians': 'Galatians',
  'eph': 'Ephesians', 'ephesians': 'Ephesians',
  'phil': 'Philippians', 'philippians': 'Philippians',
  'col': 'Colossians', 'colossians': 'Colossians',
  '1thess': '1 Thessalonians', '1 thess': '1 Thessalonians',
  '2thess': '2 Thessalonians', '2 thess': '2 Thessalonians',
  '1tim': '1 Timothy', '1 tim': '1 Timothy', '1 timothy': '1 Timothy',
  '2tim': '2 Timothy', '2 tim': '2 Timothy', '2 timothy': '2 Timothy',
  'titus': 'Titus',
  'philem': 'Philemon', 'philemon': 'Philemon',

  // General Epistles
  'heb': 'Hebrews', 'hebrews': 'Hebrews',
  'jas': 'James', 'james': 'James',
  '1pet': '1 Peter', '1 pet': '1 Peter', '1 peter': '1 Peter',
  '2pet': '2 Peter', '2 pet': '2 Peter', '2 peter': '2 Peter',
  '1john': '1 John', '1 jn': '1 John', '1 john': '1 John',
  '2john': '2 John', '2 jn': '2 John', '2 john': '2 John',
  '3john': '3 John', '3 jn': '3 John', '3 john': '3 John',
  'jude': 'Jude',

  // Revelation
  'rev': 'Revelation', 'revelation': 'Revelation',
};

/**
 * Normalize a book name to standard form.
 *
 * @param {string} name - Book name or abbreviation
 * @returns {string} - Normalized book name
 */
export function normalizeBookName(name) {
  const key = name.toLowerCase().replace(/\./g, '').trim();
  return BOOK_NAMES[key] || name;
}

/**
 * Parse a single scripture reference string.
 *
 * @param {string} refString - e.g., "Gen 1:1-3", "1 John 3:16"
 * @returns {object|null} - { book, chapter, verseStart, verseEnd, normalized, original }
 */
export function parseReference(refString) {
  if (!refString) return null;

  refString = refString.trim();

  // Pattern for numbered books (1 John, 2 Kings, I Cor, etc.)
  const numberedPattern = /^([123]|I{1,3})\s*([A-Za-z]+)\s+(\d+):(\d+)(?:-(\d+))?/i;

  // Pattern for regular books
  const regularPattern = /^([A-Za-z]+)\.?\s+(\d+):(\d+)(?:-(\d+))?/i;

  let match = refString.match(numberedPattern);
  let bookName;
  let chapter, verseStart, verseEnd;

  if (match) {
    let [, num, book, ch, vs, ve] = match;
    // Normalize Roman numerals to Arabic
    num = num.toUpperCase().replace('III', '3').replace('II', '2').replace('I', '1');
    bookName = `${num} ${book}`;
    chapter = parseInt(ch, 10);
    verseStart = parseInt(vs, 10);
    verseEnd = ve ? parseInt(ve, 10) : null;
  } else {
    match = refString.match(regularPattern);
    if (!match) return null;

    let [, book, ch, vs, ve] = match;
    bookName = book;
    chapter = parseInt(ch, 10);
    verseStart = parseInt(vs, 10);
    verseEnd = ve ? parseInt(ve, 10) : null;
  }

  const normalizedBook = normalizeBookName(bookName);
  const normalized = verseEnd
    ? `${normalizedBook} ${chapter}:${verseStart}-${verseEnd}`
    : `${normalizedBook} ${chapter}:${verseStart}`;

  return {
    book: normalizedBook,
    chapter,
    verseStart,
    verseEnd,
    normalized,
    original: refString,
  };
}

/**
 * Find all scripture references in a block of text.
 *
 * @param {string} text - Text to search
 * @returns {Array} - Array of { match, index, endIndex, parsed }
 */
export function findReferences(text) {
  if (!text) return [];

  // Pattern to match potential references
  // Handles: "Gen 1:1", "1 John 3:16", "I Cor 13:4-7", "Psalm 23:1-6"
  const pattern = /(?:[123]|I{1,3})?\s*[A-Za-z]+\.?\s+\d+:\d+(?:-\d+)?/gi;

  const results = [];
  let match;

  while ((match = pattern.exec(text)) !== null) {
    const parsed = parseReference(match[0]);
    if (parsed) {
      results.push({
        match: match[0],
        index: match.index,
        endIndex: match.index + match[0].length,
        parsed,
      });
    }
  }

  return results;
}

/**
 * Check if a string looks like a scripture reference.
 *
 * @param {string} text - Text to check
 * @returns {boolean} - True if text appears to be a reference
 */
export function isReference(text) {
  return parseReference(text) !== null;
}

/**
 * Format a reference object back to string.
 *
 * @param {object} ref - Reference object with book, chapter, verseStart, verseEnd
 * @returns {string} - Formatted reference string
 */
export function formatReference(ref) {
  if (!ref || !ref.book || !ref.chapter || !ref.verseStart) {
    return '';
  }

  if (ref.verseEnd && ref.verseEnd !== ref.verseStart) {
    return `${ref.book} ${ref.chapter}:${ref.verseStart}-${ref.verseEnd}`;
  }
  return `${ref.book} ${ref.chapter}:${ref.verseStart}`;
}

/**
 * Build API lookup URL for a reference.
 *
 * @param {string|object} ref - Reference string or parsed object
 * @param {object} options - { sources, translations }
 * @returns {string} - API URL for lookup
 */
export function buildLookupUrl(ref, options = {}) {
  const refString = typeof ref === 'string' ? ref : formatReference(ref);
  const params = new URLSearchParams({ ref: refString });

  if (options.sources) {
    params.set('sources', options.sources.join(','));
  }
  if (options.translations) {
    params.set('translations', options.translations.join(','));
  }

  return `/api/references/lookup?${params.toString()}`;
}

export default {
  normalizeBookName,
  parseReference,
  findReferences,
  isReference,
  formatReference,
  buildLookupUrl,
  BOOK_NAMES,
};
