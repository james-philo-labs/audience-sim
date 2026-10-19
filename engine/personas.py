"""persona-scope-0.2: project only approved base fields and the selected post override."""

from copy import deepcopy

VERSION = "persona-scope-0.2"
POSTS = frozenset({"example", "opus", "gdpval", "omni"})
FIELDS = (
    "id",
    "name",
    "role",
    "education_technical_background",
    "interests",
    "prior_knowledge",
    "reading_goal",
    "continue_signals",
    "leave_signals",
    "version",
    "evidence_status",
)
LISTS = frozenset({"interests", "continue_signals", "leave_signals"})
OVERRIDES = frozenset({"reading_goal", "prior_knowledge", "interests"})
REQUIRED = frozenset(
    {
        "id",
        "role",
        "education_technical_background",
        "interests",
        "prior_knowledge",
        "reading_goal",
    }
)


def assemble(profile, post):
    if post not in POSTS:
        raise ValueError("Unknown selected post")
    if not isinstance(profile, dict):
        raise ValueError("Profile must be an object")
    persona = {k: deepcopy(profile[k]) for k in FIELDS if k in profile}
    overrides = profile.get("post_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("Invalid post override catalog")
    selected = overrides.get(post, {})
    if not isinstance(selected, dict) or set(selected) - OVERRIDES:
        raise ValueError("Selected override contains unsupported fields")
    persona.update(deepcopy(selected))
    if REQUIRED - set(persona):
        raise ValueError("Missing required profile field")
    for key, value in persona.items():
        if key in LISTS:
            if (
                not isinstance(value, list)
                or not value
                or not all(isinstance(x, str) and x.strip() for x in value)
            ):
                raise ValueError("Invalid list field " + key)
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("Invalid string field " + key)
    return persona, {
        "version": VERSION,
        "selected_post": post,
        "applied_override": post if selected else None,
        "withheld_override_keys": sorted(k for k in overrides if k != post),
        "forwarded_fields": sorted(persona),
        "catalog_not_forwarded": True,
    }
