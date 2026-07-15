"""Surgical, plan-first editor and package projections for declared dev targets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..catalog import canonical_json, sha256_bytes
from ..config import CONFIG_SCHEMA_VERSION, ConfigError, ResolvedConfig, load_config
from ..plans import PLAN_SCHEMA_VERSION, Blocker, PlannedWrite, make_write


SETUP_PROJECTION_VERSION = 1
_MARKER = re.compile(
    r"^\s*svc:dev:begin\s+target=([A-Za-z0-9][A-Za-z0-9._-]*)\s+body-sha256=([0-9a-f]{64})\s*$"
)
_END_MARKER = re.compile(r"^\s*svc:dev:end\s+target=([A-Za-z0-9][A-Za-z0-9._-]*)\s*$")


@dataclass(frozen=True)
class SetupPlan:
    """A LocalPlan-compatible plan whose digest also binds setup authority."""

    command: str
    repo: Path
    target_version: str
    writes: tuple[PlannedWrite, ...]
    blockers: tuple[Blocker, ...]
    integration: str
    profile: str | None
    targets: tuple[str, ...]
    base_digest: str | None
    local_digest: str | None
    effective_digest: str | None
    orphaned: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if self.blockers:
            return "blocked"
        return "ready" if self.writes else "noop"

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.signature()))

    def signature(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "command": self.command,
            "repo": str(self.repo.resolve()),
            "target_version": self.target_version,
            "setup": {
                "projection_version": SETUP_PROJECTION_VERSION,
                "config_schema_version": CONFIG_SCHEMA_VERSION,
                "integration": self.integration,
                "profile": self.profile,
                "targets": list(self.targets),
                "base_digest": self.base_digest,
                "local_digest": self.local_digest,
                "effective_digest": self.effective_digest,
            },
            "operations": [write.signature() for write in self.writes],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
        }

    def as_dict(self) -> dict[str, object]:
        summary: dict[str, int] = {}
        for write in self.writes:
            summary[write.action] = summary.get(write.action, 0) + 1
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "command": self.command,
            "status": self.status,
            "target_version": self.target_version,
            "setup": {
                "projection_version": SETUP_PROJECTION_VERSION,
                "integration": self.integration,
                "profile": self.profile,
                "targets": list(self.targets),
                "base_digest": self.base_digest,
                "local_digest": self.local_digest,
                "effective_digest": self.effective_digest,
                "orphaned": list(self.orphaned),
            },
            "operations": [write.as_dict() for write in self.writes],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
            "summary": summary,
            "plan_digest": self.digest,
        }


@dataclass(frozen=True)
class _Token:
    kind: str
    start: int
    end: int
    value: Any = None


@dataclass(frozen=True)
class _Member:
    key: str
    key_token: _Token
    value: "_Node"


@dataclass(frozen=True)
class _Node:
    kind: str
    start: int
    end: int
    value: Any = None
    members: tuple[_Member, ...] = ()
    items: tuple["_Node", ...] = ()


class _JsonSyntax(ValueError):
    pass


class _JsoncDocument:
    """A small JSON/JSONC parser retaining lexical positions for bounded edits."""

    def __init__(self, source: str, *, allow_comments: bool) -> None:
        self.source = source
        self.allow_comments = allow_comments
        self.comments: list[_Token] = []
        self.tokens = self._lex()
        self.index = 0
        self.root = self._value()
        if self.index != len(self.tokens):
            raise _JsonSyntax("unexpected trailing content")

    def _lex(self) -> list[_Token]:
        tokens: list[_Token] = []
        offset = 0
        text = self.source
        while offset < len(text):
            char = text[offset]
            if char in " \t\r\n":
                offset += 1
                continue
            if char == "/" and offset + 1 < len(text) and text[offset + 1] in "/*":
                if not self.allow_comments:
                    raise _JsonSyntax("comments are not valid JSON")
                if text[offset + 1] == "/":
                    finish = text.find("\n", offset + 2)
                    finish = len(text) if finish < 0 else finish
                    token = _Token("comment", offset, finish, text[offset + 2 : finish])
                else:
                    finish = text.find("*/", offset + 2)
                    if finish < 0:
                        raise _JsonSyntax("unterminated block comment")
                    finish += 2
                    token = _Token("comment", offset, finish, text[offset + 2 : finish - 2])
                self.comments.append(token)
                offset = token.end
                continue
            if char in "{}[]:,":
                tokens.append(_Token(char, offset, offset + 1))
                offset += 1
                continue
            if char == '"':
                start = offset
                offset += 1
                escaped = False
                while offset < len(text):
                    current = text[offset]
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        offset += 1
                        break
                    elif ord(current) < 0x20:
                        raise _JsonSyntax("control character in string")
                    offset += 1
                else:
                    raise _JsonSyntax("unterminated string")
                raw = text[start:offset]
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as error:
                    raise _JsonSyntax("invalid string") from error
                tokens.append(_Token("string", start, offset, value))
                continue
            number = re.match(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", text[offset:])
            if number:
                end = offset + len(number.group(0))
                if end < len(text) and text[end] not in " \t\r\n{}[]:,/":
                    raise _JsonSyntax("invalid JSON value")
                tokens.append(_Token("scalar", offset, end, json.loads(number.group(0))))
                offset = end
                continue
            for literal, value in (("true", True), ("false", False), ("null", None)):
                if text.startswith(literal, offset):
                    end = offset + len(literal)
                    if end == len(text) or text[end] in " \t\r\n{}[]:,/":
                        tokens.append(_Token("scalar", offset, end, value))
                        offset = end
                        break
            else:
                raise _JsonSyntax("invalid JSON value")
            if tokens and tokens[-1].end == offset:
                continue
        return tokens

    def _take(self, kind: str) -> _Token:
        if self.index >= len(self.tokens) or self.tokens[self.index].kind != kind:
            raise _JsonSyntax(f"expected {kind}")
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _value(self) -> _Node:
        if self.index >= len(self.tokens):
            raise _JsonSyntax("missing value")
        token = self.tokens[self.index]
        if token.kind == "{":
            return self._object()
        if token.kind == "[":
            return self._array()
        if token.kind in {"string", "scalar"}:
            self.index += 1
            return _Node(token.kind, token.start, token.end, token.value)
        raise _JsonSyntax("expected JSON value")

    def _object(self) -> _Node:
        opening = self._take("{")
        members: list[_Member] = []
        keys: set[str] = set()
        if self.index < len(self.tokens) and self.tokens[self.index].kind == "}":
            closing = self._take("}")
            return _Node("object", opening.start, closing.end, members=tuple(members))
        while True:
            key = self._take("string")
            if key.value in keys:
                raise _JsonSyntax(f"duplicate key {key.value!r}")
            keys.add(key.value)
            self._take(":")
            value = self._value()
            members.append(_Member(key.value, key, value))
            if self.index >= len(self.tokens):
                raise _JsonSyntax("unterminated object")
            separator = self.tokens[self.index]
            if separator.kind == "}":
                self.index += 1
                return _Node("object", opening.start, separator.end, members=tuple(members))
            self._take(",")
            if self.index < len(self.tokens) and self.tokens[self.index].kind == "}":
                if not self.allow_comments:
                    raise _JsonSyntax("trailing comma is not valid JSON")
                closing = self._take("}")
                return _Node("object", opening.start, closing.end, members=tuple(members))

    def _array(self) -> _Node:
        opening = self._take("[")
        items: list[_Node] = []
        if self.index < len(self.tokens) and self.tokens[self.index].kind == "]":
            closing = self._take("]")
            return _Node("array", opening.start, closing.end, items=tuple(items))
        while True:
            items.append(self._value())
            if self.index >= len(self.tokens):
                raise _JsonSyntax("unterminated array")
            separator = self.tokens[self.index]
            if separator.kind == "]":
                self.index += 1
                return _Node("array", opening.start, separator.end, items=tuple(items))
            self._take(",")
            if self.index < len(self.tokens) and self.tokens[self.index].kind == "]":
                if not self.allow_comments:
                    raise _JsonSyntax("trailing comma is not valid JSON")
                closing = self._take("]")
                return _Node("array", opening.start, closing.end, items=tuple(items))


def plan_setup(repo: Path, integration: str, target: str | None = None) -> SetupPlan:
    """Plan one explicit consumer-owned setup projection without writing bytes."""
    if integration not in {"vscode", "npm"}:
        raise ValueError(f"unknown setup integration: {integration}")
    root = repo.resolve()
    command = f"dev setup {integration}"
    try:
        resolved = load_config(root)
    except ConfigError as error:
        return _blocked_plan(root, command, integration, "invalid-project-configuration", str(error))
    if resolved.effective.dev is None:
        return _blocked_plan(root, command, integration, "dev-configuration-missing", "svc.json does not declare dev targets.", resolved)
    profile = resolved.effective.dev.profile
    declared = resolved.effective.dev.profiles[profile].targets
    if target is not None:
        if target not in declared:
            return _blocked_plan(root, command, integration, "unknown-dev-target", f"Selected profile does not declare target {target!r}.", resolved, profile, (target,))
        targets = (target,)
    else:
        targets = tuple(sorted(declared))
    if integration == "vscode":
        writes, blockers, orphaned = _plan_vscode(root, targets)
    else:
        writes, blockers, orphaned = _plan_npm(root, targets)
    return SetupPlan(
        command,
        root,
        resolved.effective.svc_version,
        tuple(writes),
        tuple(blockers),
        integration,
        profile,
        targets,
        resolved.base_digest,
        resolved.local_digest,
        resolved.effective_digest,
        tuple(orphaned),
    )


def _blocked_plan(
    root: Path,
    command: str,
    integration: str,
    code: str,
    message: str,
    resolved: ResolvedConfig | None = None,
    profile: str | None = None,
    targets: tuple[str, ...] = (),
) -> SetupPlan:
    return SetupPlan(
        command,
        root,
        resolved.effective.svc_version if resolved else "",
        (),
        (Blocker(code, "svc.json", message),),
        integration,
        profile,
        targets,
        resolved.base_digest if resolved else None,
        resolved.local_digest if resolved else None,
        resolved.effective_digest if resolved else None,
    )


def _plan_vscode(root: Path, targets: tuple[str, ...]) -> tuple[list[PlannedWrite], list[Blocker], list[str]]:
    relative = ".vscode/tasks.json"
    path = root / ".vscode" / "tasks.json"
    blockers = _path_blockers(path, relative, allow_missing=True)
    parent = root / ".vscode"
    if parent.is_symlink():
        blockers.append(Blocker("setup-symlink", ".vscode", "VS Code directory must not be a symlink."))
    if blockers:
        return [], blockers, []
    if not path.exists():
        content = _new_tasks_document(targets)
        return [make_write(root, relative, "create", "create generated VS Code dev tasks", content)], [], []
    try:
        original = path.read_bytes()
        source = original.decode("utf-8")
        document = _JsoncDocument(source, allow_comments=True)
        if document.root.kind != "object":
            raise _JsonSyntax("tasks.json root must be an object")
        tasks_member = _member(document.root, "tasks")
        if tasks_member is not None and tasks_member.value.kind != "array":
            raise _JsonSyntax("tasks must be an array")
        if tasks_member is None:
            task_value = _render_tasks_value(targets, source, _item_indent(source, document.root))
            updated = _insert_object_property(source, document.root, "tasks", task_value)
            return [make_write(root, relative, "update", "insert generated VS Code dev tasks", updated.encode("utf-8"))], [], []
        updated, orphaned = _edit_tasks(source, document, tasks_member.value, targets)
    except (OSError, UnicodeDecodeError, _JsonSyntax) as error:
        return [], [Blocker("invalid-vscode-tasks", relative, str(error))], []
    if updated == source:
        return [], [], orphaned
    return [make_write(root, relative, "update", "insert generated VS Code dev tasks", updated.encode("utf-8"))], [], orphaned


def _plan_npm(root: Path, targets: tuple[str, ...]) -> tuple[list[PlannedWrite], list[Blocker], list[str]]:
    relative = "package.json"
    path = root / relative
    blockers = _path_blockers(path, relative, allow_missing=False)
    if blockers:
        return [], blockers, []
    try:
        original = path.read_bytes()
        source = original.decode("utf-8")
        document = _JsoncDocument(source, allow_comments=False)
        if document.root.kind != "object":
            raise _JsonSyntax("package.json root must be an object")
        scripts = _member(document.root, "scripts")
        if scripts is not None and scripts.value.kind != "object":
            raise _JsonSyntax("scripts must be an object")
        if scripts is None:
            value = _render_scripts_value(targets, source, _item_indent(source, document.root))
            updated = _insert_object_property(source, document.root, "scripts", value)
        else:
            updated = _edit_scripts(source, scripts.value, targets)
    except (OSError, UnicodeDecodeError, _JsonSyntax) as error:
        return [], [Blocker("invalid-package-json", relative, str(error))], []
    if updated == source:
        return [], [], []
    return [make_write(root, relative, "update", "insert generated SVC dev scripts", updated.encode("utf-8"))], [], []


def _path_blockers(path: Path, relative: str, *, allow_missing: bool) -> list[Blocker]:
    if not path.exists() and not path.is_symlink():
        if allow_missing:
            return []
        return [Blocker("setup-target-missing", relative, "Required consumer file does not exist.")]
    if path.is_symlink():
        return [Blocker("setup-symlink", relative, "Consumer setup target must not be a symlink.")]
    if not path.is_file():
        return [Blocker("setup-target-not-file", relative, "Consumer setup target must be a regular file.")]
    return []


def _edit_tasks(source: str, document: _JsoncDocument, tasks: _Node, selected: tuple[str, ...]) -> tuple[str, list[str]]:
    marked = _marked_tasks(source, document, tasks)
    selected_set = set(selected)
    for marked_target, item in marked.items():
        if not _clean_marked_task(source, item, marked_target):
            raise _JsonSyntax(f"generated task marker for {marked_target!r} is edited or malformed")
    labels: dict[str, _Node] = {}
    for item in tasks.items:
        if item.kind != "object":
            continue
        label = _member(item, "label")
        if label is not None and label.value.kind == "string":
            labels[str(label.value.value)] = item
    for target in selected:
        label = _task_label(target)
        owner = marked.get(target)
        if label in labels and (owner is None or labels[label] is not owner):
            raise _JsonSyntax(f"reserved task label already belongs to Consumer content: {label}")
    orphaned = sorted(target for target in marked if target not in selected_set)
    missing = tuple(target for target in selected if target not in marked)
    if not missing:
        return source, orphaned
    item_indent = _array_item_indent(source, tasks)
    rendered = [_render_task(target, source, tasks.start, indent=item_indent) for target in missing]
    return _append_array_items(source, tasks, rendered), orphaned


def _marked_tasks(source: str, document: _JsoncDocument, tasks: _Node) -> dict[str, _Node]:
    begins: list[tuple[_Token, str, str]] = []
    ends: list[tuple[_Token, str]] = []
    for comment in document.comments:
        begin = _MARKER.fullmatch(str(comment.value))
        end = _END_MARKER.fullmatch(str(comment.value))
        if begin:
            begins.append((comment, begin.group(1), begin.group(2)))
        elif end:
            ends.append((comment, end.group(1)))
        elif "svc:dev:" in str(comment.value):
            raise _JsonSyntax("malformed generated task marker")
    found: dict[str, _Node] = {}
    for begin, target, digest in begins:
        matching = [(end, end_target) for end, end_target in ends if end_target == target and end.start > begin.end]
        if len(matching) != 1:
            raise _JsonSyntax(f"ambiguous generated task marker for {target!r}")
        end = matching[0][0]
        enclosed = [item for item in tasks.items if begin.end <= item.start and item.end <= end.start]
        if len(enclosed) != 1 or target in found:
            raise _JsonSyntax(f"ambiguous generated task marker for {target!r}")
        item = enclosed[0]
        if any(item is candidate for candidate in found.values()):
            raise _JsonSyntax("one task has multiple generated markers")
        if not _only_trivia(source, begin.end, item.start) or not _only_trivia(source, item.end, end.start):
            raise _JsonSyntax(f"generated task marker for {target!r} does not bound one object")
        found[target] = item
        if _task_body_digest(item) != digest:
            raise _JsonSyntax(f"generated task marker for {target!r} has an invalid body digest")
    if len(begins) != len(ends):
        raise _JsonSyntax("unpaired generated task marker")
    for end, target in ends:
        if not any(begin_target == target and begin.start < end.start for begin, begin_target, _ in begins):
            raise _JsonSyntax(f"unpaired generated task marker for {target!r}")
    return found


def _clean_marked_task(source: str, item: _Node, target: str) -> bool:
    if item.kind != "object":
        return False
    expected = _task_object(target)
    actual = _node_to_value(item)
    return actual == expected


def _edit_scripts(source: str, scripts: _Node, targets: tuple[str, ...]) -> str:
    missing: list[tuple[str, str]] = []
    for target in targets:
        key = _script_key(target)
        expected = f"svc dev ensure {target}"
        member = _member(scripts, key)
        if member is None:
            missing.append((key, expected))
        elif member.value.kind != "string" or member.value.value != expected:
            raise _JsonSyntax(f"reserved script conflicts with Consumer value: {key}")
    if not missing:
        return source
    rendered = [f"{json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)}" for key, value in missing]
    return _append_object_properties(source, scripts, rendered)


def _member(node: _Node, key: str) -> _Member | None:
    return next((member for member in node.members if member.key == key), None)


def _node_to_value(node: _Node) -> Any:
    if node.kind in {"string", "scalar"}:
        return node.value
    if node.kind == "array":
        return [_node_to_value(item) for item in node.items]
    if node.kind == "object":
        return {member.key: _node_to_value(member.value) for member in node.members}
    raise AssertionError(node.kind)


def _task_object(target: str) -> dict[str, object]:
    return {
        "label": _task_label(target),
        "type": "process",
        "command": "svc",
        "args": ["dev", "ensure", target],
        "problemMatcher": [],
    }


def _task_body_digest(item: _Node) -> str:
    return sha256_bytes(canonical_json(_node_to_value(item)))


def _task_label(target: str) -> str:
    return f"svc:dev:{target}"


def _script_key(target: str) -> str:
    return f"svc:dev:{target}"


def _new_tasks_document(targets: tuple[str, ...]) -> bytes:
    rendered = "\n".join(_render_task(target, "", 0, indent="    ") for target in targets)
    if len(targets) > 1:
        rendered = rendered.replace("\n    /* svc:dev:begin", ",\n    /* svc:dev:begin")
    return ("{\n  \"version\": \"2.0.0\",\n  \"tasks\": [\n" + rendered + "\n  ]\n}\n").encode("utf-8")


def _render_tasks_value(targets: tuple[str, ...], source: str, base: str) -> str:
    line_ending = _line_ending(source)
    item_indent = base + "  "
    rendered = ("," + line_ending).join(_render_task(target, source, 0, indent=item_indent) for target in targets)
    return "[" + line_ending + rendered + line_ending + base + "]"


def _render_scripts_value(targets: tuple[str, ...], source: str, base: str) -> str:
    line_ending = _line_ending(source)
    item_indent = base + "  "
    values = [f"{item_indent}{json.dumps(_script_key(target))}: {json.dumps(f'svc dev ensure {target}')}" for target in targets]
    return "{" + line_ending + ("," + line_ending).join(values) + line_ending + base + "}"


def _render_task(target: str, source: str, position: int, *, indent: str | None = None) -> str:
    line_ending = _line_ending(source)
    item_indent = indent if indent is not None else _line_indent(source, position) + "  "
    property_indent = item_indent + "  "
    body = _task_object(target)
    rendered_object = (
        item_indent
        + "{"
        + line_ending
        + property_indent
        + json.dumps("label")
        + ": "
        + json.dumps(body["label"])
        + ","
        + line_ending
        + property_indent
        + json.dumps("type")
        + ": "
        + json.dumps(body["type"])
        + ","
        + line_ending
        + property_indent
        + json.dumps("command")
        + ": "
        + json.dumps(body["command"])
        + ","
        + line_ending
        + property_indent
        + json.dumps("args")
        + ": "
        + json.dumps(body["args"])
        + ","
        + line_ending
        + property_indent
        + json.dumps("problemMatcher")
        + ": []"
        + line_ending
        + item_indent
        + "}"
    )
    digest = sha256_bytes(canonical_json(body))
    return (
        item_indent
        + f"/* svc:dev:begin target={target} body-sha256={digest} */"
        + line_ending
        + rendered_object
        + line_ending
        + item_indent
        + f"/* svc:dev:end target={target} */"
    )


def _insert_object_property(source: str, node: _Node, key: str, value: str) -> str:
    return _append_object_properties(source, node, [f"{json.dumps(key)}: {value}"])


def _append_object_properties(source: str, node: _Node, properties: list[str]) -> str:
    closing = node.end - 1
    line_ending = _line_ending(source)
    indent = _item_indent(source, node)
    rendered = ("," + line_ending).join(indent + property for property in properties)
    if not node.members:
        insertion = line_ending + rendered + line_ending + _line_indent(source, node.start)
        return source[:closing] + insertion + source[closing:]
    last = node.members[-1].value
    trailing = _has_separator(source, last.end, closing)
    prefix = "" if trailing else ","
    suffix = "," if trailing else ""
    tail = source[last.end:closing]
    before, separator = _tail_before_append(tail, line_ending)
    insertion = separator + rendered + suffix + line_ending + _line_indent(source, closing)
    return source[:last.end] + prefix + before + insertion + source[closing:]


def _append_array_items(source: str, node: _Node, items: list[str]) -> str:
    closing = node.end - 1
    line_ending = _line_ending(source)
    rendered = ("," + line_ending).join(items)
    if not node.items:
        insertion = line_ending + rendered + line_ending + _line_leading_indent(source, node.start)
        return source[:closing] + insertion + source[closing:]
    last = node.items[-1]
    trailing = _has_separator(source, last.end, closing)
    prefix = "" if trailing else ","
    suffix = "," if trailing else ""
    tail = source[last.end:closing]
    before, separator = _tail_before_append(tail, line_ending)
    insertion = separator + rendered + suffix + line_ending + _line_indent(source, closing)
    return source[:last.end] + prefix + before + insertion + source[closing:]


def _has_separator(source: str, start: int, end: int) -> bool:
    return "," in source[start:end]


def _item_indent(source: str, node: _Node) -> str:
    if node.members:
        return _line_indent(source, node.members[0].key_token.start)
    return _line_indent(source, node.start) + "  "


def _array_item_indent(source: str, node: _Node) -> str:
    if node.items:
        return _line_indent(source, node.items[0].start)
    return _line_leading_indent(source, node.start) + "  "


def _tail_before_append(tail: str, line_ending: str) -> tuple[str, str]:
    """Keep trailing comments/separators, but relocate only closing indentation."""
    newline = tail.rfind("\n")
    if newline >= 0 and not tail[newline + 1 :].strip(" \t\r"):
        return tail[: newline + 1], ""
    return tail, line_ending


def _line_indent(source: str, position: int) -> str:
    start = source.rfind("\n", 0, position) + 1
    prefix = source[start:position]
    return prefix if prefix.strip(" \t\r") == "" else ""


def _line_leading_indent(source: str, position: int) -> str:
    start = source.rfind("\n", 0, position) + 1
    line = source[start:position]
    return line[: len(line) - len(line.lstrip(" \t\r"))]


def _line_ending(source: str) -> str:
    return "\r\n" if "\r\n" in source else "\n"


def _only_trivia(source: str, start: int, end: int) -> bool:
    fragment = source[start:end]
    fragment = re.sub(r"//[^\r\n]*", "", fragment)
    fragment = re.sub(r"/\*.*?\*/", "", fragment, flags=re.DOTALL)
    return not fragment.strip()
