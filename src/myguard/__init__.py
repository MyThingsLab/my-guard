from importlib.metadata import version

from myguard.ask import AskChannel, SubprocessAsk, ask_channel_from_env
from myguard.guard import Guard
from myguard.paths import RULES_FILE, ProjectRules, action_paths, find_root
from myguard.rules import MERGE_ACTION, Rule, default_rules

__version__ = version("my-guard")

__all__ = [
    "MERGE_ACTION",
    "RULES_FILE",
    "AskChannel",
    "Guard",
    "ProjectRules",
    "Rule",
    "SubprocessAsk",
    "action_paths",
    "ask_channel_from_env",
    "default_rules",
    "find_root",
]
