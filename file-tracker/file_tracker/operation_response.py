import enum
import json


class OperationStatus(enum.Enum):
    SUCCESS = "success"
    INVALID = "invalid"
    ERROR = "error"


class OperationResponse:

    def __init__(self, status=OperationStatus.SUCCESS, message=None):
        self.status = status
        self.message = message

    def to_dict(self):
        return {"status": self.status.value, "message": self.message}

    def to_json_string(self):
        return json.dumps(self.to_dict())
