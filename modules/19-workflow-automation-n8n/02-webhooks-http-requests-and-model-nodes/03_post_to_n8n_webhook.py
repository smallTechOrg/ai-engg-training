"""19.2/3  Call the workflow through a real n8n webhook (query string and headers included)

Needs n8n running, this lesson's workflow imported, and the agent URL in the 'Call the agent' node reachable
from n8n. Posts one ticket with a query string and a custom header, to show that the Webhook node puts them
in $json.query and $json.headers. With n8n absent the lesson stops with exit 3 and the start command.

Run it:   ./run 19.2/3 [--production]       (Windows: run 19.2/3)
     or:  python modules/19-workflow-automation-n8n/02-webhooks-http-requests-and-model-nodes/03_post_to_n8n_webhook.py
"""

import json
import sys
import urllib.error
import urllib.request

from labkit import lesson
from labkit.services import require


@lesson("19.2/3", "Call the workflow through a real n8n webhook")
def main(ctx):
    base = require("N8N_URL").rstrip("/")
    kind = "webhook" if "--production" in sys.argv else "webhook-test"
    url = f"{base}/{kind}/helpdesk-agent?priority=high"
    ticket = {"ticket": "The shared printer on floor 3 shows 'offline' for everyone."}

    ctx.step("POST a ticket")
    ctx.note(f"POST {url}  with header X-Larkspur-Source: course")
    ctx.show_data("Body", ticket)
    req = urllib.request.Request(
        url,
        data=json.dumps(ticket).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Larkspur-Source": "course"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as err:
        ctx.note(f"Could not reach n8n: {err}")
        return

    ctx.step("What came back")
    print(f"  status: {status}")
    print(f"  body:   {body[:800]}")
    if status == 404:
        ctx.note("404: wrong URL kind for the workflow state (test needs 'Listen for test event'; production needs Active).")
    elif status >= 500:
        ctx.note("500 usually means the 'Call the agent' node could not reach the agent. Open the execution in n8n to see which node failed.")
    ctx.note("In n8n the query string arrived as $json.query.priority and the header as $json.headers['x-larkspur-source'].")


if __name__ == "__main__":
    main()
