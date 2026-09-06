"""Session memory — RAM only. Nothing is ever written to disk.

The original promised: "MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE."
We honor it by architecture: everything here is dataclasses in the Engine
process, gone at exit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MOOD_KEYWORDS: dict[str, tuple[int, str]] = {
    "great": (2, "GREAT"),
    "happy": (2, "HAPPY"),
    "excited": (2, "EXCITED"),
    "wonderful": (2, "WONDERFUL"),
    "good": (1, "GOOD"),
    "better": (1, "BETTER"),
    "calm": (1, "CALM"),
    "proud": (1, "PROUD"),
    "fine": (0, "FINE"),
    "okay": (0, "OKAY"),
    "ok": (0, "OKAY"),
    "tired": (-1, "TIRED"),
    "stressed": (-1, "STRESSED"),
    "anxious": (-1, "ANXIOUS"),
    "worried": (-1, "WORRIED"),
    "nervous": (-1, "NERVOUS"),
    "angry": (-1, "ANGRY"),
    "mad": (-1, "ANGRY"),
    "frustrated": (-1, "FRUSTRATED"),
    "overwhelmed": (-1, "OVERWHELMED"),
    "sad": (-2, "SAD"),
    "lonely": (-2, "LONELY"),
    "depressed": (-2, "DEPRESSED"),
    "hopeless": (-2, "HOPELESS"),
    "awful": (-2, "AWFUL"),
    "terrible": (-2, "TERRIBLE"),
    "horrible": (-2, "HORRIBLE"),
}

TOPIC_KEYWORDS = [
    "work", "job", "boss", "family", "love", "relationship", "health",
    "sleep", "money", "school", "friend", "future", "death", "anxiety",
    "marriage", "kids", "divorce", "career", "retirement",
]


@dataclass
class Fact:
    key: str
    value: str
    turn: int


@dataclass
class MoodEntry:
    turn: int
    score: int
    label: str


@dataclass
class JournalEntry:
    idx: int
    turn: int
    title: str
    text: str


@dataclass
class SessionMemory:
    """Everything the doctor knows about this session. RAM only."""

    name: str | None = None
    age: int | None = None
    facts: list[Fact] = field(default_factory=list)
    moods: list[MoodEntry] = field(default_factory=list)
    journal: list[JournalEntry] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    turns: int = 0
    user_words: int = 0
    sbaitso_words: int = 0
    last_response: str = ""

    # ------------------------------------------------------------------
    def note_user(self, text: str) -> None:
        self.turns += 1
        self.user_words += len(text.split())
        low = text.lower()
        self._extract_facts(low)
        self._extract_mood(low)
        self._extract_topics(low)

    def _extract_facts(self, low: str) -> None:
        def add(key: str, value: str) -> None:
            value = value.strip(" .!?\"'").upper()
            if not value or len(value) > 60:
                return
            if any(f.key == key and f.value == value for f in self.facts):
                return
            self.facts.append(Fact(key, value, self.turns))

        m = re.search(r"\bmy name is ([a-z' ]+)", low)
        if m and not self.name:
            add("NAME", m.group(1))
        m = re.search(r"\bi(?:'m| am) (\d{1,3}) years old\b", low)
        if m and not self.age:
            self.age = int(m.group(1))
            add("AGE", m.group(1) + " YEARS OLD")
        m = re.search(r"\bi work as an? ([a-z ]+)", low) or re.search(
            r"\bmy job is ([a-z ]+)", low
        )
        if m:
            add("JOB", m.group(1))
        m = re.search(r"\bi work at ([a-z ]+)", low)
        if m:
            add("EMPLOYER", m.group(1))
        m = re.search(r"\bmy boss(?:'s name)? is ([a-z ]+)", low)
        if m:
            add("BOSS", m.group(1))
        m = re.search(r"\bi live in ([a-z ]+)", low)
        if m:
            add("HOME", m.group(1))

    def _extract_mood(self, low: str) -> None:
        for word, (score, label) in MOOD_KEYWORDS.items():
            if re.search(rf"\b{word}\b", low):
                self.moods.append(MoodEntry(self.turns, score, label))
                return

    def _extract_topics(self, low: str) -> None:
        for topic in TOPIC_KEYWORDS:
            if re.search(rf"\b{topic}\b", low) and topic not in self.topics:
                self.topics.append(topic)

    # ------------------------------------------------------------------
    def add_mood(self, score: int, label: str) -> None:
        self.moods.append(MoodEntry(self.turns, score, label))

    def add_journal(self, title: str, text: str) -> JournalEntry:
        entry = JournalEntry(
            idx=len(self.journal) + 1, turn=self.turns,
            title=title.upper(), text=text,
        )
        self.journal.append(entry)
        return entry

    def mood_trend(self) -> str:
        if len(self.moods) < 2:
            return "TOO EARLY TO SAY" if self.moods else "UNKNOWN (YOU HAVE NOT TOLD ME)"
        scores = [m.score for m in self.moods]
        half = max(1, len(scores) // 2)
        early = sum(scores[:half]) / half
        late = sum(scores[half:]) / max(1, len(scores) - half)
        diff = late - early
        if diff > 0.5:
            return "LIFTING"
        if diff < -0.5:
            return "DESCENDING"
        return "STEADY"

    def mood_chart(self) -> list[str]:
        if not self.moods:
            return [" NO MOODS LOGGED YET. TELL ME HOW YOU FEEL."]
        lines = [" MOOD LOG (THIS SESSION ONLY — RAM ONLY)"]
        for m in self.moods:
            bar = "\u2593" * (abs(m.score) * 5) or "\u2591"
            lines.append(f" T{m.turn:03d}  {m.label:<13} {bar}")
        lines.append(f" TREND: {self.mood_trend()}")
        return lines

    def snapshot_lines(self) -> list[str]:
        """The DIR listing — a virtual DOS filesystem over RAM."""
        lines = [
            " Volume in drive C is SBAITSO",
            " Directory of C:\\SBAITSO",
            "",
        ]
        lines.append(f" MEMORY   DAT     {len(self.facts):>4} FACT(S)      [RAM ONLY]")
        lines.append(f" MOOD     LOG     {len(self.moods):>4} ENTRY(IES)   [RAM ONLY]")
        lines.append(f" JOURNAL  \\       {len(self.journal):>4} ENTRY(IES)   [RAM ONLY]")
        total = len(self.facts) + len(self.moods) + len(self.journal)
        lines.append(f"        {total} file(s) on a drive that does not exist")
        return lines
