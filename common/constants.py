# Names of events that Spamphibian will process.
# The names are either the names of the actions
# sent by GitLab System Hooks or derived from
# the actions they represent.

from enum import Enum

class ProjectEvent(Enum):
    PROJECT_CREATE = "project_create"
    PROJECT_RENAME = "project_rename"
    PROJECT_TRANSFER = "project_transfer"

class UserEvent(Enum):
    USER_CREATE = "user_create"
    USER_RENAME = "user_rename"

class IssueEvent(Enum):
    ISSUE_OPEN = "issue_open"
    ISSUE_UPDATE = "issue_update"
    ISSUE_CLOSE = "issue_close"
    ISSUE_REOPEN = "issue_reopen"

class IssueNoteEvent(Enum):
    ISSUE_NOTE_CREATE = "issue_note_create"
    ISSUE_NOTE_UPDATE = "issue_note_update"

class GroupEvent(Enum):
    GROUP_CREATE = "group_create"
    GROUP_RENAME = "group_rename"

class SnippetEvent(Enum):
    SNIPPET_CHECK = "snippet_check"
