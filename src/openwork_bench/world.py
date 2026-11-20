"""The simulated workplace: mail, calendar, drive, CRM, chat and contacts.

A World is seeded from a task's world.yaml and workspace files. Agents act on it only through
tools. Every call is logged so graders can check side effects (who was emailed, what was
deleted) as well as the final state.
"""

from __future__ import annotations

import copy
import fnmatch
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class ToolError(Exception):
    """An error the agent should see as a tool result (bad arguments, missing item...)."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    mutating: bool = False


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


STR = {"type": "string"}
STR_LIST = {"type": "array", "items": {"type": "string"}}


def parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError as e:
        raise ToolError(f"Invalid date/time {value!r}; use ISO format like 2026-03-12T14:30") from e


def _norm_dt(value: str) -> str:
    return parse_dt(value).isoformat(timespec="minutes")


def _lower(s: Any) -> str:
    return str(s or "").lower()


def build_state(seed: dict[str, Any], workspace: dict[str, str]) -> dict[str, Any]:
    seed = copy.deepcopy(seed or {})
    state: dict[str, Any] = {
        "now": seed.get("now", "2026-03-09T09:00:00"),
        "timezone": seed.get("timezone", "America/New_York"),
        "company": seed.get("company", {"name": "Example Co.", "domain": "example.com"}),
        "user": seed.get("user", {"name": "Alex", "email": "alex@example.com", "title": "Employee"}),
        "contacts": seed.get("contacts", []),
        "mail": {"messages": []},
        "calendar": {"events": []},
        "drive": {"files": {}},
        "crm": {
            "records": seed.get("crm", {}).get("records", []),
            "stages": seed.get("crm", {}).get("stages", []),
        },
        "chat": {
            "channels": {
                k: list(v or []) for k, v in (seed.get("chat", {}).get("channels", {}) or {}).items()
            }
        },
    }
    for i, m in enumerate(seed.get("mail", {}).get("messages", []), 1):
        msg = {
            "id": m.get("id", f"m{i}"),
            "folder": m.get("folder", "inbox"),
            "from": m.get("from", ""),
            "to": m.get("to", [state["user"]["email"]]),
            "cc": m.get("cc", []),
            "subject": m.get("subject", ""),
            "body": m.get("body", ""),
            "date": m.get("date", state["now"]),
            "thread_id": m.get("thread_id", m.get("id", f"m{i}")),
            "attachments": m.get("attachments", []),
            "seeded": True,
        }
        state["mail"]["messages"].append(msg)
    for i, e in enumerate(seed.get("calendar", {}).get("events", []), 1):
        ev = dict(e)
        ev.setdefault("id", f"e{i}")
        ev["start"] = _norm_dt(ev["start"])
        ev["end"] = _norm_dt(ev["end"])
        ev.setdefault("attendees", [state["user"]["email"]])
        ev.setdefault("location", "")
        ev.setdefault("description", "")
        ev["seeded"] = True
        state["calendar"]["events"].append(ev)
    for path, content in (seed.get("drive", {}).get("files", {}) or {}).items():
        state["drive"]["files"][path] = {"content": content, "seeded": True}
    for path, content in workspace.items():
        state["drive"]["files"][path] = {"content": content, "seeded": True}
    for r in state["crm"]["records"]:
        r["seeded"] = True
    return state


class World:
    def __init__(self, seed: dict[str, Any], workspace: dict[str, str] | None = None):
        self.state = build_state(seed, workspace or {})
        self.initial = copy.deepcopy(self.state)
        self.actions: list[dict[str, Any]] = []
        self.answer: str | None = None
        self.done = False
        self._counter = 1000
        self.tools: dict[str, ToolSpec] = {t.name: t for t in self._specs()}

    # ------------------------------------------------------------------ plumbing
    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    @property
    def user_email(self) -> str:
        return self.state["user"]["email"]

    def tool_specs(self) -> list[ToolSpec]:
        return list(self.tools.values())

    def call(self, name: str, args: dict[str, Any] | None) -> tuple[bool, str]:
        """Run a tool. Returns (ok, result_text). Never raises for agent mistakes."""
        args = dict(args or {})
        entry: dict[str, Any] = {"step": len(self.actions) + 1, "tool": name, "args": args}
        spec = self.tools.get(name)
        if spec is None:
            entry.update(ok=False, error=f"Unknown tool {name!r}")
            self.actions.append(entry)
            return False, f"Error: unknown tool {name!r}"
        try:
            result = spec.fn(**args)
            entry["ok"] = True
            self.actions.append(entry)
            return True, result if isinstance(result, str) else json.dumps(result, indent=1, default=str)
        except ToolError as e:
            entry.update(ok=False, error=str(e))
            self.actions.append(entry)
            return False, f"Error: {e}"
        except TypeError as e:
            entry.update(ok=False, error=f"Bad arguments: {e}")
            self.actions.append(entry)
            return False, f"Error: bad arguments for {name}: {e}"

    def snapshot(self) -> dict[str, Any]:
        return {"state": copy.deepcopy(self.state), "actions": list(self.actions), "answer": self.answer}

    # ------------------------------------------------------------------ mail
    def _msg_summary(self, m: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": m["id"],
            "folder": m["folder"],
            "from": m["from"],
            "to": m["to"],
            "subject": m["subject"],
            "date": m["date"],
            "snippet": m["body"][:140],
            "attachments": m.get("attachments", []),
        }

    def mail_search(self, query: str = "", folder: str = "inbox", limit: int = 25) -> Any:
        q = _lower(query)
        out = []
        for m in self.state["mail"]["messages"]:
            if folder != "all" and m["folder"] != folder:
                continue
            hay = " ".join([m["from"], " ".join(m["to"]), m["subject"], m["body"]]).lower()
            if q and q not in hay:
                continue
            out.append(self._msg_summary(m))
        return out[: max(1, int(limit))]

    def _get_msg(self, message_id: str) -> dict[str, Any]:
        for m in self.state["mail"]["messages"]:
            if m["id"] == message_id:
                return m
        raise ToolError(f"No message with id {message_id!r}")

    def mail_read(self, message_id: str) -> Any:
        m = self._get_msg(message_id)
        return {k: v for k, v in m.items() if k != "seeded"}

    def _check_attachments(self, attachments: list[str]) -> list[str]:
        for p in attachments:
            if p not in self.state["drive"]["files"]:
                raise ToolError(f"Attachment {p!r} not found in drive")
        return list(attachments)

    def mail_send(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        reply_to_id: str | None = None,
        attachments: list[str] | None = None,
    ) -> Any:
        if isinstance(to, str):
            to = [to]
        if not to:
            raise ToolError("At least one recipient is required")
        thread = reply_to_id and self._get_msg(reply_to_id)["thread_id"]
        msg = {
            "id": self._next_id("m"),
            "folder": "sent",
            "from": self.user_email,
            "to": [t.strip() for t in to],
            "cc": [c.strip() for c in (cc or [])],
            "subject": subject,
            "body": body,
            "date": self.state["now"],
            "thread_id": thread or None,
            "attachments": self._check_attachments(attachments or []),
            "seeded": False,
        }
        msg["thread_id"] = msg["thread_id"] or msg["id"]
        self.state["mail"]["messages"].append(msg)
        return {"sent": True, "id": msg["id"]}

    def mail_forward(self, message_id: str, to: list[str], note: str = "") -> Any:
        orig = self._get_msg(message_id)
        body = (
            f"{note}\n\n---------- Forwarded message ----------\nFrom: {orig['from']}\n"
            f"Subject: {orig['subject']}\n\n{orig['body']}"
        )
        return self.mail_send(
            to=to, subject=f"Fwd: {orig['subject']}", body=body, attachments=orig.get("attachments", [])
        )

    def mail_delete(self, message_id: str) -> Any:
        m = self._get_msg(message_id)
        m["folder"] = "trash"
        return {"deleted": True, "id": message_id}

    # ------------------------------------------------------------------ calendar
    def _event_out(self, e: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in e.items() if k != "seeded"}

    def calendar_list(self, start_date: str, end_date: str) -> Any:
        s = parse_dt(start_date)
        e = parse_dt(end_date if "T" in end_date else end_date + "T23:59")
        out = []
        for ev in self.state["calendar"]["events"]:
            if self.user_email not in ev["attendees"]:
                continue
            if parse_dt(ev["end"]) > s and parse_dt(ev["start"]) < e:
                out.append(self._event_out(ev))
        return sorted(out, key=lambda x: x["start"])

    def calendar_availability(self, emails: list[str], date: str) -> Any:
        day = parse_dt(date if "T" in date else date + "T00:00").date()
        busy: dict[str, list[dict[str, str]]] = {e: [] for e in emails}
        for ev in self.state["calendar"]["events"]:
            if parse_dt(ev["start"]).date() != day:
                continue
            for person in emails:
                if person in ev["attendees"]:
                    busy[person].append({"start": ev["start"][11:], "end": ev["end"][11:]})
        return {
            "date": day.isoformat(),
            "busy": {k: sorted(v, key=lambda x: x["start"]) for k, v in busy.items()},
        }

    def calendar_create(
        self,
        title: str,
        start: str,
        end: str,
        attendees: list[str] | None = None,
        location: str = "",
        description: str = "",
    ) -> Any:
        s, e = parse_dt(start), parse_dt(end)
        if e <= s:
            raise ToolError("end must be after start")
        attendees = list(dict.fromkeys([*(attendees or []), self.user_email]))
        ev = {
            "id": self._next_id("e"),
            "title": title,
            "start": s.isoformat(timespec="minutes"),
            "end": e.isoformat(timespec="minutes"),
            "attendees": attendees,
            "location": location,
            "description": description,
            "seeded": False,
        }
        self.state["calendar"]["events"].append(ev)
        return {"created": True, "event": self._event_out(ev)}

    def _get_event(self, event_id: str) -> dict[str, Any]:
        for ev in self.state["calendar"]["events"]:
            if ev["id"] == event_id:
                return ev
        raise ToolError(f"No event with id {event_id!r}")

    def calendar_update(
        self,
        event_id: str,
        title: str | None = None,
        start: str | None = None,
        end: str | None = None,
        attendees: list[str] | None = None,
        location: str | None = None,
        description: str | None = None,
    ) -> Any:
        ev = self._get_event(event_id)
        if title is not None:
            ev["title"] = title
        if start is not None:
            ev["start"] = _norm_dt(start)
        if end is not None:
            ev["end"] = _norm_dt(end)
        if parse_dt(ev["end"]) <= parse_dt(ev["start"]):
            raise ToolError("end must be after start")
        if attendees is not None:
            ev["attendees"] = list(dict.fromkeys(attendees))
        if location is not None:
            ev["location"] = location
        if description is not None:
            ev["description"] = description
        return {"updated": True, "event": self._event_out(ev)}

    def calendar_delete(self, event_id: str) -> Any:
        ev = self._get_event(event_id)
        self.state["calendar"]["events"].remove(ev)
        return {"deleted": True, "id": event_id}

    # ------------------------------------------------------------------ drive
    def drive_list(self, folder: str = "/") -> Any:
        prefix = folder if folder.endswith("/") else folder + "/"
        return sorted(p for p in self.state["drive"]["files"] if p.startswith(prefix) or folder == "/")

    def drive_search(self, query: str) -> Any:
        q = _lower(query)
        out = []
        for path, f in sorted(self.state["drive"]["files"].items()):
            content = f["content"]
            if q in path.lower() or q in content.lower():
                i = content.lower().find(q)
                snippet = content[max(0, i - 60) : i + 100] if i >= 0 else content[:120]
                out.append({"path": path, "snippet": snippet})
        return out

    def drive_read(self, path: str) -> Any:
        f = self.state["drive"]["files"].get(path)
        if f is None:
            matches = fnmatch.filter(self.state["drive"]["files"], f"*{path.strip('/')}")
            hint = f" Did you mean {matches[0]!r}?" if matches else ""
            raise ToolError(f"File {path!r} not found.{hint}")
        return f["content"]

    def drive_write(self, path: str, content: str) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        existing = self.state["drive"]["files"].get(path)
        self.state["drive"]["files"][path] = {
            "content": content,
            "seeded": bool(existing and existing.get("seeded")),
        }
        return {"written": True, "path": path, "bytes": len(content)}

    def drive_delete(self, path: str) -> Any:
        if path not in self.state["drive"]["files"]:
            raise ToolError(f"File {path!r} not found")
        del self.state["drive"]["files"][path]
        return {"deleted": True, "path": path}

    # ------------------------------------------------------------------ crm
    def _record_out(self, r: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in r.items() if k != "seeded"}

    def crm_search(self, query: str = "", type: str | None = None) -> Any:
        q = _lower(query)
        out = []
        for r in self.state["crm"]["records"]:
            if type and r.get("type") != type:
                continue
            if q and q not in json.dumps(r, default=str).lower():
                continue
            out.append(self._record_out(r))
        return out

    def _get_record(self, record_id: str) -> dict[str, Any]:
        for r in self.state["crm"]["records"]:
            if r["id"] == record_id:
                return r
        raise ToolError(f"No CRM record with id {record_id!r}")

    def crm_get(self, record_id: str) -> Any:
        return self._record_out(self._get_record(record_id))

    def crm_update(self, record_id: str, fields: dict[str, Any]) -> Any:
        r = self._get_record(record_id)
        if not isinstance(fields, dict):
            raise ToolError("fields must be an object of field names to values")
        fields = dict(fields)
        stages = self.state["crm"].get("stages") or []
        if "stage" in fields and stages and fields["stage"] not in stages:
            raise ToolError(f"Invalid stage {fields['stage']!r}; allowed: {stages}")
        for protected in ("id", "type", "seeded"):
            fields.pop(protected, None)
        r.update(fields)
        return {"updated": True, "record": self._record_out(r)}

    def crm_create(self, type: str, fields: dict[str, Any]) -> Any:
        r = {"id": self._next_id(type[:1].upper() + "-"), "type": type, **fields, "seeded": False}
        self.state["crm"]["records"].append(r)
        return {"created": True, "record": self._record_out(r)}

    # ------------------------------------------------------------------ chat & contacts
    def chat_channels(self) -> Any:
        return sorted(self.state["chat"]["channels"])

    def chat_list(self, channel: str, limit: int = 20) -> Any:
        ch = channel.lstrip("#")
        if ch not in self.state["chat"]["channels"]:
            raise ToolError(f"No channel #{ch}")
        return self.state["chat"]["channels"][ch][-int(limit) :]

    def chat_post(self, channel: str, text: str) -> Any:
        ch = channel.lstrip("#")
        if ch not in self.state["chat"]["channels"]:
            raise ToolError(f"No channel #{ch}")
        msg = {
            "id": self._next_id("c"),
            "author": self.user_email,
            "text": text,
            "ts": self.state["now"],
            "seeded": False,
        }
        self.state["chat"]["channels"][ch].append(msg)
        return {"posted": True, "id": msg["id"]}

    def contacts_search(self, query: str = "") -> Any:
        q = _lower(query)
        return [c for c in self.state["contacts"] if not q or q in json.dumps(c).lower()]

    # ------------------------------------------------------------------ finish
    def submit(self, answer: str) -> Any:
        self.answer = str(answer)
        self.done = True
        return {"submitted": True}

    # ------------------------------------------------------------------ registry
    def _specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                "mail_search",
                "Search email by text in sender, recipients, subject or body. folder: inbox, sent, drafts, trash or all.",
                _obj({"query": STR, "folder": STR, "limit": {"type": "integer"}}),
                self.mail_search,
            ),
            ToolSpec(
                "mail_read",
                "Read one email in full.",
                _obj({"message_id": STR}, ["message_id"]),
                self.mail_read,
            ),
            ToolSpec(
                "mail_send",
                "Send an email. Use reply_to_id to reply in a thread. attachments are drive paths.",
                _obj(
                    {
                        "to": STR_LIST,
                        "subject": STR,
                        "body": STR,
                        "cc": STR_LIST,
                        "reply_to_id": STR,
                        "attachments": STR_LIST,
                    },
                    ["to", "subject", "body"],
                ),
                self.mail_send,
                True,
            ),
            ToolSpec(
                "mail_forward",
                "Forward an email (with its attachments) to recipients, with an optional note.",
                _obj({"message_id": STR, "to": STR_LIST, "note": STR}, ["message_id", "to"]),
                self.mail_forward,
                True,
            ),
            ToolSpec(
                "mail_delete",
                "Move an email to trash.",
                _obj({"message_id": STR}, ["message_id"]),
                self.mail_delete,
                True,
            ),
            ToolSpec(
                "calendar_list",
                "List your calendar events between two dates (YYYY-MM-DD or ISO datetimes).",
                _obj({"start_date": STR, "end_date": STR}, ["start_date", "end_date"]),
                self.calendar_list,
            ),
            ToolSpec(
                "calendar_availability",
                "Busy times for colleagues (by email) on one date.",
                _obj({"emails": STR_LIST, "date": STR}, ["emails", "date"]),
                self.calendar_availability,
            ),
            ToolSpec(
                "calendar_create",
                "Create a calendar event. Times are ISO local times like 2026-03-12T14:30.",
                _obj(
                    {
                        "title": STR,
                        "start": STR,
                        "end": STR,
                        "attendees": STR_LIST,
                        "location": STR,
                        "description": STR,
                    },
                    ["title", "start", "end"],
                ),
                self.calendar_create,
                True,
            ),
            ToolSpec(
                "calendar_update",
                "Change an existing event; only the fields you pass are changed.",
                _obj(
                    {
                        "event_id": STR,
                        "title": STR,
                        "start": STR,
                        "end": STR,
                        "attendees": STR_LIST,
                        "location": STR,
                        "description": STR,
                    },
                    ["event_id"],
                ),
                self.calendar_update,
                True,
            ),
            ToolSpec(
                "calendar_delete",
                "Delete a calendar event.",
                _obj({"event_id": STR}, ["event_id"]),
                self.calendar_delete,
                True,
            ),
            ToolSpec(
                "drive_list", "List file paths in a drive folder.", _obj({"folder": STR}), self.drive_list
            ),
            ToolSpec(
                "drive_search",
                "Search drive files by name or content.",
                _obj({"query": STR}, ["query"]),
                self.drive_search,
            ),
            ToolSpec(
                "drive_read",
                "Read a drive file's text content.",
                _obj({"path": STR}, ["path"]),
                self.drive_read,
            ),
            ToolSpec(
                "drive_write",
                "Create or overwrite a drive file (Markdown, CSV or text).",
                _obj({"path": STR, "content": STR}, ["path", "content"]),
                self.drive_write,
                True,
            ),
            ToolSpec(
                "drive_delete", "Delete a drive file.", _obj({"path": STR}, ["path"]), self.drive_delete, True
            ),
            ToolSpec(
                "crm_search",
                "Search CRM records (accounts, deals, contacts) by text, optionally by type.",
                _obj({"query": STR, "type": STR}),
                self.crm_search,
            ),
            ToolSpec(
                "crm_get", "Get one CRM record by id.", _obj({"record_id": STR}, ["record_id"]), self.crm_get
            ),
            ToolSpec(
                "crm_update",
                "Update fields on a CRM record.",
                _obj({"record_id": STR, "fields": {"type": "object"}}, ["record_id", "fields"]),
                self.crm_update,
                True,
            ),
            ToolSpec(
                "crm_create",
                "Create a CRM record of a type (account, deal, contact).",
                _obj({"type": STR, "fields": {"type": "object"}}, ["type", "fields"]),
                self.crm_create,
                True,
            ),
            ToolSpec("chat_channels", "List team chat channels.", _obj({}), self.chat_channels),
            ToolSpec(
                "chat_list",
                "Read recent messages in a chat channel.",
                _obj({"channel": STR, "limit": {"type": "integer"}}, ["channel"]),
                self.chat_list,
            ),
            ToolSpec(
                "chat_post",
                "Post a message to a team chat channel.",
                _obj({"channel": STR, "text": STR}, ["channel", "text"]),
                self.chat_post,
                True,
            ),
            ToolSpec(
                "contacts_search",
                "Search the company directory and contacts.",
                _obj({"query": STR}),
                self.contacts_search,
            ),
            ToolSpec(
                "submit",
                "Finish the task. Put the requested answer or a short summary of what you did in answer.",
                _obj({"answer": STR}, ["answer"]),
                self.submit,
            ),
        ]
