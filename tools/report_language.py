from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Iterable


REPORT_LANGUAGE_ENV = "SPECGUARD_CONVERSATION_LANGUAGE"
SUPPORTED_REPORT_LANGUAGES = frozenset({"en", "ko"})

_KOREAN_ISSUE_TITLES = {
    "Account verification contract is unsafe": "계정 검증 계약이 안전하지 않음",
    "Architecture is still a placeholder": "아키텍처가 아직 placeholder 상태임",
    "Audit evidence is mutable": "감사 근거를 변경할 수 있음",
    "Background job retry contract is unsafe": "백그라운드 작업 재시도 계약이 안전하지 않음",
    "Booking conflict contract is unsafe": "예약 충돌 계약이 안전하지 않음",
    "Brute-force protection is missing": "무차별 대입 공격 방어가 누락됨",
    "Cache invalidation boundary is unsafe": "캐시 무효화 경계가 안전하지 않음",
    "Coupon redemption contract is unsafe": "쿠폰 사용 계약이 안전하지 않음",
    "Data flow is too generic": "데이터 흐름이 지나치게 일반적임",
    "Delete semantics are unsafe": "삭제 정책이 안전하지 않음",
    "Deleted task terminal behavior is unsafe": "삭제된 작업의 종료 상태 동작이 안전하지 않음",
    "Device trust lifecycle is unsafe": "신뢰 기기 수명 주기가 안전하지 않음",
    "Document share ownership boundary is unsafe": "문서 공유 소유권 경계가 안전하지 않음",
    "External dependency failure path is absent": "외부 의존성 실패 경로가 누락됨",
    "Failure handling is not actionable": "실패 처리 방식이 실행 가능할 만큼 구체적이지 않음",
    "Feature flag targeting boundary is unsafe": "기능 플래그 대상 지정 경계가 안전하지 않음",
    "File upload validation is missing": "파일 업로드 검증이 누락됨",
    "Inventory reservation contract is unsafe": "재고 예약 계약이 안전하지 않음",
    "Ledger immutability contract is unsafe": "원장 불변성 계약이 안전하지 않음",
    "No LLM readiness findings returned": "상세 검토에서 준비 상태 항목을 반환하지 않음",
    "No obvious readiness triggers found": "명확한 준비 상태 위험 신호가 발견되지 않음",
    "Notification safety contract is unsafe": "알림 안전 계약이 안전하지 않음",
    "OAuth consent scope boundary is unsafe": "OAuth 동의 범위 경계가 안전하지 않음",
    "Order state transition is unsafe": "주문 상태 전이가 안전하지 않음",
    "Payment idempotency contract is ambiguous": "결제 멱등성 계약이 모호함",
    "Privacy deletion contract is incomplete": "개인정보 삭제 계약이 불완전함",
    "Server-side authorization is missing": "서버 측 인가가 누락됨",
    "Server-side rate limit is missing": "서버 측 요청 제한이 누락됨",
    "Spec package structure is incomplete": "스펙 패키지 구조가 불완전함",
    "Spec required sections are incomplete": "스펙 필수 섹션이 불완전함",
    "State transitions are underspecified": "상태 전이 정의가 부족함",
    "Subscription billing transition is ambiguous": "구독 청구 전이가 모호함",
    "Support ticket boundary is unsafe": "지원 티켓 경계가 안전하지 않음",
    "Task error contract is non-actionable": "작업 오류 계약이 실행 가능할 만큼 구체적이지 않음",
    "Task idempotency contract is ambiguous": "작업 멱등성 계약이 모호함",
    "Task ownership boundary is unclear": "작업 소유권 경계가 불명확함",
    "Task service acceptance evidence is too vague": "작업 서비스 인수 근거가 지나치게 모호함",
    "Task title validation is unsafe": "작업 제목 검증이 안전하지 않음",
    "Tenant boundary is unsafe": "테넌트 경계가 안전하지 않음",
    "Tenant cache boundary is unsafe": "테넌트 캐시 경계가 안전하지 않음",
    "Todo ownership boundary is unclear": "할 일 소유권 경계가 불명확함",
    "Token lifecycle is missing": "토큰 수명 주기가 누락됨",
    "Webhook side-effect contract is ambiguous": "웹훅 부작용 계약이 모호함",
    "Webhook signature verification is missing": "웹훅 서명 검증이 누락됨",
    "Workspace invite recipient binding is unsafe": "워크스페이스 초대 수신자 바인딩이 안전하지 않음",
}

_KOREAN_TOKEN = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]+")
_ENGLISH_TOKEN = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class ReportLanguageResolution:
    code: str
    source: str
    fallback_used: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "source": self.source,
            "fallback_used": self.fallback_used,
        }


def resolve_report_language(
    authored_texts: Iterable[str],
    *,
    conversation_language: str | None = None,
) -> ReportLanguageResolution:
    hint = conversation_language
    if hint is None:
        hint = os.getenv(REPORT_LANGUAGE_ENV)

    conversation_code = detect_supported_language(hint or "", allow_language_code=True)
    if conversation_code:
        return ReportLanguageResolution(conversation_code, "conversation")

    spec_code = detect_supported_language("\n".join(authored_texts))
    if spec_code:
        return ReportLanguageResolution(spec_code, "spec")

    return ReportLanguageResolution("en", "fallback", fallback_used=True)


def detect_supported_language(text: str, *, allow_language_code: bool = False) -> str | None:
    normalized = text.strip().lower()
    if allow_language_code:
        aliases = {
            "en": "en",
            "eng": "en",
            "english": "en",
            "ko": "ko",
            "kor": "ko",
            "korean": "ko",
            "한국어": "ko",
        }
        if normalized in aliases:
            return aliases[normalized]

    korean_count = len(_KOREAN_TOKEN.findall(text))
    english_count = len(_ENGLISH_TOKEN.findall(text))
    total = korean_count + english_count
    if total == 0:
        return None
    if korean_count and not english_count:
        return "ko"
    if english_count and not korean_count:
        return "en"
    if korean_count / total >= 0.6:
        return "ko"
    if english_count / total >= 0.6:
        return "en"
    return None


def report_language_from_payload(payload: dict[str, Any] | None) -> ReportLanguageResolution:
    if isinstance(payload, dict):
        raw = payload.get("report_language")
        if isinstance(raw, dict):
            code = str(raw.get("code") or "").strip().lower()
            source = str(raw.get("source") or "").strip().lower()
            if code in SUPPORTED_REPORT_LANGUAGES and source in {"conversation", "spec", "fallback"}:
                return ReportLanguageResolution(
                    code=code,
                    source=source,
                    fallback_used=bool(raw.get("fallback_used", source == "fallback")),
                )
    return ReportLanguageResolution("en", "fallback", fallback_used=True)


def localized_issue_title(title: str, report_language: str) -> str:
    if report_language == "ko":
        return _KOREAN_ISSUE_TITLES.get(title, title)
    return title
