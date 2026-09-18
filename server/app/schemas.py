"""Loose Pydantic models — defaults match previous Flask silent/force JSON parsing."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateKbBody(BaseModel):
    name: str = "Untitled"
    description: str = ""


class InstructionBody(BaseModel):
    instruction: str = ""


class LlmSettingsBody(BaseModel):
    base_url: str = ""
    api_key: Optional[str] = None
    model: str = ""
    model_fast: str = ""


class LlmTestBody(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    model_fast: Optional[str] = None
    which: Literal["model", "model_fast"] = "model"


class FileContentBody(BaseModel):
    content: Any = None


class StreamFlagBody(BaseModel):
    stream: bool = False


class BuildBody(BaseModel):
    stream: bool = False


class UpdateBody(BaseModel):
    source_dir: Optional[str] = None
    stream: bool = False


class QueryBody(BaseModel):
    question: str = ""
    stream: bool = False


class ImportDirBody(BaseModel):
    source_dir: str = ""
    stream: bool = False
