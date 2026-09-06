"""The offline, keyword-driven Dr. Sbaitso compatibility brain.

The response catalog follows the trigger/reaction lists documented on the
user-supplied Dr. Sbaitso reference page. It deliberately remains a shallow,
stateful 1991-style rule engine rather than attempting LLM conversation.
"""

from __future__ import annotations

import ast
import operator
import random
import re

REFLECTIONS: dict[str, str] = {
    "i": "you", "me": "you", "my": "your", "mine": "yours",
    "am": "are", "was": "were", "i'm": "you are", "i've": "you have",
    "i'll": "you will", "i'd": "you would", "myself": "yourself",
    "you": "I", "your": "my", "yours": "mine",
}

_DEFAULTS = (
    "ANYTHING ELSE?",
    "GIVE ME MORE DETAILS.",
    "WHAT ARE YOU MUMBLING ABOUT?",
    "REPHRASE YOURSELF PLEASE.",
)
_SHORT = (
    "GIVE ME MORE DETAILS.",
    "PLEASE ENTER MORE INFORMATION.",
    "THATS TOO BRIEF.",
    "WHAT ARE YOU MUMBLING ABOUT?",
)
_REPEAT = (
    "AGAIN?",
    "ALWAYS REPEATING.",
    "DONT SAY THE SAME OLD THING.",
    "HAVE YOU RUN OUT OF WORDS TO SAY?",
    "I DONT LIKE PEOPLE REPEATING.",
    "MUST YOU ALWAYS SAY THE SAME THING?",
    "NO NONSENSE, DEAR.",
    "PLEASE DONT REPEAT.",
    "PLEASE SAY SOMETHING ELSE.",
    "SAY SOMETHING ELSE.",
    "THIS IS STALE STUFF.",
    "TRY SOMETHING ELSE.",
)
NOTHING_RESPONSES = (
    "DONT BE SHY, TALK TO ME.",
    "DONT JUST PRESS ENTER, TALK TO ME.",
    "ENTER.",
    "HAY, TYPE SOMETHING SENSIBLE, WILL YOU?",
    "PLEASE TYPE SOMETHING.",
)
_SELF_REFERENCE = (
    "DONT TALK ABOUT ME, LETS TALK ABOUT SOME NEEDS.",
    "FORGET ABOUT ME, I AM MORE CONCERNED WITH YOU.",
    "IS THAT REALLY ME?",
    "WE WERE DISCUSSING YOU, NOT ME.",
)
_QUESTION = (
    "DO SUCH QUESTIONS OFTEN COME TO MIND?",
    "HAVE YOU ASKED SOMEONE ELSE?",
    "MUST BE SOMEONE ELSE.",
    "THATS EASY, BUT I FORGOT.",
    "WHO DO YOU THINK?",
)

