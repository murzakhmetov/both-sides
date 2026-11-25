"""Every rule, limit and threshold of the prototype in one place.

Nothing in this file is secret. The Gemini key and the staff password are read
from the environment by the code that needs them (see ``bothsides/settings.py``).
"""

from __future__ import annotations

from datetime import date, time, timedelta, timezone

# --------------------------------------------------------------------------
# Decision rules
# --------------------------------------------------------------------------

#: Release only at this match probability or above.
RELEASE_PROBABILITY = 0.80

#: Hold below this probability, and only when the language model scored the pair.
HOLD_PROBABILITY = 0.35

#: Each answer needs at least this many informative words.
MIN_INFORMATIVE_WORDS = 2

#: More risky bank facts than this, and the comparison alone never releases.
MAX_RISKY_FACTS_FOR_RELEASE = 1

#: This many other receivers with a similar sender story stop a release.
REPEATED_STORY_RECEIVERS = 2
REPEATED_STORY_WINDOW = timedelta(days=30)
#: Character-trigram cosine from which two sender stories count as similar.
REPEATED_STORY_SIMILARITY = 0.60

# --------------------------------------------------------------------------
# Risky bank facts (seeded in the demo, bank systems in real life)
# --------------------------------------------------------------------------

#: A receiver account younger than this many days is risky.
NEW_ACCOUNT_DAYS = 14
#: This many first-time senders to the receiver today is risky.
MANY_FIRST_TIME_SENDERS = 3

# --------------------------------------------------------------------------
# Deadlines
# --------------------------------------------------------------------------

#: Kazakhstan has one time zone (UTC+5). A fixed offset avoids the ``tzdata``
#: package, which Windows Python does not ship.
BANK_TIMEZONE = timezone(timedelta(hours=5))

#: Law on Payments, article 25-1, paragraph 3-1: at most five working days,
#: counted from the date of suspension. The day of suspension itself is day 0.
HOLD_WORKING_DAYS = 5
#: The deadline is the end of the bank's working day on the fifth working day.
HOLD_DEADLINE_TIME = time(18, 0)

#: Public holidays and transferred days off that fall on weekdays. Saturdays
#: and Sundays are skipped anyway. 16 December 2026 is in the Law on Holidays;
#: the 2027 dates come from published calendars and must be checked
#: against the official production calendar before any real use.
PUBLIC_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2026, 12, 16),
        date(2027, 1, 1),
        date(2027, 1, 4),
        date(2027, 1, 7),
        date(2027, 3, 8),
        date(2027, 3, 15),
        date(2027, 3, 22),
        date(2027, 3, 23),
        date(2027, 3, 24),
        date(2027, 5, 3),
        date(2027, 5, 7),
        date(2027, 5, 10),
    }
)

#: A pair where somebody did not answer within this time goes to a person.
#: Much shorter than the legal limit, so that a person still has days left.
ANSWER_WINDOW = timedelta(hours=24)

#: A comparison that has not finished after this time goes to a person.
COMPARING_TIMEOUT = timedelta(seconds=60)

#: "I do not know this person" needs a second tap within this time.
DENY_CONFIRM_WINDOW = timedelta(seconds=4)

# --------------------------------------------------------------------------
# Language model
# --------------------------------------------------------------------------

#: Default Flash model. Override with the GEMINI_MODEL environment variable.
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
#: Wall-clock limit for one whole comparison call, in seconds.
GEMINI_TIMEOUT_SECONDS = 20.0
#: Limit for the one model-list request at start, in seconds.
GEMINI_LIST_TIMEOUT_SECONDS = 10.0
#: Online the list is part of a request of the start page, so there it may take only so long.
ONLINE_LIST_TIMEOUT_SECONDS = 4.0
#: Online a failed model-list request is made again after so many seconds.
GEMINI_CHECK_AGAIN_SECONDS = 20.0
#: The SDK retries several times by default; one attempt is enough here.
GEMINI_ATTEMPTS = 1
#: Asked in this order while the model is overloaded, until Google's list says which ones there are.
GEMINI_SPARE_MODELS = ("gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash")
#: So long a model that answered is asked first; then the main model gets its place back.
GEMINI_KEEP_SECONDS = 120.0
#: A model that has a spare behind it gets so many seconds of the wall-clock limit.
GEMINI_TRY_SECONDS = 6.0
#: A try with a spare model needs at least so much of the wall-clock limit.
GEMINI_NEXT_TRY_SECONDS = 4.0
#: Online, requests to Gemini: of one visitor a minute, of one address (a hall with one Wi-Fi) a
#: minute and a day, of one running copy a minute and a day.
#: One comparison is one request, up to four while models are overloaded. Beyond, the offline matcher answers.
ONLINE_GEMINI_SHARE = 16
ONLINE_GEMINI_ADDRESS = 60
ONLINE_GEMINI_ADDRESS_A_DAY = 1500
ONLINE_GEMINI_CALLS = 90
ONLINE_GEMINI_CALLS_A_DAY = 3000
#: "minimal" is rejected by gemini-3.8-flash, "low" is the fastest allowed level.
GEMINI_THINKING_LEVEL = "low"
GEMINI_MAX_OUTPUT_TOKENS = 1024
#: The staff note from the model is cut to this length.
MAX_NOTE_LENGTH = 200

# --------------------------------------------------------------------------
# Input limits
# --------------------------------------------------------------------------

MAX_ANSWER_LENGTH = 300
MIN_ANSWER_LENGTH = 2
MAX_PASSWORD_LENGTH = 200
MAX_BODY_BYTES = 8 * 1024
#: Request line, headers and body together.
MAX_REQUEST_BYTES = 64 * 1024
#: A request must be complete within this time; idle connections close after it.
REQUEST_SECONDS = 20.0
MAX_CONNECTIONS = 128
MAX_CONNECTIONS_PER_ADDRESS = 48
MAX_PATH_LENGTH = 200

# --------------------------------------------------------------------------
# Staff login
# --------------------------------------------------------------------------

MIN_STAFF_PASSWORD_LENGTH = 10
PBKDF2_ITERATIONS = 600_000
SESSION_LIFETIME = timedelta(hours=8)
MAX_STAFF_SESSIONS = 50
LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW = timedelta(minutes=10)
LOGIN_LOCKOUT = timedelta(minutes=5)

# --------------------------------------------------------------------------
# Rate limits (requests per window, per client address)
# --------------------------------------------------------------------------

RATE_WINDOW = timedelta(seconds=60)
#: Two phones, the stage and the demo page poll from one laptop.
RATE_LIMIT_READS = 1200
RATE_LIMIT_PAGES = 1200
RATE_LIMIT_WRITES = 120
#: Online the limits above hold for one visitor; a whole address may make so many requests.
ONLINE_READS_PER_ADDRESS = 24000
ONLINE_WRITES_PER_ADDRESS = 2400
RATE_LIMIT_LOGIN = 20
#: Public matcher for the landing page of Part 2.
RATE_LIMIT_TRY = 60
