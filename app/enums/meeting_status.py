import enum

class MeetingStatus(enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"