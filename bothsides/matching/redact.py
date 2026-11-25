"""Cleans an answer before it goes to the language model.

Removes digits, amounts in words, currency, contacts and one leading name
followed by a comma. Relation words such as "Брат," or "Анам," stay, and so does
every word that is not a listed name: "Неизвестный," is an answer.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ..datafiles import load_json
from ..textnorm import clean, fold_word, part_fits, read_phrase, without_contacts
from .names import is_given_name, is_name_part, is_relation_word

_IBAN_PREFIX = re.compile(r"\b[A-Za-z]{2}(?=\s*\d)")
_WORD = re.compile(r"[^\W\d_]+")
_SPACE_BEFORE_MARK = re.compile(r"\s+([,.;:!?])")
_REPEATED_MARK = re.compile(r"([,;:])(?:\s*[,;:])+")
_LONELY_MARK = re.compile(r"(?<!\S)[-–—/+№#*()]+(?!\S)")
_EDGES = " \t\r\n,;:.-–—+/№#()*«»\"“”„'"
_LEADING_SEGMENT = re.compile(r"^([^,]{1,60}),(.*)$", re.DOTALL)
_MAX_NAME_WORDS = 4
_PREPOSITIONS = frozenset({"от", "для", "у", "к", "с", "from", "to", "for"})


@lru_cache(maxsize=None)
def _amount_pattern() -> re.Pattern[str]:
    suffixes = sorted(load_json("redaction")["amount_suffixes"], key=len, reverse=True)
    suffix = "|".join(re.escape(item) for item in suffixes)
    # "½" becomes "1⁄2" (with a fraction slash) when the text is cleaned.
    return re.compile(rf"\d+(?:[\s.,:/⁄-]*\d+)*(?:\s*(?:{suffix})(?![^\W\d_]))?", re.IGNORECASE)


@lru_cache(maxsize=None)
def _amount_words() -> tuple[tuple[str, bool], ...]:
    data = load_json("redaction")
    words = (*data["currency_words"], *data["number_words"])
    return tuple(item for word in words for part in read_phrase(word) for item in part)


@lru_cache(maxsize=4096)
def _is_amount_word(word: str) -> bool:
    return part_fits(fold_word(word.lower()), _amount_words())


def _may_stay(word: str, text: str) -> bool:
    """True for "торт" (cake) and "СТО" (car service): on their own they are no amounts.

    In a text typed in capitals only, "СТО" says nothing about a car service.
    """
    keep = load_json("redaction")["keep"]
    return word.lower() in keep["any_case"] or (word in keep["exactly"] and text != text.upper())


def _without_amount_words(text: str) -> str:
    found = [(match.start(), match.end(), match.group()) for match in _WORD.finditer(text)]
    sure = [_is_amount_word(word) and not _may_stay(word, text) for _, _, word in found]
    kept, end = [], 0
    for index, (start, stop, word) in enumerate(found):
        beside = any(sure[max(0, index - 1) : index] + sure[index + 1 : index + 2])
        goes = sure[index] or (beside and _is_amount_word(word))
        kept.append(text[end:start] + (" " if goes else word))
        end = stop
    return "".join(kept) + text[end:]


def _drop_amounts(text: str) -> str:
    without_accounts = _IBAN_PREFIX.sub(" ", without_contacts(text))
    without_digits = _amount_pattern().sub(" ", without_accounts)
    symbols = load_json("redaction")["currency_symbols"]
    kept = "".join(
        " " if ch in symbols or unicodedata.category(ch) in {"Nd", "Nl", "No", "Sc"} else ch
        for ch in without_digits
    )
    return _without_amount_words(kept)


def _tidy(text: str) -> str:
    joined = " ".join(_LONELY_MARK.sub(" ", text).split())
    joined = _SPACE_BEFORE_MARK.sub(r"\1", joined)
    return _REPEATED_MARK.sub(r"\1", joined).strip(_EDGES)


def _is_of_the_name(word: str, behind_a_name: bool) -> bool:
    """True for the given name and its surname. "Хозяину Серику" keeps its relation, "Сергей Внуков" has none."""
    if is_given_name(word):
        return True
    # In front of a name "Внуков" is a surname, "Хозяину" is who the person is.
    keeps = is_relation_word(word) and not word.lower().endswith(("ов", "ев"))
    return is_name_part(word) and (behind_a_name or not keeps)


def _without_name(segment: str) -> str | None:
    """Return the segment without its name, or None when it holds no listed name."""
    words = [word.strip(_EDGES) for word in segment.split()]
    names = [index for index, word in enumerate(words) if is_given_name(word)]
    if not names or len(words) > _MAX_NAME_WORDS:
        return None
    kept = [word for index, word in enumerate(words) if word and not _is_of_the_name(word, index > names[0])]
    if all(word.lower() in _PREPOSITIONS for word in kept):
        return ""
    return " ".join(kept)


def _drop_leading_name(text: str) -> str:
    found = _LEADING_SEGMENT.match(text)
    if not found:
        return text
    rest = _without_name(found.group(1))
    if rest is None:
        return text
    return f"{rest}, {found.group(2).strip()}" if rest else found.group(2)


def redact(text: str) -> str:
    """Return what may be sent to the language model. May be empty."""
    stripped = " ".join(_drop_amounts(clean(text)).split()).lstrip(_EDGES)
    # The comma is still there, so that "Данияр, 90000" is a name as well.
    return _tidy(_drop_leading_name(_SPACE_BEFORE_MARK.sub(r"\1", stripped)))
