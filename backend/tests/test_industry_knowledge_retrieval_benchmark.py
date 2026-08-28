from __future__ import annotations

import json

from app.services import industry_knowledge_retrieval_benchmark as benchmark


def _dataset(path) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmark_id": "fixture",
                "version": "fixture-v1",
                "cases": [
                    {
                        "case_id": "case-a",
                        "query": "政务数据开放",
                        "industries": ["government_public"],
                        "document_types": ["policy_standard"],
                        "relevant_document_ids": ["doc-a"],
                        "relevance_by_document_id": {"doc-a": 3},
                        "expected_citation_terms": ["政务", "开放"],
                    },
                    {
                        "case_id": "case-b",
                        "query": "智能工厂质量",
                        "industries": ["manufacturing_supply_chain"],
                        "document_types": ["solution"],
                        "relevant_document_ids": ["doc-b"],
                        "relevance_by_document_id": {"doc-b": 3},
                        "expected_citation_terms": ["智能工厂", "质量"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _successful_hit(document_id: str, query: str) -> dict[str, object]:
    return {
        "document_id": document_id,
        "title": f"{query} 资料",
        "snippet": query,
        "locator": "第 1 页",
    }


def _configure_ready_knowledge_base(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(benchmark, "resolve_library_dir", lambda _value=None: tmp_path)
    monkeypatch.setattr(benchmark, "knowledge_base_public_status", lambda _value: {"status": "ready", "warnings": []})
    monkeypatch.setattr(
        benchmark,
        "load_knowledge_base_manifest",
        lambda _value: {"generation_id": "fixture-generation", "generated_at": "2026-08-12T00:00:00+00:00"},
    )


def _bind_review_to_fixed_result(tmp_path, dataset_path, review_path) -> str:
    preview = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "preview.json",
        review_path=tmp_path / "missing-review.json",
        persist=False,
    )
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["benchmark_digest"] = preview["benchmark_digest"]
    review_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(preview["benchmark_digest"])


def test_benchmark_uses_fixed_cases_and_holds_without_completed_human_review(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    monkeypatch.setattr(
        benchmark,
        "resolve_library_dir",
        lambda _value=None: tmp_path,
    )
    monkeypatch.setattr(
        benchmark,
        "knowledge_base_public_status",
        lambda _value: {"status": "ready", "warnings": []},
    )
    monkeypatch.setattr(
        benchmark,
        "load_knowledge_base_manifest",
        lambda _value: {"generation_id": "fixture-generation", "generated_at": "2026-08-12T00:00:00+00:00"},
    )

    def fake_search(_library_dir, *, query, strategy, **_kwargs):
        document_id = "doc-a" if "政务" in query else "doc-b"
        return {
            "hits": [_successful_hit(document_id, query)],
            "rerank_applied": strategy != "prefilter_weighted_rerank" or False,
            "rerank_backend": "unavailable" if strategy == "prefilter_weighted_rerank" else "disabled",
        }

    monkeypatch.setattr(benchmark, "hybrid_search_industry_knowledge", fake_search)
    result = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "result.json",
        review_path=tmp_path / "review.json",
        review_sample_dir=tmp_path / "review-samples",
        persist=True,
    )

    assert result["case_count"] == 2
    assert result["arms"][0]["metrics"][0]["value"] == 1.0
    assert result["promotion"]["decision"] == "hold"
    assert result["promotion"]["completed_human_review_case_count"] == 0
    assert (tmp_path / "result.json").is_file()
    template = json.loads((tmp_path / "review.json").read_text(encoding="utf-8"))
    assert len(template["entries"]) == 6
    assert template["review_status"] == "pending"
    assert template["entries"][0]["review_sample_path"]
    assert not template["entries"][0]["review_sample_path"].startswith(str(tmp_path))
    sample_path = tmp_path / "review-samples" / "baseline_hybrid" / "case-a.md"
    assert sample_path.is_file()
    assert "检索排序固定证据审阅样本" in sample_path.read_text(encoding="utf-8")
    assert result["artifact_path"] == "result.json"
    assert result["review_template_path"] == "review.json"


def test_benchmark_warms_every_strategy_before_measuring(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    monkeypatch.setattr(benchmark, "resolve_library_dir", lambda _value=None: tmp_path)
    monkeypatch.setattr(benchmark, "knowledge_base_public_status", lambda _value: {"status": "ready", "warnings": []})
    monkeypatch.setattr(
        benchmark,
        "load_knowledge_base_manifest",
        lambda _value: {"generation_id": "fixture-generation", "generated_at": "2026-08-12T00:00:00+00:00"},
    )
    calls: list[str] = []

    def fake_search(_library_dir, *, query, strategy, **_kwargs):
        calls.append(strategy)
        return {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
        }

    monkeypatch.setattr(benchmark, "hybrid_search_industry_knowledge", fake_search)
    benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "result.json",
        review_path=tmp_path / "review.json",
        persist=False,
    )

    assert calls[: len(benchmark.STRATEGY_KEYS)] == list(benchmark.STRATEGY_KEYS)


def test_completed_human_review_and_real_rerank_can_promote_candidate(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "dataset_sha256": benchmark._dataset_digest(dataset_path),
                "review_status": "complete",
                "review_protocol_version": benchmark.REVIEW_PROTOCOL_VERSION,
                "reviewer_name": "Independent Reviewer",
                "reviewer_role": "domain reviewer",
                "reviewed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "已独立审阅全部完整报告。",
                "independence_attestation": "本人未参与候选策略实现或评分生成。",
                "conflict_disclosure": "无需要披露的利益冲突。",
                "entries": [
                    {
                        "case_id": case_id,
                        "strategy": strategy,
                        "report_artifact_path": f"reports/{case_id}-{strategy}.md",
                        "human_review_score": score,
                    }
                    for case_id in ("case-a", "case-b")
                    for strategy, score in (
                        ("baseline_hybrid", 4.0),
                        ("prefilter_weighted_hybrid", 4.2),
                        ("prefilter_weighted_rerank", 4.5),
                    )
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_ready_knowledge_base(tmp_path, monkeypatch)

    def fake_search(_library_dir, *, query, strategy, **_kwargs):
        document_id = "doc-a" if "政务" in query else "doc-b"
        snippet = query if strategy != "baseline_hybrid" else query.split(" ")[0]
        return {
            "hits": [_successful_hit(document_id, snippet)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        }

    monkeypatch.setattr(benchmark, "hybrid_search_industry_knowledge", fake_search)
    _bind_review_to_fixed_result(tmp_path, dataset_path, review_path)
    result = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "result.json",
        review_path=review_path,
        persist=False,
    )

    assert result["promotion"]["decision"] == "promote"
    assert result["promotion"]["candidate_strategy"] == "prefilter_weighted_rerank"
    assert result["promotion"]["completed_human_review_case_count"] == 6


def test_completed_scores_without_report_artifacts_cannot_be_promoted(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "dataset_sha256": benchmark._dataset_digest(dataset_path),
                "review_status": "complete",
                "review_protocol_version": benchmark.REVIEW_PROTOCOL_VERSION,
                "reviewer_name": "Independent Reviewer",
                "reviewer_role": "domain reviewer",
                "reviewed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "已独立审阅全部完整报告。",
                "independence_attestation": "本人未参与候选策略实现或评分生成。",
                "conflict_disclosure": "无需要披露的利益冲突。",
                "entries": [
                    {"case_id": case_id, "strategy": strategy, "human_review_score": 5.0}
                    for case_id in ("case-a", "case-b")
                    for strategy in benchmark.STRATEGY_KEYS
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_ready_knowledge_base(tmp_path, monkeypatch)
    monkeypatch.setattr(
        benchmark,
        "hybrid_search_industry_knowledge",
        lambda _library_dir, *, query, strategy, **_kwargs: {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        },
    )
    _bind_review_to_fixed_result(tmp_path, dataset_path, review_path)

    result = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "result.json",
        review_path=review_path,
        persist=False,
    )

    assert result["promotion"]["decision"] == "hold"
    assert result["promotion"]["completed_human_review_case_count"] == 0
    assert any("没有关联完整报告工件" in warning for warning in result["warnings"])


def test_completed_review_without_independence_proof_cannot_be_promoted(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "dataset_sha256": benchmark._dataset_digest(dataset_path),
                "review_status": "complete",
                "review_protocol_version": benchmark.REVIEW_PROTOCOL_VERSION,
                "reviewer_name": "Independent Reviewer",
                "reviewer_role": "domain reviewer",
                "reviewed_at": "2026-08-13T00:00:00+00:00",
                "attestation": "已完成复核。",
                "conflict_disclosure": "无需要披露的利益冲突。",
                "entries": [
                    {
                        "case_id": case_id,
                        "strategy": strategy,
                        "report_artifact_path": f"reports/{case_id}-{strategy}.md",
                        "human_review_score": 5.0,
                    }
                    for case_id in ("case-a", "case-b")
                    for strategy in benchmark.STRATEGY_KEYS
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _configure_ready_knowledge_base(tmp_path, monkeypatch)
    monkeypatch.setattr(
        benchmark,
        "hybrid_search_industry_knowledge",
        lambda _library_dir, *, query, strategy, **_kwargs: {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        },
    )
    _bind_review_to_fixed_result(tmp_path, dataset_path, review_path)

    result = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=tmp_path / "result.json",
        review_path=review_path,
        persist=False,
    )

    assert result["promotion"]["decision"] == "hold"
    assert any("独立性声明" in warning for warning in result["warnings"])


def test_latest_persisted_benchmark_overlays_only_a_review_bound_to_its_digest(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    artifact_path = tmp_path / "result.json"
    review_path = tmp_path / "review.json"
    _configure_ready_knowledge_base(tmp_path, monkeypatch)
    calls: list[str] = []

    def fake_search(_library_dir, *, query, strategy, **_kwargs):
        calls.append(strategy)
        return {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        }

    monkeypatch.setattr(benchmark, "hybrid_search_industry_knowledge", fake_search)
    persisted = benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
        persist=True,
    )
    template = json.loads(review_path.read_text(encoding="utf-8"))
    template.update(
        {
            "review_status": "complete",
            "reviewer_name": "Independent Reviewer",
            "reviewer_role": "domain reviewer",
            "reviewed_at": "2026-08-13T00:00:00+00:00",
            "attestation": "已独立审阅全部完整报告。",
            "independence_attestation": "本人未参与候选策略实现或评分生成。",
            "conflict_disclosure": "无需要披露的利益冲突。",
        }
    )
    for entry in template["entries"]:
        entry["report_artifact_path"] = f"reports/{entry['case_id']}-{entry['strategy']}.md"
        entry["human_review_score"] = 4.5 if entry["strategy"] == "prefilter_weighted_rerank" else 4.0
    review_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

    before_overlay_calls = len(calls)
    latest = benchmark.load_latest_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
    )

    assert latest["benchmark_digest"] == persisted["benchmark_digest"]
    assert latest["promotion"]["completed_human_review_case_count"] == 6
    assert len(calls) == before_overlay_calls
    assert not any("尚未生成或完成报告人工评分" in warning for warning in latest["warnings"])


def test_latest_persisted_benchmark_rejects_review_with_a_different_digest(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    artifact_path = tmp_path / "result.json"
    review_path = tmp_path / "review.json"
    _configure_ready_knowledge_base(tmp_path, monkeypatch)

    monkeypatch.setattr(
        benchmark,
        "hybrid_search_industry_knowledge",
        lambda _library_dir, *, query, strategy, **_kwargs: {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        },
    )
    benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
        persist=True,
    )
    template = json.loads(review_path.read_text(encoding="utf-8"))
    template.update(
        {
            "benchmark_digest": "different-fixed-retrieval-result",
            "review_status": "complete",
            "reviewer_name": "Independent Reviewer",
            "reviewer_role": "domain reviewer",
            "reviewed_at": "2026-08-13T00:00:00+00:00",
            "attestation": "已独立审阅全部完整报告。",
            "independence_attestation": "本人未参与候选策略实现或评分生成。",
            "conflict_disclosure": "无需要披露的利益冲突。",
        }
    )
    for entry in template["entries"]:
        entry["report_artifact_path"] = f"reports/{entry['case_id']}-{entry['strategy']}.md"
        entry["human_review_score"] = 5.0
    review_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")

    latest = benchmark.load_latest_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
    )

    assert latest["promotion"]["decision"] == "hold"
    assert any("未绑定当前固定检索结果摘要" in warning for warning in latest["warnings"])


def test_latest_benchmark_refuses_a_persisted_result_with_a_tampered_digest(tmp_path, monkeypatch) -> None:
    dataset_path = tmp_path / "dataset.json"
    _dataset(dataset_path)
    artifact_path = tmp_path / "result.json"
    review_path = tmp_path / "review.json"
    _configure_ready_knowledge_base(tmp_path, monkeypatch)
    calls: list[str] = []

    def fake_search(_library_dir, *, query, strategy, **_kwargs):
        calls.append(strategy)
        return {
            "hits": [_successful_hit("doc-a" if "政务" in query else "doc-b", query)],
            "rerank_applied": strategy == "prefilter_weighted_rerank",
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": "BAAI/bge-reranker-v2-m3" if strategy == "prefilter_weighted_rerank" else "",
        }

    monkeypatch.setattr(benchmark, "hybrid_search_industry_knowledge", fake_search)
    benchmark.run_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
        persist=True,
    )
    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    persisted["benchmark_digest"] = "tampered"
    artifact_path.write_text(json.dumps(persisted), encoding="utf-8")
    calls_before_refresh = len(calls)

    latest = benchmark.load_latest_industry_knowledge_retrieval_benchmark(
        dataset_path=dataset_path,
        artifact_path=artifact_path,
        review_path=review_path,
    )

    assert latest["benchmark_digest"] != "tampered"
    assert len(calls) > calls_before_refresh
    assert any("未落盘预览" in warning for warning in latest["warnings"])


def test_missing_cross_encoder_model_name_cannot_promote_candidate() -> None:
    def arm(strategy: str, *, human_score: float, rerank_model: str = "") -> dict[str, object]:
        return {
            "strategy": strategy,
            "role": "baseline" if strategy == "baseline_hybrid" else "candidate",
            "rerank_applied_case_count": 1 if strategy == "prefilter_weighted_rerank" else 0,
            "rerank_backend": "sentence-transformers" if strategy == "prefilter_weighted_rerank" else "disabled",
            "rerank_model": rerank_model,
            "metrics": [
                {"key": "recall_at_10", "value": 1.0},
                {"key": "ndcg_at_10", "value": 1.0},
                {"key": "citation_hit_rate", "value": 1.0},
                {"key": "latency_ms", "value": 10.0},
                {"key": "human_review_score", "value": human_score},
            ],
            "cases": [{"human_review_score": human_score}],
        }

    decision = benchmark._promotion_decision(
        [
            arm("baseline_hybrid", human_score=4.0),
            arm("prefilter_weighted_rerank", human_score=4.5),
        ],
        case_count=1,
    )

    assert decision["decision"] == "hold"
    assert any("模型名" in reason for reason in decision["reasons"])


def test_delivery_review_artifacts_register_against_pending_template(tmp_path) -> None:
    review_path = tmp_path / "review.json"
    artifact_path = tmp_path / "benchmark.json"
    artifact_path.write_text("{}", encoding="utf-8")
    review_path.write_text(
        json.dumps(
            {
                "review_status": "pending",
                "entries": [
                    {"case_id": "case-a", "strategy": strategy, "report_artifact_path": ""}
                    for strategy in benchmark.STRATEGY_KEYS
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    warnings = benchmark.register_industry_knowledge_delivery_review_artifacts(
        case_id="case-a",
        artifact_paths={strategy: f"reviews/{strategy}.md" for strategy in benchmark.STRATEGY_KEYS},
        review_path=review_path,
        benchmark_artifact_path=artifact_path,
    )

    saved = json.loads(review_path.read_text(encoding="utf-8"))
    assert not warnings
    assert {entry["report_artifact_path"] for entry in saved["entries"]} == {
        f"reviews/{strategy}.md" for strategy in benchmark.STRATEGY_KEYS
    }
