# Bewertet Tatoeba-Sätze längenbereinigt nach Untertitel-Häufigkeit und wählt ein Deck aus.
# Aufruf im Datenordner nach count.py:  VK_LANG=nld python3 score.py 1000
import collections, csv, math, os, pickle, re, statistics, sys
from count import tok, LANG

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
CONF = {
    # B1: ganze Sätze, gern mit Nebensatz; nur Sätze mit mindestens einem Wort jenseits der Top 300
    'nld': dict(minlen=5, maxlen=12, learn_lo=300, freq='nl_50k.txt', lang='Niederländisch',
                out='niederlaendisch_b1_saetze_1000.csv', keep={'u', 'uw'}),
    # Alltagswendungen von kurz bis lang
    'fra': dict(minlen=2, maxlen=12, learn_lo=100, freq='fr_50k.txt', lang='Französisch',
                out='franzoesisch_wendungen_laengenbereinigt_1000.csv', keep=set()),
}[LANG]
MINLEN, MAXLEN = CONF['minlen'], CONF['maxlen']
MAX_RANK = 8000                 # keine seltenen Wörter
LEARN_LO = CONF['learn_lo']     # Wörter ab diesem Rang zählen als Lernwörter
MAX_PER_WORD = 3                # höchstens so viele Sätze pro Lernwort

d = pickle.load(open('counts.pkl', 'rb'))
LINE, SEQ, CANDS, TOKENS = d['line'], d['seq'], d['cands'], d['tokens']

nl, de = {}, {}
for l in open(LANG + '_sentences.tsv', encoding='utf-8'):
    i, _, t = l.rstrip('\n').split('\t', 2); nl[i] = t
links = collections.defaultdict(list)
for l in open(LANG + '-deu_links.tsv'):
    a, b = l.split(); links[a].append(b)
need = {b for v in links.values() for b in v}
for l in open('deu_sentences.tsv', encoding='utf-8'):
    i, _, t = l.rstrip('\n').split('\t', 2)
    if i in need: de[i] = t

rank = {}
for k, l in enumerate(open(CONF['freq'], encoding='utf-8'), 1):
    w = l.split()[0]
    rank.setdefault(w, k)

# Eigennamen: Wörter, die in Tatoeba mitten im Satz überwiegend großgeschrieben auftreten
cap, low = collections.Counter(), collections.Counter()
for t in nl.values():
    ws = re.findall(r"[A-Za-zÀ-ÿŒœ]+", t)
    for w in ws[1:]:
        (cap if w[0].isupper() else low)[w.lower()] += 1
NAMES = {w for w in cap if cap[w] > low[w]} - CONF['keep']

# ---------- Kennzahlen pro Satz ----------
rows = []
for t, ids in CANDS.items():
    L = len(t)
    c_line, c_seq = LINE.get(t, 0), SEQ.get(t, 0)
    n = 3 if L >= 3 else L
    grams = [t[i:i + n] for i in range(L - n + 1)]
    # Baustein-Häufigkeit: mittlere log-Häufigkeit der 3-Wort-Bausteine -> unabhängig von der Satzlänge
    chunk = sum(math.log1p(SEQ.get(g, 0)) for g in grams) / len(grams)
    rows.append(dict(t=t, ids=ids, L=L, line=c_line, seq=c_seq, chunk=chunk))

# Längenbereinigung: Rohwert = log(Vorkommen als Wortfolge) + mittlere log-Häufigkeit der Bausteine.
# Dieser Rohwert wird nur mit Sätzen GLEICHER Länge verglichen (Perzentil 0..1), damit lange Sätze
# nicht allein deshalb verlieren, weil exakte Treffer mit jeder Wortzahl seltener werden.
for r in rows:
    r['raw'] = math.log1p(r['seq']) + r['chunk']
by = collections.defaultdict(list)
for r in rows: by[min(r['L'], 12)].append(r)
for grp in by.values():
    grp.sort(key=lambda r: r['raw'])
    for i, r in enumerate(grp):
        r['score'] = i / max(1, len(grp) - 1)

# Statistik zur Längenabhängigkeit für den Bericht
stat = []
by = collections.defaultdict(list)
for r in rows: by[r['L']].append(r)
for L in range(1, 15):
    g = by.get(L, [])
    if g:
        stat.append((L, len(g), statistics.median(r['seq'] for r in g), statistics.median(r['line'] for r in g),
                     sum(r['seq'] > 0 for r in g) / len(g)))

