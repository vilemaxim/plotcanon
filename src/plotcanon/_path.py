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
report agree.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def _passage(story, name):
    """The scene or ending a step names, or None."""
    found = story.passage(name)
    return None if found is None or found.kind == START else found


def _ways_on(passage):
    """What can follow a passage in a Path, for saying so: the passages its
    exits lead to, then its Contests."""
    ways = []
    for exit in passage.exits:
        if exit.passage is not None and f"`{exit.passage}`" not in ways:
            ways.append(f"`{exit.passage}`")
    ways.extend(f"the Contest `{c.label}`" for c in passage.contests)
    return ", ".join(ways) if ways else "none"


SHAPE = ("must be the name of a scene or outcome, `hook: <the Hook taken>`, or "
         "`contest: <the Contest>` with `result: <the result taken>`")


def _shape(step):
    """A step as `("passage", name)`, `("hook", label)` or
    `("contest", label, result)`, or None when it is none of those."""
    if isinstance(step, str) and step.strip():
        return ("passage", step)
    if not isinstance(step, dict):
        return None
    if set(step) == {"hook"} and isinstance(step["hook"], str) and step["hook"].strip():
        return ("hook", step["hook"])
    if set(step) == {"contest", "result"} and all(
            isinstance(step[k], str) and step[k].strip() for k in step):
        return ("contest", step["contest"], step["result"])
    return None


def _named(choices, label):
    return next((c for c in choices if key(c.label) == key(label)), None)


def check_path(story, steps, *, continues_from=None):
    """`steps` read against `story`. Returns a `Path`. It never raises on what
    `steps` holds; what does not fit is in `path.problems`.

    A Path starts with the Hook taken. `continues_from` is where the Path of
    the report before this one on the same Mod stopped, a scene's name, when
    there is one: this Path may start there instead.
    """
    if not isinstance(steps, (list, tuple)) or not steps:
        return Path(tuple(steps) if isinstance(steps, (list, tuple)) else (steps,), None,
                    ("`path` must be a list of steps",))
    problems = []
    # What the next step must follow on from: "start", a Passage, a
    # (passage name, what leads there) pair, or None when it is not known.
    here = "start"
    for i, step in enumerate(steps):
        where = f"`path[{i}]`"
        shape = _shape(step)
        if shape is None:
            problems.append(f"{where} {SHAPE}")
            here = None
        elif shape[0] == "hook":
            hook = _named(story.start.exits if story.start else (), shape[1])
            if hook is None:
                problems.append(f"{where}: `{shape[1]}` is not one of the Mod's Hooks")
                here = None
                continue
            if here != "start":
                problems.append(f"{where}: a Hook can only be the first step of a Path")
            here = (hook.passage, f"the Hook `{hook.label}`")
        elif shape[0] == "contest":
            label, result = shape[1], shape[2]
            if not any(_named(p.contests, label) for p in story.passages):
                problems.append(f"{where}: `{label}` is not a Contest in the Mod")
                here = None
                continue
            contest = _named(here.contests, label) if isinstance(here, Passage) else None
            if contest is None:
                if here is not None:
                    problems.append(f"{where}: the Contest `{label}` cannot be reached from "
                                    f"{_after(here)}")
                contest = next(_named(p.contests, label) for p in story.passages
                               if _named(p.contests, label))
            taken = _named(contest.results, result)
            if taken is None:
                results = ", ".join(f"`{r.label}`" for r in contest.results) or "none"
                problems.append(f"{where}: the Contest `{contest.label}` has no result "
                                f"`{result}` — its results are {results}")
                here = None
                continue
            here = (taken.passage, f"the result `{taken.label}` of the Contest "
                                   f"`{contest.label}`")
        else:
            passage = _passage(story, shape[1])
            if passage is None:
                problems.append(f"{where}: `{shape[1]}` is not a scene or outcome of the Mod")
            elif isinstance(here, tuple):
                if passage.name != here[0]:
                    problems.append(f"{where}: `{passage.name}` is not where {here[1]} leads, "
                                    f"which is `{here[0]}`")
            elif isinstance(here, Passage):
                if not any(e.passage == passage.name for e in here.exits):
                    problems.append(f"{where}: `{passage.name}` cannot be reached from "
                                    f"`{here.name}` — its ways on are {_ways_on(here)}")
            elif here == "start":
                stopped = None if continues_from is None else _passage(story, continues_from)
                if stopped is None or stopped.name != passage.name:
                    last = "" if stopped is None else f" (`{stopped.name}`)"
                    problems.append(f"{where}: a Path starts with the Hook taken "
                                    f"(`hook: <the Hook>`), or where the last report's Path "
                                    f"stopped{last}, not at `{passage.name}`")
            here = passage
    end = here if isinstance(here, Passage) else None
    if isinstance(here, tuple):
        problems.append(f"`path[{len(steps) - 1}]`: a Path ends at the scene or outcome where "
                        f"play stopped — add `{here[0]}`, where {here[1]} leads")
    return Path(tuple(steps), None if problems else end, tuple(problems))


def _after(here):
    if here == "start":
        return "the start of the Path, which is a Hook"
    if isinstance(here, tuple):
        return f"{here[1]}, which leads to `{here[0]}`"
    return f"`{here.name}`"


def path_steps(story, choices, *, continues_from=None):
    """The steps of a Path, as a report's `path` holds them, from the choices
    taken in a walk through `story`'s Dry Run.

    The walk starts at the Premise, so the first choice is a Hook, or, given
    `continues_from`, at that scene, where the last report's Path stopped.
    Each of `choices` is an `Exit` from the `choices` of the passage the walk
    has reached. A Contest's result is written as the Contest and the result.
    Every step a Hook or a Contest leads to is written as its own step, so the
    last step is where the walk stopped.

    Raises ValueError for a choice that is not one of the ways on from where
    the walk is, or a `continues_from` that is not a scene or outcome.
    """
    if continues_from is None:
        here, steps = story.start, []
        if here is None:
            raise ValueError("the story has no Premise for a walk to start from")
    else:
        here = _passage(story, continues_from)
        if here is None:
            raise ValueError(f"`{continues_from}` is not a scene or outcome of the Mod")
        steps = [here.name]
    for choice in choices:
        if not isinstance(choice, Exit):
            raise TypeError(f"a choice is an Exit, not {type(choice).__name__}")
        if here.kind == START and choice in here.exits:
            steps.append({"hook": choice.label})
        elif choice in here.exits:
            pass
        else:
            contest = next((c for c in here.contests if choice in c.results), None)
            if contest is None:
                raise ValueError(f"`{getattr(choice, 'label', choice)}` is not a way on "
                                 f"from `{here.name}`")
            steps.append({"contest": contest.label, "result": choice.label})
        here = _passage(story, choice.passage) if choice.passage else None
        if here is None:
            raise ValueError(f"`{choice.label}` leads to no scene or outcome")
        steps.append(here.name)
    return steps
