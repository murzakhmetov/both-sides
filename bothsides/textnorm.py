"""Text folding and tokens shared by every word-based check.

People type Kazakh with plain Cyrillic letters, mix scripts and skip
punctuation. Folding maps all of that to one plain spelling. The rules are
simple on purpose, so that a JavaScript port can follow them line by line.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .datafiles import load_json

_KAZAKH_TO_PLAIN = str.maketrans(
    {
        "ә": "а",
        "ғ": "г",
        "қ": "к",
        "ң": "н",
        "ө": "о",
        "ұ": "у",
        "ү": "у",
        "һ": "х",
        "і": "и",
        "ё": "е",
    }
)

#: Latin letters that look like Cyrillic ones, used only inside words that
#: already contain a Cyrillic letter ("әкe" typed with a Latin e).
_LATIN_LOOKALIKES = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "н",
        "i": "и",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
    }
)

#: Words that only the typed letters tell apart. "ага" with a plain "г" is the Russian
#: "yeah", the Kazakh "аға" has "ғ". "досқа" is "to a friend", "доска" is a board.
_BEFORE_FOLDING = {"ага": "угу", "досқа": "дос"}

#: Signs that people type instead of an apostrophe ("don´t").
_APOSTROPHE_SIGNS = str.maketrans({sign: "'" for sign in "\u2018\u00b4\u2032"})
#: "№5" and "flat No 5" are numbers, not the English "no". "I have no 2 brothers" stays.
_NUMBER_SIGN = re.compile(r"№|(?<=\bflat )no\.?\s*(?=\d)|(?<=\bhouse )no\.?\s*(?=\d)|(?<=\bschool )no\.?\s*(?=\d)|(?<=\broom )no\.?\s*(?=\d)", re.IGNORECASE)
_APOSTROPHES = re.compile("['’ʼ`]")
_WORD = re.compile(r"[^\W\d_]+")
_CYRILLIC = re.compile(r"[а-яёәғқңөұүһі]")
_LATIN = re.compile(r"[a-z]")

#: Links, e-mail addresses and handles. They say nothing about a transfer.
_CONTACT = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\S+\s?@\s?[\w.-]+\.\w+"
    r"|\S*@\S+"
    r"|[\w-]+(?:\.[\w-]+)*\.[^\W\d_]{2,}/\S*"
    r"|\b[\w-]+\.(?:com|kz|ru|me|net|org|io|app)\b",
    re.IGNORECASE,
)


#: Format characters, and the marks that are still loose after composing: stress marks,
#: variation selectors. None of them may split or change a word.
_INVISIBLE = frozenset({"Cf", "Mn", "Me"})


def clean(text: str) -> str:
    """Return *text* with composed letters and plain apostrophes, without invisible characters and number signs."""
    composed = unicodedata.normalize("NFKC", _NUMBER_SIGN.sub(" ", text.translate(_APOSTROPHE_SIGNS)))
    return "".join(ch for ch in composed if unicodedata.category(ch) not in _INVISIBLE)


def _visible(char: str) -> str:
    category = unicodedata.category(char)
    if category in _INVISIBLE:
        return ""
    return " " if category[0] == "C" else char


def one_line(text: str) -> str:
    """Return *text* as one tidy line without control characters.

    Soft hyphens, zero-width signs and the like are dropped, not turned into
    spaces: a word with one inside stays one word.
    """
    composed = unicodedata.normalize("NFC", text)
    return " ".join("".join(map(_visible, composed)).split())


def without_contacts(text: str) -> str:
    """Return *text* without links, e-mail addresses and handles."""
    return _CONTACT.sub(" ", text)


def fold_word(word: str) -> str:
    """Fold one lower-case word to plain Cyrillic or plain Latin letters."""
    if _CYRILLIC.search(word) and _LATIN.search(word):
        word = word.translate(_LATIN_LOOKALIKES)
    return word.translate(_KAZAKH_TO_PLAIN)


@lru_cache(maxsize=4096)
def typed_words(text: str) -> tuple[str, ...]:
    """Split *text* into lower-case words with the letters as typed."""
    return tuple(_WORD.findall(_APOSTROPHES.sub("", without_contacts(clean(text)).lower())))


@lru_cache(maxsize=4096)
def tokens(text: str) -> tuple[str, ...]:
    """Split *text* into folded words. Digits, marks and contacts are dropped."""
    return tuple(fold_word(_BEFORE_FOLDING.get(word, word)) for word in typed_words(text))


def has_kazakh_letter(word: str) -> bool:
    """True for a typed word with a letter that Russian does not have."""
    return any(ord(letter) in _KAZAKH_TO_PLAIN and letter != "ё" for letter in word)


def normalized(text: str) -> str:
    """Return the folded words joined by single spaces."""
    return " ".join(tokens(text))


@lru_cache(maxsize=None)
def kazakh_suffix() -> re.Pattern[str]:
    """The endings of Kazakh words (folded), in their order: plural, owner, case."""
    return re.compile(load_json("lexicon")["kazakh_suffix_pattern"])


# -- phrases of the shared word lists ------------------------------------------------

#: One position of a phrase: alternatives, each with "any ending" or not.
Part = tuple[tuple[str, bool], ...]
Phrase = tuple[Part, ...]


def read_phrase(text: str) -> Phrase:
    """Read "слово|слов* слово": | separates alternatives, * means any ending."""
    return tuple(
        tuple((fold_word(item.rstrip("*").lower()), item.endswith("*")) for item in part.split("|"))
        for part in text.split()
    )


def part_fits(word: str, part: Part) -> bool:
    """True when the word is one of the alternatives."""
    return any(word.startswith(text) if open_end else word == text for text, open_end in part)


def phrase_at(words: tuple[str, ...], start: int, phrase: Phrase, max_gap: int = 0) -> bool:
    """True when the phrase begins at *start*, with at most *max_gap* other words between."""
    if not part_fits(words[start], phrase[0]):
        return False
    if len(phrase) == 1:
        return True
    last = min(len(words) - 1, start + 1 + max_gap)
    return any(phrase_at(words, position, phrase[1:], max_gap) for position in range(start + 1, last + 1))


@lru_cache(maxsize=None)
def _ignored_phrases() -> tuple[Phrase, ...]:
    return tuple(read_phrase(phrase) for phrase in load_json("stopwords")["ignored_phrases"])


@lru_cache(maxsize=4096)
def meaning_tokens(text: str) -> tuple[str, ...]:
    """Tokens without fixed phrases that name no reason ("по номеру телефона")."""
    words = tokens(text)
    dropped = {
        start + offset
        for phrase in _ignored_phrases()
        for start in range(len(words) - len(phrase) + 1)
        if phrase_at(words, start, phrase)
        for offset in range(len(phrase))
    }
    return tuple(word for index, word in enumerate(words) if index not in dropped)
