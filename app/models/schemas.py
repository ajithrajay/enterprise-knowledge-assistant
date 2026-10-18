from pydantic import BaseModel, Field
from enum import IntEnum
from typing import Optional

class RoleLevel(IntEnum):
    intern = 0
    employee = 1
    manager = 2
    hr_admin = 3

class UserIn(BaseModel):
    username: str
    password: str
    role: str = "employee"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str

class ChatIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)

class Source(BaseModel):
    doc_id: str
    title: str
    version: str
    snippet: str
    score: float

class ChatOut(BaseModel):
    id: str
    answer: str
    sources: list[Source] = []
    confidence: Optional[float] = None
    refused: bool
    latency_ms: int

class TicketIn(BaseModel):
    summary: str = Field(min_length=5, max_length=300)
    confirmed: bool = False

class TicketOut(BaseModel):
    status: str
    ticket_id: Optional[str] = None
    message: Optional[str] = None

class IngestIn(BaseModel):
    title: str
    version: str
    min_role: str = "employee"
    text: str

class LLMAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
