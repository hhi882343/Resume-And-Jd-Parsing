"""
Core type definitions for the Resume Parser Module.
"""
from typing import TypedDict, Literal, Optional, List, Dict, Any, Union


class ParsedCandidateResume(TypedDict, total=False):
    candidateName: Optional[str]
    email: Optional[str]
    contactNumber: Optional[str]
    linkedinUrl: Optional[str]
    highestQualification: Optional[str]
    skillsRaw: Optional[str]
    technologiesRaw: Optional[str]
    technologies: Optional[str]
    totalExperience: Optional[str]
    relevantExperience: Optional[str]
    currentEmployer: Optional[str]
    currentLocation: Optional[str]
    location: Optional[str]
    sourceFile: str
    parser: Literal['metaforge', 'legacy']
    role: Optional[str]


class CoreParsedFields(TypedDict, total=False):
    candidateName: Optional[str]
    email: Optional[str]
    contactNumber: Optional[str]
    linkedinUrl: Optional[str]
    highestQualification: Optional[str]
    educationRaw: Optional[str]
    skillsRaw: Optional[str]
    technologiesRaw: Optional[str]
    technologies: Optional[str]
    totalExperienceYears: Optional[Union[float, int]]
    totalExperienceText: Optional[str]
    relevantExperience: Optional[str]
    currentCompany: Optional[str]
    currentLocation: Optional[str]
    location: Optional[str]
    role: Optional[str]


class BulkParseItemDone(TypedDict):
    sourceFile: str
    status: Literal['done']
    data: ParsedCandidateResume


class BulkParseItemError(TypedDict):
    sourceFile: str
    status: Literal['error']
    error: str


BulkParseItemResult = Union[BulkParseItemDone, BulkParseItemError]


class ExtractResumeTextResult(TypedDict, total=False):
    text: str
    error: Optional[str]


class WorkPeriod(TypedDict, total=False):
    start: Optional[str]
    end: Optional[str]
    from_: Optional[str]
    to: Optional[str]


class MetaforgeParsed(TypedDict, total=False):
    full_name: Optional[str]
    contact: Optional[str]
    email: Optional[str]
    linkedin: Optional[str]
    qualification: Optional[str]
    total_experience: Optional[str]
    relevant_experience: Optional[str]
    skills: Optional[List[str]]
    technology: Optional[List[str]]
    role: Optional[str]
    location: Optional[str]
    current_location: Optional[str]
    current_employer: Optional[str]
    work_periods: Optional[List[Dict[str, Any]]]
    relevant_work_periods: Optional[List[Dict[str, Any]]]


class ResumeParserOptions(TypedDict, total=False):
    enableAi: Optional[bool]
    geminiApiKey: Optional[str]
    geminiModel: Optional[str]
    fallbackModels: Optional[List[str]]


class ChatMessage(TypedDict):
    role: Literal['user', 'assistant', 'system']
    content: str


class ChatWithContextOptions(TypedDict, total=False):
    messages: List[ChatMessage]
    candidateProfile: Optional[Dict[str, Any]]