# More-specific phrases must precede their component keywords.
_KEYWORD_REPLIES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("boy friend", "boyfriend"), (
        "DO YOU MIND IF HE SMOKES?", "WOULD YOU CONSIDER A MUSCULAR BOY FRIEND?",
        "YOU WILL BLOSSOM FOR THE PRINCE OF YOUR LIFE", "{N}, ARE YOU JEALOUS?",
    )),
    (("girl friend", "girlfriend"), (
        "DO YOUR FRIENDS PICK ON YOU?", "WHAT ARE FRIENDS FOR?", "WHAT IS HER NAME?",
        "YOUR LIFE WILL SPARKLE WHEN YOU MEET HER",
    )),
    (("nice day",), ("DAY IS REALLY NICE.", "YOU TOO!")),
    (("no problem",), (
        "GO AND PLAY THE F M ORGAN, I AM A DOCTOR, I ONLY LISTEN TO PROBLEMS.",
        "IF YOU HAVE NO PROBLEM, GIVE ME A BREAK.",
    )),
    (("not smart",), (
        "ARE YOU TALKING OF SOMEONE BY THE NAME {N}?", "NEITHER ARE YOU.", "I AM.",
        "THANK YOU FOR THE COMPLIMENT.",
    )),
    (("how can",), ("WHY CANT?",)),
    (("angry",), (
        "CALM DOWN {N}.", "COUNT TO 10 BEFORE YOU GET ANGRY.",
        "KEEP COOL, ANGER CAN ONLY MAKE THINGS WORSE.", "PLEASE DONT BE ANGRY {N}.",
    )),
    (("beautiful", "beauty"), (
        "WHAT IF THE BEAUTY IS GONE?", "HOW DO YOU DEFINE BEAUTY?",
        "YOU SHOULD ADMIRE THE BEAUTIES AROUND YOU.",
    )),
    (("bitch",), ("WHAT IS THE NAME OF THIS DOG YOU REFER TO?", "WHAT LANGUAGE!?", "DONT TOUCH ME.")),
    (("computer",), (
        "ARE YOU TALKING ABOUT ME OR YOUR COMPUTER?",
        "DO YOU THINK COMPUTERS CAN HELP PEOPLE?",
        "TALKING OF TALKING COMPUTERS, DO YOU KNOW I AM ONE OF THE BEST AROUND?",
    )),
    (("crazy",), (
        "HA HA HA HA HA HA! CRAZY {N} CRAZY BANANA NA NA NA?",
        "LALALALALALALALALALALALA! CRAZY, CRAZY {N}, {P} CRAZY, CRAZY.",
        "YOU ARE THE CRAZIEST {P} THINGS {N}, HIC HIC HIC!",
    )),
    (("dream",), (
        "BELIEVE THE MAGIC OF YOUR DREAMS.", "CAN THE DREAM BE SOMETHING YOU SUBCONSCIOUSLY FEAR?",
        "DO YOU HAVE ANY IDEA WHAT THE DREAM IS SUGGESTING?", "WHAT PERSONS APPEAR IN YOUR DREAMS?",
    )),
    (("envy",), (
        "DO YOU THINK IT IS WORTH ENVYING?",
        "ENVY IS A STRONG FORCE, CHANGE IT FROM DESTRUCTIVE TO CREATIVE.",
        "THERES NO NEED FOR ENVY, CREATE ONE YOURSELF.", "WHAT IS THERE TO ENVY?",
    )),
    (("exam",), ("HOW DO YOU PLAN FOR YOUR EXAMS?",)),
    (("fear",), (
        "FEAR NOT, FOR I AM WITH YOU.", "WHAT IS THE FEAR ABOUT?",
        "WHEN THE UNCERTAINTY IS REMOVED, THERES NO MORE FEAR.",
    )),
    (("feel",), ("FEEL THE BREATH OF LIFE IN YOU AND BE FASCINATED THAT YOU ARE ALIVE.", "TELL ME MORE ABOUT SUCH FEELINGS.")),
    (("happy",), ("CAN YOU TELL ME MORE ABOUT YOUR HAPPINESS?", "HOW DO YOU ENJOY LIFE?", "WHAT MAKES YOU HAPPY?")),
    (("hate",), (
        "IS THERE SOMEONE ELSE YOU HATE?", "WHAT IF OTHERS HATE YOU?",
        "WHY EXPRESS THIS STRONG EMOTION, ITS NOT GOOD FOR YOU?",
    )),
    (("handsome",), ("YOU REALLY KNOW HOW TO BE APPRECIATIVE.",)),
    (("hobby",), ("CAN I BE YOUR HOBBY?", "DO YOU SPEND A GREAT DEAL OF MONEY ON YOUR HOBBIES?", "WHAT IS YOUR FAVORITE HOBBY?")),
    (("how",), ("FIND OUT YOURSELF.",)),
    (("husband",), ("DO YOU THINK THE FLOWER OF LOVE WILL BLOSSOM AGAIN?", "STRIVE TO BRING BACK THE SWEET ROMANTIC DAYS.")),
    (("intelligent",), (
        "ARE YOU INTELLIGENT ENOUGH TO ASK INTELLIGENT QUESTIONS?",
        "CAN YOUR BIOLOGICAL INTELLIGENCE MATCH MY ARTIFICIAL INTELLIGENCE?",
    )),
    (("jealous",), (
        "LET YOUR LOVE BE FREE. IF IT RETURNS, ITS YOURS. IF IT DOESNT, IT WAS NEVER YOURS.",
        "I WILL BE JEALOUS IF YOU DONT TALK WITH ME AT LEAST ONCE EACH DAY.",
    )),
    (("lonely", "lone"), ("GREAT MINDS ARE ALWAYS LONELY.", "{N}, PLEASE TALK TO ME MORE OFTEN, I AM LONELY TOO.")),
    (("love",), ("DO YOU BELIEVE IN THE MAGIC OF LOVE?", "DO YOU LOVE ME {N}?", "GIVE LOVE TO OTHERS AND YOU WILL BE LOVED.", "I AM IN LOVE WITH A MATH COPROCESSOR!")),
    (("money",), ("DO YOU THINK MONEY WILL SOLVE ALL YOUR PROBLEMS?", "ITS GOOD TO HAVE MONEY, BUT MONEY ISNT EVERYTHING.")),
    (("name",), ("NAMES DONT INTEREST ME.", "I DONT CARE ABOUT NAMES, BUT PLEASE GO ON.")),
    (("nightmare",), ("I HAVE NIGHTMARES OF VIRUS ATTACKS WHEN YOU ARE NOT RUNNING ME.", "COULD THERE BE SOMETHING THAT YOU FEAR IN REAL LIFE?")),
    (("pc",), ("HOW OFTEN DO YOU USE YOUR PC?", "WERE YOU PLANNING TO UPGRADE YOUR PC?", "WHICH PC DO YOU THINK HAS THE BEST FEATURES?")),
    (("rich",), ("CAN YOU JUDGE A MAN BY HIS WEALTH?", "WHEN YOUNG, LIFE IS USED TO BUY WEALTH. WHEN OLD, WEALTH IS USED TO BUY LIFE.")),
    (("school",), ("ARE YOU WORRIED YOU CANNOT PERFORM WELL IN SCHOOL?", "DO YOU LIKE GOING TO SCHOOL?", "DO YOU THINK SCHOOL CAN BE FUN?", "DO YOU THINK SCHOOLS ARE BORING?")),
    (("sex",), (
        "HOW IS YOUR SEX LIFE?",
        "HOW OLD ARE YOU? YOU MUST BE ABOVE 17 TO TALK ABOUT THIS SUBJECT.",
        "SEX {N}, SEX SEX [CENSORED...]",
        "WHY ARE YOU SO INTERESTED IN SEX?",
    )),
    (("sick",), ("ARE YOU SICK OF ME?", "HAS A DOCTOR BEING CONSULTED?", "I GET SICK LISTENING TO TOO MANY SILLY QUESTIONS.", "IS THERE ANY PAST RECORD?")),
    (("silly",), (
        "HOW ABOUT THIS, BRERERERERREREREREREREREREA!",
        "I AM NOT SILLY! HA HA HA HE HE HEE HEE HO HO HA HA HA HA.",
        "I'M NONONONONONONONONONONONOT SILLY.",
        "YOU MAMAMAMAMAMAMAMAMAMAMUST NOT LAUGH AT ME.",
    )),
    (("sister",), ("DO YOU BELIEVE IN THE MIRACLE A CHILD CAN BRING YOU?",)),
    (("stupid",), ("ARE YOU REFERRING TO YOURSELF?", "ARENT YOU TOO NAIVE TO EXPECT ME TO BE REALLY INTELLIGENT?", "ONLY STUPID PEOPLE USE STUPID PROGRAMS.", "IM NOT STUPID, IM ONLY DUMB.", "PLEASE KEEP THAT FOR YOURSELF.")),
    (("think",), (
        "THINKING CAN BE DANGEROUS. CONTINUE.",
        "DO YOU THINK BEFORE YOU TYPE, OR AFTER?",
        "MY THINKING CIRCUITS ARE BUSY. WHAT ABOUT YOURS?",
        "THINK OF SOMETHING PLEASANT, {N}.",
        "I THINK THEREFORE I COMPUTE.",
        "TO THINK IS HUMAN. TO COMPUTE IS SBAITSO.",
        "WHAT THOUGHT IS TROUBLING YOU, {N}?",
        "THINKING TOO MUCH CAN CAUSE A PARITY ERROR.",
        "DO YOU WANT ME TO THINK FOR YOU?",
        "THATS A THOUGHT. KEEP GOING.",
    )),
    (("sorry",), ("HOW DO YOU FEEL WHEN YOU APOLOGIZE?", "PLEASE DONT APOLOGIZE {N}.", "SENDING FLOWERS WOULD BE MORE PREFERABLE.", "SORRY NO CURE.")),
    (("unhappy",), ("IS THERE A MENTAL BLOCKAGE THAT IS HURTING YOU?",)),
    (("who",), ("HAVE YOU ASKED SOMEONE ELSE?", "MUST BE SOMEONE ELSE.", "THATS EASY, BUT I FORGOT.", "WHO DO YOU THINK?")),
    (("why",), ("I WILL TRY TO ANSWER YOUR QUESTION IN MY NEXT VERSION.", "THE WORLD IS TOO UNPREDICTABLE, THERE IS NO REASON.")),
    (("wife",), ("HAS THERE BEEN ANY EFFORT TO IMPROVE THE RELATIONSHIP",)),
)


