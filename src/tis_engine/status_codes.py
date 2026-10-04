from __future__ import annotations

from enum import IntEnum


class StatusCode(IntEnum):
    SUCCESS = 0
    INVALID_CONFIG = 2
    MISSING_OR_INVALID_INPUT = 3
    EXTERNAL_TOOL_NOT_FOUND = 4
    DICOM_CONVERSION_FAILED = 5
    HEAD_MODEL_FAILED = 6
    SOLVER_FAILED = 7
    TIMEOUT = 8
    INTERNAL_ERROR = 9


STATUS_MESSAGES: dict[StatusCode, str] = {
    StatusCode.SUCCESS: "success",
    StatusCode.INVALID_CONFIG: "invalid config",
    StatusCode.MISSING_OR_INVALID_INPUT: "missing or invalid input",
    StatusCode.EXTERNAL_TOOL_NOT_FOUND: "external tool not found",
    StatusCode.DICOM_CONVERSION_FAILED: "DICOM conversion failed",
    StatusCode.HEAD_MODEL_FAILED: "head model failed",
    StatusCode.SOLVER_FAILED: "solver failed",
    StatusCode.TIMEOUT: "timeout",
    StatusCode.INTERNAL_ERROR: "internal error",
}


def status_message(code: StatusCode | int) -> str:
    return STATUS_MESSAGES.get(StatusCode(code), "unknown status")

