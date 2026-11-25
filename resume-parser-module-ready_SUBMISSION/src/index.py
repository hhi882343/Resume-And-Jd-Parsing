"""
Resume Parser Module (Python Parity Port)

A self-contained, enterprise-grade resume parsing engine with:
1. Hybrid Gemini AI extraction (Gemini 3.8 Flash with multi-model fallback & context chat).
2. Deterministic local fallback parser (zero external API dependency).
3. Multi-format text extraction (PDF, DOCX, DOC, TXT, OCR).
4. Strict extraction rules (verbatim skills, 10-skill cap, professional roles, location).
"""

# Types
from .types import (
    ParsedCandidateResume,
    CoreParsedFields,
    BulkParseItemResult,
    ExtractResumeTextResult,
    MetaforgeParsed,
    ResumeParserOptions,
    ChatMessage,
    ChatWithContextOptions,
)

# Core Orchestration & Parsing API
from .metaforgeParser import (
    parseResumeBuffer,
    parseResumeBuffersBulk,
    parseResumeBufferWithMetaforge,
    parseResumeBufferLegacy,
    isMetaforgeParserAvailable,
    getAiParsingSuspendedReason,
    applyEvidenceLock,
)

# Local Deterministic Parser
from .parseCoreResumeFields import (
    parseCoreFieldsFromResumeText,
    extractTotalExperienceInfo,
    extractWholeResumeSkills,
    extractEligibleSkillsBlock,
    extractVerbatimDesignation,
    cleanAndValidateRoleOrTechnologies,
    extractCurrentLocation,
)

# Strict Skills Extraction Engine
from .skillsExtractionEngine import (
    extractSkillsWithEngine,
    extractSkillsWithEngineSync,
    detectSkillSection,
    validateSkillsAgainstSection,
    expandCompoundSkillPhrases,
    SkillsSectionLayout,
    SkillEvidence,
    SkillsExtractionDiagnostics,
    SkillsEngineOptions,
    SkillsExtractionResult,
)

# Multi-Format Text Extraction
from .extractResumeText import (
    extractPlainTextFromResumeBuffer,
    normalizeResumeText,
)

# Gemini AI Services
from .ai.gemini import (
    parseResumeFromPdf,
    parseResumeFromText,
    extractSkillsWithGemini,
    chatWithContext,
)

# Validation and Sanitization Utilities
from .candidateNameValidation import (
    isBadCandidateDisplayName,
    trimJobTitleSuffixFromDisplayName,
)

from .resumeFieldSanitize import (
    compactHighestQualification,
    cleanAcademicSpecialization,
    isCertificationOrNonAcademic,
    looksLikeJobRolePhrase,
    sanitizeDisplayText,
)

from .coreTechKeywords import (
    CORE_TECH_KEYWORDS,
)

# Candidate Storage Adapters (Optional Persistence)
from .adapters.candidateStoreAdapter import (
    CandidateStoreAdapter,
    InMemoryCandidateStore,
)

__all__ = [
    # Types
    "ParsedCandidateResume",
    "CoreParsedFields",
    "BulkParseItemResult",
    "ExtractResumeTextResult",
    "MetaforgeParsed",
    "ResumeParserOptions",
    "ChatMessage",
    "ChatWithContextOptions",
    # Core Orchestration
    "parseResumeBuffer",
    "parseResumeBuffersBulk",
    "parseResumeBufferWithMetaforge",
    "parseResumeBufferLegacy",
    "isMetaforgeParserAvailable",
    "getAiParsingSuspendedReason",
    "applyEvidenceLock",
    # Local Deterministic Parser
    "parseCoreFieldsFromResumeText",
    "extractTotalExperienceInfo",
    "extractWholeResumeSkills",
    "extractEligibleSkillsBlock",
    "extractVerbatimDesignation",
    "cleanAndValidateRoleOrTechnologies",
    "extractCurrentLocation",
    # Strict Skills Extraction Engine
    "extractSkillsWithEngine",
    "extractSkillsWithEngineSync",
    "detectSkillSection",
    "validateSkillsAgainstSection",
    "expandCompoundSkillPhrases",
    "SkillsSectionLayout",
    "SkillEvidence",
    "SkillsExtractionDiagnostics",
    "SkillsEngineOptions",
    "SkillsExtractionResult",
    # Text Extraction
    "extractPlainTextFromResumeBuffer",
    "normalizeResumeText",
    # Gemini AI Services
    "parseResumeFromPdf",
    "parseResumeFromText",
    "extractSkillsWithGemini",
    "chatWithContext",
    # Validation and Sanitization
    "isBadCandidateDisplayName",
    "trimJobTitleSuffixFromDisplayName",
    "compactHighestQualification",
    "cleanAcademicSpecialization",
    "isCertificationOrNonAcademic",
    "looksLikeJobRolePhrase",
    "sanitizeDisplayText",
    "CORE_TECH_KEYWORDS",
    # Candidate Store
    "CandidateStoreAdapter",
    "InMemoryCandidateStore",
]