# ---------- Auswahl ----------
def sent_type(s):
    s = s.strip()
    if s.endswith('?'): return 'Frage'
    if s.endswith('!'): return 'Ausruf'
    return 'Aussage'

def clean(s):
    # Tatoeba-Typografie vereinheitlichen: schmale Leerzeichen vor ?!:; und typografische Apostrophe
    return re.sub(r'\s+', ' ', s.replace('\u202f', ' ').replace('\xa0', ' ').replace('’', "'")).strip()

def pick_de(ids):
    # Übersetzung mit der ähnlichsten Länge (sehr freie Übersetzungen sind meist viel kürzer/länger)
    best = None
    for i in ids:
        for b in links[i]:
            g = de.get(b)
            if not g: continue
            d = abs(math.log(len(g) / len(nl[i])))
            if best is None or d < best[0]: best = (d, g)
    return clean(best[1]) if best else None

def pick_nl(ids):
    # schönste Schreibweise: mit Satzzeichen am Ende, kürzeste
    return clean(sorted((nl[i] for i in ids), key=lambda s: (not s.rstrip()[-1:] in '.?!', len(s)))[0])

cand = []
for r in rows:
    if not (MINLEN <= r['L'] <= MAXLEN): continue
    if any(w in NAMES for w in r['t']): continue
    if nl[r['ids'][0]].count(',') >= 4: continue        # Aufzählungen
    rk = [rank.get(w, 99999) for w in r['t']]
    if max(rk) > MAX_RANK: continue
    if r['score'] < 0.5: continue                       # untere Hälfte seiner Längenklasse
    r['learn'] = sorted({w for w in r['t'] if rank.get(w, 0) >= LEARN_LO and len(w) > 1 and not w.endswith("'")},
                        key=lambda w: -rank[w])
    if not r['learn']: continue                       # nur Grundwortschatz -> eher A1/A2
    cand.append(r)
cand.sort(key=lambda r: -r['score'])

# Längenquote: jede Satzlänge bekommt so viele Plätze, wie es ihrem Anteil an den Kandidaten entspricht.
# Sonst würden lange Sätze bevorzugt, weil sie mehr noch unbenutzte Lernwörter mitbringen.
pool = collections.Counter(r['L'] for r in cand)
share = {L: TARGET * n / len(cand) for L, n in pool.items()}
quota = {L: int(v) for L, v in share.items()}
for L in sorted(share, key=lambda L: share[L] - quota[L], reverse=True)[:TARGET - sum(quota.values())]:
    quota[L] += 1
used_words = collections.Counter()
seen_content = set()
taken = collections.Counter()
out = []
for r in cand:
    if taken[r['L']] >= quota[r['L']]: continue
    content = frozenset(w for w in r['t'] if rank.get(w, 99999) > 150)
    if content in seen_content: continue
    fresh = [w for w in r['learn'] if used_words[w] < MAX_PER_WORD]
    if not fresh: continue
    g = pick_de(r['ids'])
    if not g: continue
    seen_content.add(content)
    for w in r['learn']: used_words[w] += 1
    key = fresh[0]   # seltenstes noch nicht ausgeschöpftes Lernwort
    taken[r['L']] += 1
    out.append((g, pick_nl(r['ids']), sent_type(pick_nl(r['ids'])), key, rank[key], r['L'], r['seq'], r['line'],
                round(100 * r['score'], 1)))
    if len(out) >= TARGET: break

pickle.dump({'stat': stat, 'out': out, 'ncand': len(cand), 'rows': len(rows), 'tokens': TOKENS, 'lines': d['lines']},
            open('result.pkl', 'wb'))
print('Kandidaten', len(cand), 'ausgewählt', len(out))
for s in stat: print(s)
sel = collections.Counter(o[5] for o in out)
for L in sorted(pool): print(L, pool[L], sel[L], round(sel[L]/pool[L],3))
for o in out[:40]: print(o)
for o in out[-15:]: print(o)

with open(CONF['out'], 'w', encoding='utf-8', newline='') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['Deutsch', CONF['lang'], 'Thema', 'Schlüsselwort', 'Rang Schlüsselwort (Untertitel)', 'Wörter',
                'Vorkommen als Wortfolge (OpenSubtitles)', 'Längenbereinigter Score (0-100)', 'Quelle'])
    for g, n, typ, key, rk, L, seq, line, sc in out:
        w.writerow([g, n, typ, key, rk, L, seq, str(sc).replace('.', ','), 'Tatoeba.org, CC BY 2.0 FR'])
