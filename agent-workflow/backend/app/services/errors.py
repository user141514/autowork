class WorkflowError(Exception):
    status_code = 400


class NotFoundError(WorkflowError):
    status_code = 404


class InvalidStateError(WorkflowError):
    status_code = 409


class PolicyViolationError(WorkflowError):
    status_code = 403
