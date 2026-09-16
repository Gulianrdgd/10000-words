"""Noun gender: article forms for display, and grading of "article + noun" answers.

Word.gender is "m" | "f" | "mf" (either, e.g. élève) | "mp" | "fp" (plural-only,
e.g. gens) | None (non-nouns, or nouns the dataset couldn't gender).
"""

# Common nouns starting with an aspirated h, which blocks elision
# ("le héros", not "l'héros"). Every other h-initial noun elides.
H_ASPIRE = {
    "hache", "haie", "haine", "hall", "halte", "halo", "hamac", "hamburger", "hameau",
    "hamster", "hanche", "handicap", "hangar", "hareng", "haricot", "harem", "harnais",
    "harpe", "harpie", "harpon", "hasard", "hâte", "hauteur", "havre", "hérisson", "hernie",
    "héron", "héros", "hêtre", "hibou", "hic", "hiérarchie", "hobby", "hockey", "holding",
    "homard", "honte", "hoquet", "horde", "hotte", "housse", "hublot", "hurlement", "hutte",
    "hachis", "harcèlement", "hacker", "huit", "haut", "houx", "huée",
}

MASCULINE_ARTICLES = {"le", "un"}
FEMININE_ARTICLES = {"la", "une"}
ARTICLES = MASCULINE_ARTICLES | FEMININE_ARTICLES | {"l'", "les", "des"}

_VOWELS = "aàâäeéèêëiîïoôöuùûüyœæ"


def elides(lemma: str) -> bool:
    first = lemma[:1].lower()
    if first == "h":
        return lemma.lower().split()[0] not in H_ASPIRE
    return first in _VOWELS


def is_gendered(gender: str | None) -> bool:
    """Whether a typed answer's article can be graded for gender."""
    return gender in ("m", "f")


def display_form(lemma: str, gender: str | None) -> str:
    """The form shown to the learner: 'le chat', 'la maison', "l'homme", 'les gens'."""
    if gender is None:
        return lemma
    if gender in ("mp", "fp"):
        return f"les {lemma}"
    if elides(lemma):
        return f"l'{lemma}"
    if gender == "mf":
        return f"le/la {lemma}"
    return f"{'le' if gender == 'm' else 'la'} {lemma}"


def production_answer(lemma: str, gender: str | None) -> str:
    """The answer a production card expects. Elided nouns use the indefinite
    article, since "l'" doesn't reveal gender: 'un homme', 'la maison'."""
    if not is_gendered(gender):
        return display_form(lemma, gender)
    if elides(lemma):
        return f"{'un' if gender == 'm' else 'une'} {lemma}"
    return display_form(lemma, gender)


def split_article(typed: str) -> tuple[str | None, str]:
    text = " ".join(typed.lower().replace("’", "'").split())
    if text.startswith("l'"):
        return "l'", text[2:].strip()
    head, _, rest = text.partition(" ")
    if head in ARTICLES and rest:
        return head, rest
    return None, text


def gender_correct(article: str | None, gender: str | None) -> bool | None:
    """True/False when the typed article shows the noun's gender, None when
    gender isn't graded for this word. A missing or elided article on a
    gendered noun counts as wrong: it hides the gender we're drilling."""
    if not is_gendered(gender):
        return None
    if gender == "m":
        return article in MASCULINE_ARTICLES
    return article in FEMININE_ARTICLES
