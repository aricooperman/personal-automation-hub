from enum import Enum, unique


@unique
class MimeType(Enum):
    TEXT = 1
    HTML = 2
    PDF = 3
    IMG = 4
    OTHER = 5
