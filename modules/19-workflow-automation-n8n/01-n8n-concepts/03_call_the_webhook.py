"""19.1/3  Call the workflow's webhook

POSTs an invented helpdesk ticket to your n8n instance. Needs n8n running with the workflow imported.
By default it calls the TEST url (the workflow must be open in the editor, listening);
use --production once the workflow is saved and Active.

Run it:   ./run 19.1/3          (Windows: run 19.1/3)
     or:  python modules/19-workflow-automation-n8n/01-n8n-concepts/03_call_the_webhook.py [--production]
"""

import json
import sys
import urllib.error
import urllib.request

from labkit import lesson
from labkit.services import require


@lesson("19.1/3", "Call the workflow's webhook")
def main(ctx):
    base = require("N8N_URL").rstrip("/")
    kind = "webhook" if "--production" in sys.argv else "webhook-test"
    url = f"{base}/{kind}/helpdesk-ticket"
    ticket = {"ticket": "I cannot reach the Larkspur VPN from home; it times out after login."}

    ctx.step("Send the ticket")
    ctx.note(f"POST {url}")
    ctx.show_data("Body", ticket)
    req = urllib.request.Request(
        url, data=json.dumps(ticket).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status, body = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as err:
        ctx.note(f"Could not reach n8n: {err}")
        return

    ctx.step("What came back")
    print(f"  status: {status}")
    print(f"  body:   {body[:1000]}")
    if status == 404:
        ctx.note("404 usually means: test URL used while the editor is not listening, or production URL while the workflow is inactive.")


if __name__ == "__main__":
    main()
