"""A Path: the way one Stretch went through a Mod's Dry Run, as an
After-Action Report's `path` writes it (`schema/after-action.md`).

    path:
      - hook: The sister asks them to close what was opened
      - The descent
      - Who rings it
      - contest: stop her before the last stroke
        result: win
      - The bell is silenced

`check_path` reads such a list against a `Story`, and `path_steps` writes one
from the choices taken in a walk through it, so a walk and the checks on a
report agree. Where a Path may start depends on where the last report on the
same Mod stopped, a `LastStop`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import yaml

from ._story import ENDING, START, Exit, Passage, key


@dataclass(frozen=True)
class Path:
    """A report's Path read against its Mod's story.

    `steps` are the steps as given. `end` is the `Passage` where play stopped,
    the last step, or None when the Path has problems. `problems` say what in
    the Path does not fit the story, one sentence each.
    """

    steps: tuple
    end: Passage | None
    problems: tuple = ()

    @property
    def ok(self):
        return not self.problems

    @property
    def finished(self):
        """Whether the Path reaches an ending, which proposes that the Mod has
        nothing left to play. None when the Path has problems."""
        return None if self.end is None else self.end.kind == ENDING


@dataclass(frozen=True)
class LastStop:
    """Where play stopped on a Mod before a report, which says where the
    report's Path may start.

    - `LastStop()`: there is no earlier report, so a Path starts at a Hook.
    - `LastStop("The bell")`: the last report's Path stopped at that scene, so
      a Path starts there or at a Hook.
    - `LastStop(known=False)`: there is an earlier report, but it has no Path
      that fits, so where it stopped is not known and a Path may start at any
      scene.
    - `LastStop(among=("The bell", "Who rings it"))`: play comes back together
      after a split, and the Groups that had not finished stopped at these
      scenes, so a Path starts at one of them or at a Hook.
    """

    passage: str | None = None
    known: bool = True
    among: tuple = ()

    def __post_init__(self):
        if self.passage is not None and not self.known:
            raise ValueError("a stop that is not known has no passage")
        if self.among and (self.passage is not None or not self.known
                           or len(self.among) < 2):
            raise ValueError("a stop among several scenes names two or more, and nothing else")
        object.__setattr__(self, "among", tuple(self.among))

    @property
    def passages(self):
        """Every scene or ending a Path may start at besides a Hook, when where
        play stopped is known."""
        return self.among or (() if self.passage is None else (self.passage,))

    def lets_start_at(self, name):
        """Whether a Path may start at the scene or ending `name`."""
        if not self.known:
            return True
        return any(key(passage) == key(name) for passage in self.passages)

    def described(self):
        """Where a Path may start besides a Hook, for saying so."""
        if self.among:
            either = " or ".join(f"`{passage}`" for passage in self.among)
            return f"where the Path of one of the Groups that had not finished stopped ({either})"
        last = "" if self.passage is None else f" (`{self.passage}`)"
        return f"where the last report's Path stopped{last}"


def as_last_stop(continues_from):
    """A `continues_from` as a `LastStop`: None is no earlier report, and a
    scene's name is where the last report's Path stopped."""
    if continues_from is None:
        return LastStop()
    if isinstance(continues_from, LastStop):
        return continues_from
    if isinstance(continues_from, str):
        return LastStop(continues_from)
    raise TypeError("where the last Stretch stopped is a LastStop or a scene's name, not "
                    f"{type(continues_from).__name__}")


def has_path(steps):
    """Whether a report's `path`, or a Path given to an Interview, holds a
    Path at all. A missing or empty one does not."""
    return steps is not None and steps != [] and steps != ()


def _passage(story, name):
    """The scene or ending a step names, or None."""
    found = story.passage(name)
    return None if found is None or found.kind == START else found


def _named(choices, label):
    return next((c for c in choices if key(c.label) == key(label)), None)


def _ways_on(passage):
    """What can follow a passage in a Path, for saying so: the passages its
    exits lead to, then its Contests."""
    ways = []
    for exit in passage.exits:
        if exit.passage is not None and f"`{exit.passage}`" not in ways:
            ways.append(f"`{exit.passage}`")
    ways.extend(f"the Contest `{c.label}`" for c in passage.contests)
    return ", ".join(ways) if ways else "none"


def _scalar(text):
    """Text as a YAML value: as it is when YAML reads it back the same, quoted
    otherwise."""
    try:
        if yaml.safe_load(text) == text and "#" not in text:
            return text
    except yaml.YAMLError:
        pass
    return json.dumps(text, ensure_ascii=False)


@dataclass(frozen=True)
class _Here:
    """Where a Path has got to: what its next step must follow on from.

    `passage` is the scene or ending reached. `leads_to` is the passage a Hook
    or a Contest's result just taken leads to, and `via` says which. `at_start`
    is true before the first step. With none of these, where the Path has got
    to is not known, after a step that does not fit.
    """

    passage: Passage | None = None
    leads_to: str | None = None
    via: str = ""
    at_start: bool = False

    def described(self):
        if self.at_start:
            return "the start of the Path, which is a Hook"
        if self.leads_to is not None:
            return f"{self.via}, which leads to `{self.leads_to}`"
        return f"`{self.passage.name}`"

    @property
    def known(self):
        return self.at_start or self.passage is not None or self.leads_to is not None


LOST = _Here()


@dataclass(frozen=True)
class _SceneStep:
    name: str

    def follow(self, story, here, stop, where, problems):
        passage = _passage(story, self.name)
        if passage is None:
            problems.append(f"{where}: `{self.name}` is not a scene or outcome of the Mod")
            return LOST
        if here.leads_to is not None:
            if passage.name != here.leads_to:
                problems.append(f"{where}: `{passage.name}` is not where {here.via} leads, "
                                f"which is `{here.leads_to}`")
        elif here.passage is not None:
            if not any(e.passage == passage.name for e in here.passage.exits):
                problems.append(f"{where}: `{passage.name}` cannot be reached from "
                                f"`{here.passage.name}` — its ways on are "
                                f"{_ways_on(here.passage)}")
        elif here.at_start and not stop.lets_start_at(passage.name):
            problems.append(f"{where}: a Path starts with the Hook taken "
                            f"(`hook: <the Hook>`), or {stop.described()}, "
                            f"not at `{passage.name}`")
        return _Here(passage=passage)

    def written(self):
        return self.name

    def yaml_lines(self):
        return [f"  - {_scalar(self.name)}"]


@dataclass(frozen=True)
class _HookStep:
    label: str

    def follow(self, story, here, stop, where, problems):
        hook = _named(story.start.exits if story.start else (), self.label)
        if hook is None:
            problems.append(f"{where}: `{self.label}` is not one of the Mod's Hooks")
            return LOST
        if not here.at_start:
            problems.append(f"{where}: a Hook can only be the first step of a Path")
        return _Here(leads_to=hook.passage, via=f"the Hook `{hook.label}`")

    def written(self):
        return {"hook": self.label}

    def yaml_lines(self):
        return [f"  - hook: {_scalar(self.label)}"]


@dataclass(frozen=True)
class _ContestStep:
    label: str
    result: str

    def follow(self, story, here, stop, where, problems):
        anywhere = [c for p in story.passages for c in p.contests
                    if key(c.label) == key(self.label)]
        if not anywhere:
            problems.append(f"{where}: `{self.label}` is not a Contest in the Mod")
            return LOST
        contest = _named(here.passage.contests, self.label) if here.passage else None
        if contest is None:
            if here.known:
                problems.append(f"{where}: the Contest `{self.label}` cannot be reached "
                                f"from {here.described()}")
            contest = anywhere[0]
        taken = _named(contest.results, self.result)
        if taken is None:
            results = ", ".join(f"`{r.label}`" for r in contest.results) or "none"
            problems.append(f"{where}: the Contest `{contest.label}` has no result "
                            f"`{self.result}` — its results are {results}")
            return LOST
        return _Here(leads_to=taken.passage,
                     via=f"the result `{taken.label}` of the Contest `{contest.label}`")

    def written(self):
        return {"contest": self.label, "result": self.result}

    def yaml_lines(self):
        return [f"  - contest: {_scalar(self.label)}", f"    result: {_scalar(self.result)}"]


SHAPE = ("must be the name of a scene or outcome, `hook: <the Hook taken>`, or "
         "`contest: <the Contest>` with `result: <the result taken>`")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _step(raw):
    """A step as written in a report, read; None when it has no shape a step
    has."""
    if _text(raw):
        return _SceneStep(raw)
    if not isinstance(raw, dict):
        return None
    if set(raw) == {"hook"} and _text(raw["hook"]):
        return _HookStep(raw["hook"])
    if set(raw) == {"contest", "result"} and _text(raw["contest"]) and _text(raw["result"]):
        return _ContestStep(raw["contest"], raw["result"])
    return None


def check_path(story, steps, *, continues_from=None):
    """`steps` read against `story`. Returns a `Path`. It never raises on what
    `steps` holds; what does not fit is in `path.problems`.

    `continues_from` is where play stopped before this report: a `LastStop`
    (see `last_stop`), a scene's name where the last report's Path stopped,
    or None when there is no earlier report. A Path starts with the Hook
    taken, or where the last report's Path stopped, or, when that is not
    known, at any scene.
    """
    stop = as_last_stop(continues_from)
    if not isinstance(steps, (list, tuple)) or not steps:
        return Path(tuple(steps) if isinstance(steps, (list, tuple)) else (steps,), None,
                    ("`path` must be a list of steps",))
    problems = []
    here = _Here(at_start=True)
    for i, raw in enumerate(steps):
        where = f"`path[{i}]`"
        step = _step(raw)
        if step is None:
            problems.append(f"{where} {SHAPE}")
            here = LOST
            continue
        here = step.follow(story, here, stop, where, problems)
    if here.leads_to is not None:
        problems.append(f"`path[{len(steps) - 1}]`: a Path ends at the scene or outcome where "
                        f"play stopped — add `{here.leads_to}`, where {here.via} leads")
    return Path(tuple(steps), None if problems else here.passage, tuple(problems))


def path_steps(story, choices, *, continues_from=None, start=None):
    """The steps of a Path, as a report's `path` holds them, from the choices
    taken in a walk through `story`'s Dry Run.

    The walk starts at the Premise, so the first choice is a Hook, or at the
    scene `start`. `continues_from` is where play stopped before, as
    `check_path` takes it, and says whether the walk may start at `start`:
    where the last report's Path stopped, or any scene when that is not known.

    Each of `choices` is an `Exit` from the `choices` of the passage the walk
    has reached. A Contest's result is written as the Contest and the result.
    Every step a Hook or a Contest leads to is written as its own step, so the
    last step is where the walk stopped.

    Raises ValueError for a choice that is not one of the ways on from where
    the walk is, or a `start` that is not a scene or outcome or that the walk
    may not start at.
    """
    stop = as_last_stop(continues_from)
    if start is None:
        here, steps = story.start, []
        if here is None:
            raise ValueError("the story has no Premise for a walk to start from")
    else:
        here = _passage(story, start)
        if here is None:
            raise ValueError(f"`{start}` is not a scene or outcome of the Mod")
        if not stop.lets_start_at(here.name):
            raise ValueError(f"a walk starts at a Hook or {stop.described()}, "
                             f"not at `{here.name}`")
        steps = [_SceneStep(here.name)]
    for choice in choices:
        if not isinstance(choice, Exit):
            raise TypeError(f"a choice is an Exit, not {type(choice).__name__}")
        if here.kind == START and choice in here.exits:
            steps.append(_HookStep(choice.label))
        elif choice not in here.exits:
            contest = next((c for c in here.contests if choice in c.results), None)
            if contest is None:
                raise ValueError(f"`{choice.label}` is not a way on from `{here.name}`")
            steps.append(_ContestStep(contest.label, choice.label))
        here = _passage(story, choice.passage) if choice.passage else None
        if here is None:
            raise ValueError(f"`{choice.label}` leads to no scene or outcome")
        steps.append(_SceneStep(here.name))
    return [step.written() for step in steps]


def path_yaml(steps):
    """A Path's steps as the YAML a report holds them in, `path:` included.
    Each step must have one of the shapes a step has."""
    lines = ["path:"]
    for raw in steps:
        step = _step(raw)
        if step is None:
            raise ValueError(f"a step {SHAPE}, not {raw!r}")
        lines.extend(step.yaml_lines())
    return "\n".join(lines) + "\n"
