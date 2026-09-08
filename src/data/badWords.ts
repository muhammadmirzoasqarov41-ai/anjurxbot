// Comprehensive multilingual bad words database (Uzbek, Russian, English)

export const UZBEK_BAD_WORDS: string[] = [
  'ahmoq', 'tentak', 'haromi', 'iflos', 'jalap', 'it', 'chochqa',
  'dalbayob', 'dalbayeb', 'gandon', 'am', 'sikish', 'sikiw', 'sikay', 'sikey',
  'sikaman', 'sikdir', 'qotoq', 'qotoqbosh', 'qotoqbow', 'kot', 'kut', 'kottaq',
  'kutvachcha', 'kotvachcha', 'foxisha', 'fohisha', 'foxishaboz', 'foxishaxona',
  'jalabcha', 'jalablar', 'jallap', 'onangni', 'onangnisikey', 'oyingni',
  'padariga', 'padarlanat', 'betamiz', 'eshshak', 'hayvon', 'manjalaqi', 'shilta',
  'hezalak', 'xezalak', 'chupik', 'yiban', 'maraz', 'zormoq', 'qanjiq', 'qanjik',
  'amchalar', 'yalangoch', 'pornoxona', 'sekis', 'seks', 'siks', 'amini', 'yutvor',
  'chumo', 'mol', 'ifloscha', 'kotingga', 'amingga', 'siktir', 'suka'
];

export const RUSSIAN_BAD_WORDS: string[] = [
  'хуй', 'хуя', 'хуе', 'хуё', 'хуем', 'хуи', 'ахуеть', 'охуеть', 'нахуй', 'похуй',
  'пизда', 'пиздец', 'пиздит', 'спиздил', 'распиздяй', 'пиздабол', 'пиздюк',
  'ебать', 'ебал', 'выебу', 'ебло', 'еблан', 'ебучий', 'заебал', 'въебать',
  'блядь', 'блять', 'блядина', 'сука', 'сучка', 'сучара', 'падла', 'сволочь',
  'тварь', 'урод', 'пидор', 'пидорас', 'пидарас', 'гондон', 'гандон', 'мудак',
  'мудила', 'долбоеб', 'долбоёб', 'шалава', 'шлюха', 'шмара', 'потаскуха',
  'дрочить', 'дрочила', 'отсоси', 'отсос', 'член', 'залупа', 'хер', 'хрен',
  'сиськи', 'манда', 'порно', 'порнуха', 'секс', 'трахать', 'минет'
];

export const ENGLISH_BAD_WORDS: string[] = [
  'fuck', 'fucking', 'fucked', 'fucker', 'motherfucker', 'stfu',
  'bitch', 'bitches', 'bitching', 'asshole', 'assholes', 'cunt', 'cunts',
  'dick', 'dicks', 'dickhead', 'cock', 'cocks', 'pussy', 'pussies',
  'bastard', 'bastards', 'whore', 'whores', 'slut', 'sluts', 'retard',
  'dumbass', 'bullshit', 'dipshit', 'faggot', 'blowjob', 'handjob',
  'porn', 'porno', 'pornography', 'xxx', 'nudes', 'naked', 'boobs', 'dildo',
  'masturbate', 'masturbation', 'cum', 'cumshot', 'anal', 'horny',
  'penis', 'vagina', 'sex', 'sexy'
];

export const ALL_BAD_WORDS: string[] = Array.from(
  new Set([...UZBEK_BAD_WORDS, ...RUSSIAN_BAD_WORDS, ...ENGLISH_BAD_WORDS])
);
