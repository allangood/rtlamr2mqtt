from enum import Enum

class Level(Enum):
    DEBUG = 4      # Outputs everything
    INFO = 3       # Outputs info messages
    WARNING = 2    # Outputs only warnings and critical messages
    CRITICAL = 1   # Outputs critical/crash messages
    NONE = 0       # No output
