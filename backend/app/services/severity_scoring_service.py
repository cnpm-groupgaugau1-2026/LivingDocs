from __future__ import annotations

from typing import Dict, List, Tuple

from app.schemas.drift import DriftItem, DriftSeverity


class SeverityScoringEngine:
    """
    FE04 - 5.2: Severity Scoring Engine
    Chấm điểm rủi ro (0-100) và phân cấp mức độ nghiêm trọng:
    Low (0-34) | Medium (35-59) | High (60-79) | Critical (80-100)
    """

    _BASE_IMPACT_BY_SUBTYPE: Dict[str, Tuple[int, str]] = {
        "side_effect_contradiction": (45, "Mâu thuẫn hành vi ghi/xóa dữ liệu (side-effect)"),
        "breaking_param_change": (42, "Thay đổi tham số bắt buộc làm gãy lời gọi hàm"),
        "missing_or_renamed_symbol": (36, "Ký hiệu đã bị xóa hoặc đổi tên khỏi mã nguồn"),
        "param_order_mismatch": (35, "Đảo thứ tự tham số gây truyền sai giá trị"),
        "return_type_mismatch": (32, "Sai kiểu dữ liệu trả về"),
        "return_behavior_mismatch": (32, "Mâu thuẫn giá trị trả về thực tế (trả về None)"),
        "param_type_mismatch": (28, "Sai kiểu dữ liệu tham số đầu vào"),
        "undocumented_exception": (26, "Ném ngoại lệ chưa được mô tả trong tài liệu"),
        "broken_file_reference": (22, "Đường dẫn tệp tham chiếu không tồn tại"),
        "default_value_mismatch": (18, "Sai lệch giá trị mặc định của tham số"),
        "optional_param_added": (8, "Bổ sung tham số tùy chọn mới"),
        "llm_behavioral_contradiction": (34, "Mâu thuẫn ngữ nghĩa hành vi phát hiện qua LLM"),
    }

    _SENSITIVE_KEYWORDS = (
        "payment",
        "billing",
        "auth",
        "token",
        "security",
        "delete",
        "cleanup",
        "transaction",
        "password",
        "secret",
        "admin",
        "permission",
    )

    def score_drifts(
        self,
        drifts: List[DriftItem],
        public_symbols: set[str] | None = None,
        mutating_symbols: set[str] | None = None,
    ) -> Tuple[List[DriftItem], Dict[str, int], int, DriftSeverity]:
        public_set = public_symbols or set()
        mutating_set = mutating_symbols or set()

        scored_items: List[DriftItem] = []
        counts: Dict[str, int] = {
            DriftSeverity.CRITICAL.value: 0,
            DriftSeverity.HIGH.value: 0,
            DriftSeverity.MEDIUM.value: 0,
            DriftSeverity.LOW.value: 0,
        }

        for item in drifts:
            factors: List[str] = []

            # 1. Điểm tác động cơ sở theo loại sai lệch (8 - 45đ)
            base_pts, base_reason = self._BASE_IMPACT_BY_SUBTYPE.get(
                item.sub_type, (20, "Sai lệch cấu trúc tài liệu và mã nguồn")
            )
            score = base_pts
            factors.append(f"+{base_pts}đ: {base_reason}")

            # 2. Điểm rủi ro nghiệp vụ nhạy cảm / tác động dữ liệu (+20đ)
            context_text = f"{item.file_path or ''} {item.symbol_name}".lower()
            is_sensitive_domain = any(kw in context_text for kw in self._SENSITIVE_KEYWORDS)
            has_mutating_behavior = (
                item.symbol_name in mutating_set
                or item.sub_type == "side_effect_contradiction"
            )
            if is_sensitive_domain or has_mutating_behavior:
                score += 20
                factors.append("+20đ: Thuộc luồng nghiệp vụ nhạy cảm hoặc có thao tác ghi/xóa dữ liệu")

            # 3. Điểm phạm vi ảnh hưởng API công khai (+10đ)
            short_name = item.symbol_name.split(".")[-1]
            is_public = (
                item.symbol_name in public_set
                or short_name in public_set
                or not short_name.startswith("_")
            )
            if is_public:
                score += 10
                factors.append("+10đ: Thành phần công khai (Public API / Tài liệu hướng dẫn ngoài)")

            # 4. Trọng số độ tin cậy phát hiện (0 - 15đ)
            conf_pts = round(item.confidence * 15)
            score += conf_pts
            factors.append(f"+{conf_pts}đ: Độ tin cậy phát hiện {round(item.confidence * 100)}%")

            final_score = max(0, min(100, score))
            severity_level = self._map_score_to_severity(final_score)

            counts[severity_level.value] += 1
            scored_items.append(
                item.model_copy(
                    update={
                        "severity": severity_level,
                        "severity_score": final_score,
                        "severity_factors": factors,
                    }
                )
            )

        # Sắp xếp giảm dần theo điểm rủi ro để ưu tiên lỗi nghiêm trọng nhất lên đầu
        scored_items.sort(key=lambda d: (-d.severity_score, d.doc_line_range[0] if d.doc_line_range else 9999))

        overall_score, overall_level = self._compute_overall_risk(scored_items)
        return scored_items, counts, overall_score, overall_level

    def _map_score_to_severity(self, score: int) -> DriftSeverity:
        if score >= 80:
            return DriftSeverity.CRITICAL
        if score >= 60:
            return DriftSeverity.HIGH
        if score >= 35:
            return DriftSeverity.MEDIUM
        return DriftSeverity.LOW

    def _compute_overall_risk(self, items: List[DriftItem]) -> Tuple[int, DriftSeverity]:
        if not items:
            return 0, DriftSeverity.LOW
        top_scores = [i.severity_score for i in items[:3]]
        max_score = top_scores[0]
        avg_top = sum(top_scores) / len(top_scores)
        overall = round(max_score * 0.7 + avg_top * 0.3)
        overall = max(0, min(100, overall))
        return overall, self._map_score_to_severity(overall)