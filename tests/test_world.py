import json

from openwork_bench.tasks import deep_merge
from openwork_bench.world import World

SEED = {
    "company": {"name": "Acme", "domain": "acme.example"},
    "user": {"name": "Sam", "email": "sam@acme.example"},
    "crm": {
        "stages": ["Open", "Won"],
        "records": [{"id": "D-1", "type": "deal", "stage": "Open", "amount": 10}],
    },
    "chat": {"channels": {"general": []}},
    "calendar": {
        "events": [
            {
                "id": "e1",
                "title": "Sync",
                "start": "2026-03-10T10:00",
                "end": "2026-03-10T11:00",
                "attendees": ["sam@acme.example", "kim@acme.example"],
            }
        ]
    },
}


def test_tools_mutate_state_and_log_actions():
    w = World(SEED, {"/notes.md": "hello"})
    ok, out = w.call("drive_read", {"path": "/notes.md"})
    assert ok and out == "hello"
    ok, _ = w.call("mail_send", {"to": ["kim@acme.example"], "subject": "Hi", "body": "Body"})
    assert ok
    assert [m for m in w.state["mail"]["messages"] if m["folder"] == "sent"][0]["to"] == ["kim@acme.example"]
    assert [a["tool"] for a in w.actions] == ["drive_read", "mail_send"]


def test_agent_mistakes_are_tool_errors_not_crashes():
    w = World(SEED)
    ok, out = w.call("drive_read", {"path": "/missing.md"})
    assert not ok and "not found" in out
    ok, out = w.call("crm_update", {"record_id": "D-1", "fields": {"stage": "Bogus"}})
    assert not ok and "allowed" in out
    ok, out = w.call(
        "calendar_create", {"title": "x", "start": "2026-03-10T10:00", "end": "2026-03-10T09:00"}
    )
    assert not ok
    ok, out = w.call("no_such_tool", {})
    assert not ok
    ok, out = w.call("mail_send", {"subject": "missing to"})
    assert not ok and "bad arguments" in out


def test_availability_and_calendar():
    w = World(SEED)
    ok, out = w.call("calendar_availability", {"emails": ["kim@acme.example"], "date": "2026-03-10"})
    assert ok and json.loads(out)["busy"]["kim@acme.example"] == [{"start": "10:00", "end": "11:00"}]
    ok, _ = w.call(
        "calendar_update", {"event_id": "e1", "start": "2026-03-10T14:00", "end": "2026-03-10T15:00"}
    )
    assert ok and w.state["calendar"]["events"][0]["start"] == "2026-03-10T14:00"


def test_submit_ends_the_task():
    w = World(SEED)
    w.call("submit", {"answer": "done"})
    assert w.done and w.answer == "done"


def test_deep_merge_by_id():
    base = {"records": [{"id": "a", "x": 1}, {"id": "b", "x": 2}], "plain": [1]}
    merged = deep_merge(base, {"records": [{"id": "a", "x": 9}, {"id": "c", "x": 3}], "plain": [2]})
    assert merged["records"] == [{"id": "a", "x": 9}, {"id": "b", "x": 2}, {"id": "c", "x": 3}]
    assert merged["plain"] == [1, 2]
