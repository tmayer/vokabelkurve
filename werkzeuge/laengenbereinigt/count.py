# Zählt im niederländischen OpenSubtitles-Korpus, wie oft jeder Tatoeba-Satz
#  (a) als ganze Untertitelzeile vorkommt,
#  (b) als zusammenhängende Wortfolge irgendwo in einer Zeile vorkommt,
# und wie oft die 2- und 3-Wort-Bausteine der Sätze vorkommen.
# Aufruf im Datenordner:  VK_LANG=nld python3 count.py os.txt.gz   (bzw. VK_LANG=fra)
import collections, gzip, json, os, pickle, re, sys
from multiprocessing import Pool

LANG = os.environ.get('VK_LANG', 'nld')
TOK = {
    'nld': re.compile(r"[a-z0-9à-öø-ÿ]+(?:'[a-z]+)?|'[a-z]+"),    # z'n, 's, 't bleiben ganz
    'fra': re.compile(r"aujourd'hui|[a-z0-9à-öø-ÿœæ]+'?"),       # c'est -> c' + est (wie in fr_50k)
}[LANG]

def tok(s):
    s = s.lower().replace('’', "'").replace('‘', "'").replace('`', "'")
    return TOK.findall(s)

def load_candidates():
    nl = {}
    for l in open(LANG + '_sentences.tsv', encoding='utf-8'):
        i, _, t = l.rstrip('\n').split('\t', 2)
        nl[i] = t
    have = {a for a, b in (l.split() for l in open(LANG + '-deu_links.tsv'))}
    cands = {}
    for i in have:
        if i in nl:
            t = tuple(tok(nl[i]))
            if 1 <= len(t) <= 14:
                cands.setdefault(t, []).append(i)
    return cands

CANDS = load_candidates()
KEYS = set(CANDS)
for t in list(CANDS):
    for n in (2, 3):
        for i in range(len(t) - n + 1):
            KEYS.add(t[i:i + n])
# Präfix-Abbruch ist nur korrekt, wenn jedes Präfix eines Kandidaten in KEYS liegt
for t in list(CANDS):
    for n in range(2, len(t)):
        KEYS.add(t[:n])
MAXN = 14

def work(lines):
    line_hits = collections.Counter()
    seq_hits = collections.Counter()
    ntok = 0
    for line in lines:
        t = tok(line)
        T = len(t)
        ntok += T
        if not T:
            continue
        tt = tuple(t)
        if tt in CANDS:
            line_hits[tt] += 1
        for i in range(T):
            for n in range(1, min(MAXN, T - i) + 1):
                k = tt[i:i + n]
                if k in KEYS:
                    seq_hits[k] += 1
                elif n >= 2:
                    break  # kein längerer Kandidat kann mit einem unbekannten Präfix beginnen
    return line_hits, seq_hits, len(lines), ntok

def chunks(path, size=20000):
    buf = []
    with gzip.open(path, 'rt', encoding='utf-8', errors='replace') as f:
        for l in f:
            buf.append(l)
            if len(buf) >= size:
                yield buf
                buf = []
    if buf:
        yield buf

if __name__ == '__main__':
    L, S = collections.Counter(), collections.Counter()
    nl = nt = 0
    with Pool(14) as p:
        for k, (a, b, c, d) in enumerate(p.imap_unordered(work, chunks(sys.argv[1]), chunksize=2)):
            L.update(a); S.update(b); nl += c; nt += d
            if k % 500 == 0:
                print(k, nl, nt, flush=True)
    pickle.dump({'line': L, 'seq': S, 'lines': nl, 'tokens': nt, 'cands': CANDS}, open('counts.pkl', 'wb'))
    print('fertig', nl, 'Zeilen', nt, 'Tokens')
