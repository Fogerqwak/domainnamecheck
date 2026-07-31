import random
from pathlib import Path

random.seed()

PREFIXES = [
    "sa","sav","sca","scr","cli","cl","vi","ve","vo","no","nu","lu","ly",
    "ka","ki","ke","ko","za","ze","zi","zy","or","om","el","al","re","ri",
    "tro","tra","tri","dex","de","in","sy","syn","va","ver","quo","qu","pr",
    "fl","fr","sk","st","bl","br","gr","gl","cr","kr"
]

MIDDLES = [
    "v","vi","vo","va","ve","ly","li","lo","la","ra","ri","ro","re",
    "na","ni","no","ne","ta","ti","to","te","xa","xo","xe","za",
    "zi","zo","qa","qi","qo","ix","iq","yx","or","ar","er","ur",
    "ex","ev","el","ul","um","on","en","an","in"
]

SUFFIXES = [
    "a","o","io","ia","iq","ix","ly","sy","ra","ro","ri","ry",
    "va","vo","vi","za","zo","zi","or","os","on","ox","ex","eo",
    "iqo","ora","ivo","exa","ixa","ium","iox","ara","ero","eva",
    "ify","ica","ora","ivo","ium","ixa","iqa","ana"
]

BAD = {
    "ass","sex","cum","fuk","fuck","shit","anal","rape","kkk","nazi"
}

def make_name():
    parts = []

    parts.append(random.choice(PREFIXES))

    if random.random() < 0.65:
        parts.append(random.choice(MIDDLES))

    parts.append(random.choice(SUFFIXES))

    name = "".join(parts)

    if random.random() < 0.25:
        name += random.choice(["x","q","r","n"])

    return name.capitalize()

names = set()

while len(names) < 10000:
    n = make_name()

    lower = n.lower()

    if not (5 <= len(lower) <= 10):
        continue

    if any(b in lower for b in BAD):
        continue

    # avoid too many repeated chars
    if any(c * 3 in lower for c in "abcdefghijklmnopqrstuvwxyz"):
        continue

    names.add(n)

Path("startup_names.txt").write_text(
    "\n".join(sorted(names)),
    encoding="utf-8"
)

print(f"Generated {len(names)} names.")
