from pydantic import BaseModel


class WorkDocReport(BaseModel):
    workdoc_id: int
    status: str
    report: str
