# Names of events that Spamphibian will process.
# The names are either the names of the actions
# sent by GitLab System Hooks or derived from
# the actions they represent.

project_events = [
    "project_create",
    "project_rename",
    "project_transfer",
]

user_events = [
    "user_create",
    "user_rename",
]

issue_events = [
    "issue_open",
    "issue_update",
    "issue_close",
    "issue_reopen",
]

issue_note_events = [
    "issue_note_create",
    "issue_note_update",
]

group_events = [
    "group_create",
    "group_rename",
]

snippet_events = [
    "snippet_check",
]

event_types = (
    user_events
    + project_events
    + issue_events
    + issue_note_events
    + group_events
    + snippet_events
)
