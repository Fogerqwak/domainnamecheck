com = set(open("available_com.txt").read().split())
ai = set(open("available_ai.txt").read().split())

both = sorted(com & ai)

with open("available_both.txt", "w") as f:
    f.write("\n".join(both))

print(len(both), "domains available in BOTH")
