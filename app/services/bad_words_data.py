"""
Comprehensive Bad Words, Offensive Terms, and 18+ Filter Database.
Contains curated Uzbek, Russian, and English vulgar, insulting, and adult terms.
"""
from typing import List

# Uzbek profanities, insults, offensive slurs, and 18+ terms
UZBEK_BAD_WORDS: List[str] = [
    "ahmoq", "axmoq", "tentak", "haromi", "iflos", "jalap", "it", "chochqa",
    "dalbayob", "dalbayeb", "gandon", "am", "sikish", "sikiw", "sikay", "sikey",
    "sikaman", "sikdir", "siktir", "siktirvachcha", "qotoq", "qotoqbosh", "qotoqbow",
    "kot", "kut", "kottaq", "kutvachcha", "kotvachcha", "foxisha", "fohisha",
    "foxishaboz", "foxishaxona", "jalabcha", "jalablar", "jallap", "onangni",
    "onangnisikey", "oyingni", "padariga", "padarlanat", "betamiz", "eshshak",
    "hayvon", "manjalaqi", "shilta", "hezalak", "xezalak", "chupik", "yiban",
    "maraz", "zormoq", "qanjiq", "qanjik", "amchalar", "yalangoch", "pornoxona",
    "sekis", "seks", "siks", "amini", "yutvor", "chumo", "mol", "ifloscha",
    "kotingga", "kotingnibos", "amingga", "suka", "bort", "itvachcha", "sharmanda"
]

# Russian profanities (мат), insults, and 18+ terms
RUSSIAN_BAD_WORDS: List[str] = [
    "хуй", "хуя", "хуе", "хуё", "хуем", "хуи", "ахуеть", "охуеть", "нахуй", "похуй",
    "пизда", "пиздец", "пиздит", "спиздил", "распиздяй", "пиздабол", "пиздюк",
    "ебать", "ебал", "выебу", "ебло", "еблан", "ебучий", "заебал", "въебать",
    "блядь", "блять", "блядина", "сука", "сучка", "сучара", "падла", "сволочь",
    "тварь", "урод", "пидор", "пидорас", "пидарас", "гондон", "гандон", "мудак",
    "мудила", "долбоеб", "долбоёб", "шалава", "шлюха", "шмара", "потаскуха",
    "дрочить", "дрочила", "отсоси", "отсос", "член", "залупа", "хер", "хрен",
    "сиськи", "манда", "порно", "порнуха", "секс", "трахать", "минет",
    "залупоголовый", "долбарик", "чмо", "мразь"
]

# English profanities, offensive slurs, and 18+ terms
ENGLISH_BAD_WORDS: List[str] = [
    "fuck", "fucking", "fucked", "fucker", "motherfucker", "stfu",
    "bitch", "bitches", "bitching", "asshole", "assholes", "cunt", "cunts",
    "dick", "dicks", "dickhead", "cock", "cocks", "pussy", "pussies",
    "bastard", "bastards", "whore", "whores", "slut", "sluts", "retard",
    "dumbass", "bullshit", "dipshit", "faggot", "blowjob", "handjob",
    "porn", "porno", "pornography", "xxx", "nudes", "naked", "boobs", "dildo",
    "masturbate", "masturbation", "cum", "cumshot", "anal", "horny",
    "penis", "vagina", "sex", "sexy", "deepthroat", "gangbang"
]

# Combined and deduplicated default list
ALL_DEFAULT_BAD_WORDS: List[str] = list(dict.fromkeys(
    UZBEK_BAD_WORDS + RUSSIAN_BAD_WORDS + ENGLISH_BAD_WORDS
))
