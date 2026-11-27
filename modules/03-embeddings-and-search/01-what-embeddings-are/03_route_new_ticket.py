"""03.1/3  Scenario: route a new ticket to the most similar past ticket

Helpdesk scenario: embed past resolved tickets, then for each new ticket find the closest
one and suggest the same team and fix. No vector database yet (that is lesson 03.3).

Run it:   ./run 03.1/3          (Windows: run 03.1/3)
     or:  python modules/03-embeddings-and-search/01-what-embeddings-are/03_route_new_ticket.py
Needs the `rag` extra (local embedding model). No chat model is used.
"""

import numpy as np

from labkit import lesson

PAST = [
    {"id": "T-1001", "team": "Network", "text": "Laptop drops the Wi-Fi every few minutes in the east wing.", "fix": "Updated the wireless driver."},
    {"id": "T-1002", "team": "Identity", "text": "Locked out of my account after typing the wrong password too often.", "fix": "Unlocked the account and reset the password."},
    {"id": "T-1003", "team": "Hardware", "text": "Laptop screen flickers and then goes black.", "fix": "Swapped the display cable; replaced the unit when it recurred."},
    {"id": "T-1004", "team": "Printing", "text": "Printer on floor 2 prints blank pages.", "fix": "Replaced the toner cartridge."},
    {"id": "T-1005", "team": "Software", "text": "Need a licence for the design tool for a new hire.", "fix": "Approved the request and assigned a seat."},
    {"id": "T-1006", "team": "Network", "text": "Cannot reach internal wiki from home without the VPN connecting.", "fix": "Reinstalled the VPN client profile."},
    {"id": "T-1007", "team": "Identity", "text": "Authenticator codes are rejected after I changed phones.", "fix": "Re-enrolled the authenticator app."},
]
NEW = [
    "My computer display keeps going dark randomly",
    "The remote access tool will not log me in from my flat",
    "Please can I get Photoshop-style software for my team",
]


@lesson("03.1/3", "Route a new ticket")
def main(ctx):
    ctx.step("Embed the past resolved tickets")
    past = np.array(ctx.embed([t["text"] for t in PAST]))
    past = past / np.linalg.norm(past, axis=1, keepdims=True)
    ctx.note(f"{len(PAST)} tickets -> {past.shape[0]} vectors of {past.shape[1]} numbers each.")

    ctx.step("Route each new ticket")
    vectors = np.array(ctx.embed(NEW))
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    for text, vec in zip(NEW, vectors):
        scores = past @ vec
        order = np.argsort(-scores)
        best = PAST[int(order[0])]
        ctx.show_data(
            f"New ticket: {text}",
            {
                "most similar": f"{best['id']} (score {scores[order[0]]:.2f}): {best['text']}",
                "route to": best["team"],
                "past fix": best["fix"],
                "runner-up": f"{PAST[int(order[1])]['id']} ({scores[order[1]]:.2f}) {PAST[int(order[1])]['team']}",
            },
        )

    ctx.step("How far to trust it")
    ctx.note("Routing by nearest neighbour is cheap and needs no chat model. A margin between #1 and #2,")
    ctx.note("or a minimum score, tells you when to hand the ticket to a human instead.")


if __name__ == "__main__":
    main()
