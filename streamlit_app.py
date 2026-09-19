"""Streamlit interface for the course job advertisement extractor.

Pipeline: GBERT proposes candidate entity spans locally, the LLM verifies and
structures them into the final result. Start with:
    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import html
import json

import streamlit as st

from ie_course.examples import EXAMPLES
from ie_course.extractor import extract_job_ad, get_config_status, match_cv_to_job
from ie_course.file_extract import extract_text_from_upload
from ie_course.strict_json import ALLOWED_TYPES

LABELS = {
    "JOB_TITLE": "Job Title",
    "HARD_SKILL": "Hard Skills",
    "SOFT_SKILL": "Soft Skills",
    "EXPERIENCE": "Experience",
    "EDUCATION": "Education",
    "LANGUAGE": "Languages",
    "WORK_MODE": "Work Model",
}
ICONS = {
    "JOB_TITLE": "💼",
    "HARD_SKILL": "🛠️",
    "SOFT_SKILL": "🤝",
    "EXPERIENCE": "📈",
    "EDUCATION": "🎓",
    "LANGUAGE": "🗣️",
    "WORK_MODE": "🏢",
}
COLORS = {
    "JOB_TITLE": ("#dbeafe", "#1e3a8a"),
    "HARD_SKILL": ("#dcfce7", "#14532d"),
    "SOFT_SKILL": ("#fef3c7", "#78350f"),
    "EXPERIENCE": ("#fce7f3", "#831843"),
    "EDUCATION": ("#ede9fe", "#4c1d95"),
    "LANGUAGE": ("#cffafe", "#164e63"),
    "WORK_MODE": ("#ffedd5", "#7c2d12"),
}


def chips(values: list[str], entity_type: str) -> str:
    bg, fg = COLORS[entity_type]
    if not values:
        return '<span style="color:#94a3b8;font-size:0.9em">No value detected</span>'
    return "".join(
        f'<span style="background:{bg};color:{fg};padding:4px 12px;border-radius:999px;'
        f'margin:0 6px 6px 0;display:inline-block;font-size:0.92em">{html.escape(v)}</span>'
        for v in values
    )


def highlighted_text(text: str, spans: list[dict], visible: set[str]) -> str:
    """Render only verified, non-overlapping offsets; escape all model and user text."""
    parts: list[str] = []
    cursor = 0
    for span in sorted(spans, key=lambda item: item["start"]):
        start, end, entity_type = span["start"], span["end"], span["type"]
        if entity_type not in visible or not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < cursor or end > len(text) or start >= end or text[start:end] != span["text"]:
            continue
        bg, _fg = COLORS[entity_type]
        parts.append(html.escape(text[cursor:start]))
        parts.append(
            f'<mark title="{html.escape(LABELS[entity_type])}" '
            f'style="background:{bg};padding:2px;border-radius:3px">'
            f"{html.escape(text[start:end])}</mark>"
        )
        cursor = end
    parts.append(html.escape(text[cursor:]))
    return (
        '<div style="white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere">'
        + "".join(parts)
        + "</div>"
    )


def use_example(example_text: str) -> None:
    st.session_state.ad_text = example_text
    st.session_state.result = None
    st.session_state.result_text = None
    st.session_state.upload_key += 1
    st.session_state.upload_error = None
    st.session_state.upload_info = None


def use_upload() -> None:
    uploaded = st.session_state.get(f"upload_{st.session_state.upload_key}")
    if uploaded is None:
        st.session_state.upload_info = None
        st.session_state.upload_error = None
        return
    text, error, meta = extract_text_from_upload(uploaded.name, uploaded.getvalue())
    st.session_state.upload_info = meta
    st.session_state.upload_error = error
    if text is not None:
        st.session_state.ad_text = text
        st.session_state.result = None
        st.session_state.result_text = None


def main() -> None:
    st.set_page_config(page_title="Analyze Job Ads", page_icon="🔎", layout="wide")
    for key, initial in (
        ("ad_text", ""),
        ("result", None),
        ("result_text", None),
        ("upload_key", 0),
        ("upload_info", None),
        ("upload_error", None),
        ("match_result", None),
        ("match_error", None),
    ):
        if key not in st.session_state:
            st.session_state[key] = initial

    st.title("Information Extraction from Job Ads")
    st.write(
        "Paste or upload a job ad. A local GBERT model proposes entities, "
        "and a language model verifies them and returns the structured result."
    )

    config = get_config_status()
    status_cols = st.columns(2)
    with status_cols[0]:
        if config["configured"]:
            provider_name = "AcademicCloud Chat AI" if config["provider"] == "academiccloud" else "OpenAI"
            st.caption(f"✅ LLM: {provider_name} · Model: {config['model']}")
        else:
            st.warning(
                "The API is not configured. Set up `.env` from `.env.example`: "
                + ", ".join(config["missing"])
            )
    with status_cols[1]:
        if config["gbert_available"]:
            st.caption("✅ Local GBERT model loaded")
        else:
            st.caption("⚠️ No trained GBERT model found - result is based only on the LLM")

    st.subheader("Choose an Example")
    columns = st.columns(len(EXAMPLES))
    for column, example in zip(columns, EXAMPLES):
        with column:
            st.button(
                example["label"],
                key=f"example_{example['id']}",
                help=example["short"],
                use_container_width=True,
                on_click=use_example,
                args=(example["text"],),
            )

    st.file_uploader(
        "Upload a file (TXT, PDF, or DOCX; maximum 8 MB)",
        type=["txt", "pdf", "docx"],
        key=f"upload_{st.session_state.upload_key}",
        on_change=use_upload,
    )
    if st.session_state.upload_error:
        st.error(st.session_state.upload_error)
    elif st.session_state.upload_info:
        meta = st.session_state.upload_info
        st.caption(f"Loaded: {meta['filename']} ({meta['size_human']})")

    st.text_area(
        "Job Ad",
        key="ad_text",
        height=280,
        placeholder="Paste text here or choose an example",
    )

    cv_file = st.file_uploader(
        "Upload a CV (optional - checks whether the job is a good fit)",
        type=["txt", "pdf", "docx"],
        key="cv_upload",
    )

    action, clear = st.columns([3, 1])
    analyze = action.button("Analyze Job Ad", type="primary", use_container_width=True)
    clear.button("Clear", use_container_width=True, on_click=use_example, args=("",))

    if analyze:
        with st.spinner("GBERT is proposing entities, and the LLM is structuring the result..."):
            result, error, _diagnostics = extract_job_ad(st.session_state.ad_text)
        st.session_state.result = result
        st.session_state.result_text = st.session_state.ad_text if result is not None else None
        if error:
            st.error(error)

        st.session_state.match_result = None
        st.session_state.match_error = None
        if result is not None and cv_file is not None:
            cv_text, cv_error, _meta = extract_text_from_upload(cv_file.name, cv_file.getvalue())
            if cv_error:
                st.session_state.match_error = cv_error
            else:
                with st.spinner("Comparing the CV with the job ad..."):
                    st.session_state.match_result, st.session_state.match_error = match_cv_to_job(
                        cv_text, st.session_state.ad_text
                    )

    result = st.session_state.result
    if result is None or st.session_state.result_text != st.session_state.ad_text:
        return

    st.divider()

    job_titles = result["entities"]["JOB_TITLE"]
    headline = job_titles[0] if job_titles else "Job Ad"
    st.markdown(f"## {ICONS['JOB_TITLE']} {html.escape(headline)}")
    top_badges = chips(result["entities"]["WORK_MODE"], "WORK_MODE") + chips(
        result["entities"]["LANGUAGE"], "LANGUAGE"
    )
    st.markdown(top_badges, unsafe_allow_html=True)

    st.markdown("")
    detail_types = [t for t in ALLOWED_TYPES if t not in ("JOB_TITLE", "WORK_MODE", "LANGUAGE")]
    for row_start in (0, 2):
        row_cols = st.columns(2)
        for column, entity_type in zip(row_cols, detail_types[row_start : row_start + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{ICONS[entity_type]} {LABELS[entity_type]}**")
                    st.markdown(chips(result["entities"][entity_type], entity_type), unsafe_allow_html=True)

    with st.expander("Highlighted Original Text"):
        visible = set(
            st.multiselect(
                "Show entity types",
                options=list(ALLOWED_TYPES),
                default=list(ALLOWED_TYPES),
                format_func=lambda key: LABELS[key],
            )
        )
        st.markdown(
            highlighted_text(st.session_state.result_text, result["spans"], visible),
            unsafe_allow_html=True,
        )

    with st.expander("Technical View: Model Response and Span Mapping"):
        st.json(result["json"])
        st.caption(
            f"Model: {result['meta']['model']} · GBERT candidates: {result['meta']['gbert_candidates']} · "
            f"Unique spans: {result['meta']['spans_ok']} · "
            f"Not found in text: {result['meta']['spans_hallucinated']} · "
            f"Ambiguous: {result['meta']['spans_ambiguous']}"
        )
        st.download_button(
            "Download JSON",
            json.dumps(result["json"], ensure_ascii=False, indent=2),
            file_name="extraktion.json",
            mime="application/json",
        )

    if st.session_state.match_error:
        st.divider()
        st.subheader("🧑‍💼 Is this job right for you?")
        st.error(st.session_state.match_error)
    elif st.session_state.match_result is not None:
        st.divider()
        st.subheader("🧑‍💼 Is this job right for you?")
        match = st.session_state.match_result
        if match["fit"]:
            st.success(f"✅ This job is a good fit: {match['reason']}")
        else:
            st.warning(f"⚠️ This job is not a great fit: {match['reason']}")


if __name__ == "__main__":
    main()
