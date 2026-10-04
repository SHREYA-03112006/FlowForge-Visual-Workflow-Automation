"""Generate a synthetic support-ticket dataset (data/tickets.csv).

Tickets are composed from an opener + core issue + detail + closer, with light
typo noise, so the classifier sees varied phrasing instead of exact repeats.
Run:  python data/generate_data.py [--per-class 80] [--seed 7]
"""
import argparse
import csv
import random
from pathlib import Path

OPENERS = ["Hi,", "Hello team,", "Hey,", "Good morning,", "Hi support,", "Hello,", "", "", ""]

CLOSERS = [
    "Please help.", "Thanks!", "Urgent.", "Let me know what to do.",
    "Thank you in advance.", "Waiting for your reply.", "", "", "",
]

# Class-agnostic context, so the label depends on the core issue, not the filler.
DETAILS = [
    "It started yesterday.", "This has happened three times now.",
    "I am on the pro plan.", "I'm using the free plan.", "This is affecting my whole team.",
    "I contacted you last week as well.", "My order number is #{n}.",
    "Ticket reference {n}.", "I tried on two different devices.", "", "", "",
]

CORES = {
    "billing": [
        "I was charged twice for my subscription this month",
        "my invoice shows the wrong amount",
        "I need a refund for my last purchase",
        "the payment failed but the money was deducted from my bank account",
        "please update the billing address on my invoice",
        "my credit card was declined at renewal",
        "I want to cancel auto-renewal and get a refund",
        "there is an unknown charge on my statement",
        "the discount code was not applied at checkout",
        "can you send me a copy of last month's invoice",
        "I was billed for a plan I already downgraded",
        "GST details are missing from my invoice",
        "why was I charged a late fee on my bill",
        "I never received a receipt for my payment",
        "my promo credit disappeared from the billing page",
    ],
    "technical": [
        "the app crashes every time I open the dashboard",
        "I get a 500 error when uploading a file",
        "the API returns a timeout on every request",
        "the page is stuck on the loading screen",
        "export to CSV is not working",
        "notifications are not being delivered",
        "the mobile app freezes after the latest update",
        "I keep getting a connection error",
        "the Slack integration stopped syncing",
        "search returns no results even though the data exists",
        "the website is extremely slow today",
        "there is a bug in the report generator",
        "my webhook calls are failing with an error",
        "the editor loses my changes when I refresh",
        "images fail to load on the main page",
    ],
    "account": [
        "I forgot my password and the reset email never arrives",
        "I can't log in to my account",
        "please change the email address on my account",
        "my account was locked after several login attempts",
        "how do I enable two-factor authentication",
        "I want to delete my account and all my data",
        "please add a new user to our team workspace",
        "I need to change my username",
        "my profile information is not saving",
        "I didn't receive the verification code",
        "please merge my two accounts into one",
        "transfer ownership of the workspace to my colleague",
        "I need to update the phone number linked to my login",
        "how can I remove a member from my organization",
        "my login says the user does not exist",
    ],
    "general": [
        "do you have a student discount program",
        "what are your support hours",
        "can I get a demo of the product",
        "where can I find the documentation",
        "I would like to give feedback about the new design",
        "do you offer an on-premise version",
        "how can I become a partner or reseller",
        "which countries do you support",
        "is there a mobile app available",
        "I'd like to know about upcoming features",
        "are you hiring at the moment",
        "how do I contact the sales team",
        "do you have a public roadmap",
        "can you share case studies from other customers",
        "is there a community forum or Discord",
    ],
}


def add_typo(text: str, rng: random.Random) -> str:
    """Swap two adjacent letters in one random word (a very common typo)."""
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) > 4 and w.isalpha()]
    if not candidates:
        return text
    i = rng.choice(candidates)
    w = words[i]
    j = rng.randrange(1, len(w) - 2)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def compose(core: str, rng: random.Random) -> str:
    opener = rng.choice(OPENERS)
    detail = rng.choice(DETAILS).format(n=rng.randint(1000, 99999))
    closer = rng.choice(CLOSERS)
    sentence = core[0].upper() + core[1:] if not opener else core
    text = " ".join(p for p in [opener, sentence + ".", detail, closer] if p)
    if rng.random() < 0.15:
        text = add_typo(text, rng)
    if rng.random() < 0.1:
        text = text.lower()
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    rows, seen = [], set()
    for label, cores in CORES.items():
        count, attempts = 0, 0
        while count < args.per_class and attempts < args.per_class * 50:
            attempts += 1
            text = compose(rng.choice(cores), rng)
            if text in seen:
                continue
            seen.add(text)
            rows.append((text, label))
            count += 1

    rng.shuffle(rows)
    out = Path(__file__).resolve().parent / "tickets.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
