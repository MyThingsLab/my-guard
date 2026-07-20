from importlib.metadata import version

from myguard.ask import AskChannel, SubprocessAsk, ask_channel_from_env
from myguard.guard import Guard
from myguard.rules import MERGE_ACTION, Rule, default_rules

__version__ = version("my-guard")

__all__ = [
    "MERGE_ACTION",
    "AskChannel",
    "Guard",
    "Rule",
    "SubprocessAsk",
    "ask_channel_from_env",
    "default_rules",
]
