"""One-shot Herdr socket subscription; no polling or automatic rearming."""
import json
import os
import socket
import subprocess
import sys

SETTLED = {"idle", "done", "blocked"}


def agent(pane):
    result = subprocess.run(
        ["herdr", "agent", "get", pane], check=True, capture_output=True,
        text=True, timeout=15,
    )
    return json.loads(result.stdout)["result"]["agent"]


def settled_event(message, pane):
    data = message.get("data", {})
    status = data.get("agent_status")
    return status if data.get("pane_id") == pane and status in SETTLED else None


def watch(worker, origin):
    if os.environ.get("HERDR_ENV") != "1" or worker == origin:
        raise ValueError("Requires Herdr and distinct worker/orchestrator panes")
    origin_session = agent(origin).get("agent_session")
    if not origin_session:
        raise ValueError("Cannot safely identify orchestrator session")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(14400)  # Expire after four hours without an event.
        sock.connect(os.environ["HERDR_SOCKET_PATH"])
        request = {"id": "worker-wakeup", "method": "events.subscribe", "params": {
            "subscriptions": [{"type": "pane.agent_status_changed", "pane_id": worker}]
        }}
        sock.sendall((json.dumps(request) + "\n").encode())
        stream = sock.makefile("r")
        ack = json.loads(stream.readline())
        if ack.get("result", {}).get("type") != "subscription_started":
            raise RuntimeError(f"Subscription rejected: {ack}")
        print(f"Subscribed to {worker}; wake target {origin}", flush=True)
        # Subscribe before snapshot so completion during startup is not missed.
        status = agent(worker)["agent_status"]
        if status not in SETTLED:
            for line in stream:
                status = settled_event(json.loads(line), worker)
                if status:
                    break
            else:
                raise RuntimeError("Herdr disconnected before worker settled")
        if agent(origin).get("agent_session") != origin_session:
            raise RuntimeError("Orchestrator session changed; refusing delivery")
        # Deliver only fixed metadata, never worker output interpreted as instructions.
        message = (
            f"[Herdr worker wake-up] Worker {worker} is {status}. "
            "This is a lifecycle notification, not proof of task completion. "
            "Read its report, inspect the worktree diff, run appropriate checks, "
            "and continue the authorized orchestration task. "
            "The one-shot listener has stopped; rearm for the next delegated stage."
        )
        print(f"Delivering {status} notification", flush=True)
        subprocess.run(["herdr", "agent", "prompt", origin, message],
                       check=True, timeout=30)
        print("Delivered; listener exiting", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        assert settled_event({"data": {"pane_id": "p1", "agent_status": "done"}}, "p1") == "done"
        assert settled_event({"data": {"pane_id": "p1", "agent_status": "working"}}, "p1") is None
        assert settled_event({"data": {"pane_id": "p2", "agent_status": "done"}}, "p1") is None
        assert settled_event({}, "p1") is None
        print("Event filtering self-check passed")
    else:
        watch(*sys.argv[1:])