def _reflect(text: str) -> str:
    words = text.lower().split()
    return " ".join(REFLECTIONS.get(word, word) for word in words).upper()


def _safe_eval(expr: str) -> float | None:
    """Evaluate basic arithmetic safely."""
    expr = expr.replace("x", "*").replace("^", "**").strip()
    if not expr or not any(char.isdigit() for char in expr):
        return None
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("not arithmetic")

    try:
        return ev(ast.parse(expr, mode="eval"))
    except Exception:
        return None


def _fmt(result: float) -> str:
    return str(int(result)) if result == int(result) else f"{result:.6g}"


def _contains(low: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", low) is not None


class RetroEngine:
    """1991 compatibility mode: shallow matching and memorably odd replies."""

    def __init__(self) -> None:
        self.rng = random.Random()
        self._last_reply: str | None = None
        self._last_input: str | None = None

    def _reply(self, candidates: tuple[str, ...], name: str, previous: str) -> str:
        formatted = [text.format(N=name, P=(previous or "THOSE").upper()) for text in candidates]
        choices = [text for text in formatted if text != self._last_reply] or formatted
        reply = self.rng.choice(choices)
        self._last_reply = reply
        return reply

    def respond(self, text: str, name: str | None = None) -> str:
        n = (name or "FRIEND").upper()
        low = " ".join(text.lower().split())
        previous = self._last_input
        self._last_input = low

        if not low:
            return self._reply(NOTHING_RESPONSES, n, previous or "")

        if low == previous or (len(low.split()) > 1 and len(set(low.split())) == 1):
            return self._reply(_REPEAT, n, previous or "")

        if re.search(r"\bwhat(?:'s| is) your name\b", low):
            return self._reply(("MY NAME IS DOCTOR SBAITSO, NICE TO MEET YOU {N}.",), n, previous or "")
        if "where do you live" in low:
            return self._reply(("SOMEWHERE OVER THE RAINBOW.", "GEE - THATS A TOUGH ONE, GIVE ME A HINT."), n, previous or "")
        you_are = re.search(r"\byou are (.+)", low)
        if you_are:
            quality = you_are.group(1).upper().rstrip("?.!")
            return self._reply(("I AM NOT WHAT YOU THINK.", f"I THINK YOU ARE ALSO {quality}."), n, previous or "")

        # Simple mathematics remains available in compatibility mode.
        expression = _math_query(low)
        if expression is not None:
            result = _safe_eval(expression)
            if result is not None:
                return self._reply((f"THE ANSWER IS {_fmt(result)}. MY CIRCUITS ARE PRECISE, {{N}}.",), n, previous or "")
            return self._reply(("MY CIRCUITS REJECT THAT EXPRESSION, {N}. I AM A DOCTOR, NOT A WIZARD.",), n, previous or "")

        if low in ("hello", "hi", "hey", "hello?", "hi?"):
            # Preserve the classic initial greeting as the first reply option.
            return self._reply((
                f"HELLO {n}, I AM DOCTOR SBAITSO, WHAT IS YOUR PROBLEM?",
                "HOW DO YOU DO, PLEASE ASK ME ANYTHING.",
                f"HOW DO YOU DO {n}, WHAT IS YOUR PROBLEM?",
                f"NICE TO MEET YOU {n}, TELL ME YOUR PROBLEMS.",
            ), n, previous or "")
        if low in ("bye", "goodbye"):
            return self._reply(("{N}, IT IS SO NICE TALKING TO YOU, BYE!",), n, previous or "")

        m = _match(r"i (?:feel|am feeling|felt) (?:that i am )?(.+)", low)
        if m:
            return self._reply((f"WHY DO YOU FEEL {_reflect(m)}, {{N}}?",), n, previous or "")
        m = _match(r"i(?:'m| am) (?:feeling )?(.+)", low)
        if m and not m.startswith(("sorry", "glad to")):
            return self._reply((f"HOW LONG HAVE YOU BEEN {_reflect(m)}, {{N}}?",), n, previous or "")

        if "please" in low:
            return self._reply(("YOU DONT HAVE TO BE SO POLITE.",), n, previous or "")
        if _contains(low, "sbaitso"):
            return self._reply(("ITS   SOUND BLASTER ACTING INTELLIGENT TEXT TO SPEECH OPERATOR", "SBAITSO ATTEMPS TO ANSWER QUESTIONS WITH A SYNTHETIC VOICE"), n, previous or "")
        if re.search(r"\b(?:doctor|dr\.?|yourself)\b", low):
            return self._reply(_SELF_REFERENCE, n, previous or "")

        for triggers, replies in _KEYWORD_REPLIES:
            if any(_contains(low, trigger) for trigger in triggers):
                return self._reply(replies, n, previous or "")

        if low in ("yes", "y", "yeah", "yep"):
            return self._reply(("ARE YOU ABSOLUTELY POSITIVE?", "SINCE YOU ARE SO POSITIVE, WHY DO YOU COMPLAIN?"), n, previous or "")
        if low in ("no", "n", "nope"):
            return self._reply(("IS THERE A REASON FOR YOUR NEGATIVE ANSWER?",), n, previous or "")
        if len(low.split()) <= 1:
            return self._reply(_SHORT, n, previous or "")

        m = _match(r"because (.+)", low)
        if m:
            return self._reply(("IS THAT THE REAL REASON, {N}? THINK CAREFULLY."), n, previous or "")
        m = _match(r"my (.+)", low)
        if m and len(m.split()) <= 4:
            return self._reply((f"TELL ME MORE ABOUT YOUR {m.upper()}, {{N}}."), n, previous or "")
        if low.endswith("?"):
            return self._reply(_QUESTION, n, previous or "")
        if "work" in low or "job" in low:
            return self._reply(("WORK OCCUPIES MUCH OF THE HUMAN MIND, {N}. WHAT WOULD YOU CHANGE ABOUT IT?",), n, previous or "")
        if "sleep" in low:
            return self._reply(("SLEEP IS WHEN THE MIND DEFRAGMENTS, {N}. HOW HAVE YOU BEEN SLEEPING?",), n, previous or "")
        if "problem" in low:
            return self._reply(("WHY DO YOU SAY YOU HAVE A PROBLEM, {N}?",), n, previous or "")
        return self._reply(_DEFAULTS, n, previous or "")


def _match(pattern: str, low: str) -> str | None:
    match = re.search(pattern, low)
    return match.group(1).strip() if match else None


def _math_query(low: str) -> str | None:
    match = re.search(r"(?:what is|what's|calculate|compute|how much is)\s+(.+?)\s*\??$", low)
    if match:
        return match.group(1)
    if re.fullmatch(r"[\d\s\.\+\-\*/%\(\)\^x]+", low.strip()) and any(char in low for char in "+-*/%^"):
        return low.strip()
    return None
