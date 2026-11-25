import os
import sys
import time
import requests
import subprocess
import streamlit as st
from typing import Dict, Any, List

try:
    from dotenv import load_dotenv
    _env_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
    else:
        load_dotenv(override=True)
except Exception:
    pass

# -----------------------------------------------------------------------------
# Page Configuration & Clean Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Resume Parser",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .candidate-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        color: #f8fafc;
    }
    .candidate-name {
        font-size: 1.75rem;
        font-weight: 700;
        color: #38bdf8;
        margin-bottom: 0.25rem;
    }
    .candidate-role {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 1rem;
    }
    .badge-ai {
        background: #059669;
        color: #ffffff;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-fallback {
        background: #d97706;
        color: #ffffff;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .skill-tag {
        display: inline-block;
        background: #0284c7;
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 0.35rem 0.75rem;
        margin: 0.2rem;
        border-radius: 9999px;
    }
</style>
""", unsafe_allow_html=True)

raw_port = (os.getenv("PORT") or "").strip()
DEFAULT_PORT = raw_port if raw_port else "3001"
raw_backend_url = (os.getenv("RESUME_PARSER_URL") or "").strip()
DEFAULT_BACKEND_URL = raw_backend_url if raw_backend_url else f"http://127.0.0.1:{DEFAULT_PORT}"

def check_backend_health(base_url: str) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{base_url}/health", timeout=0.6)
        if resp.status_code == 200:
            return {"online": True, **resp.json()}
        return {"online": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"online": False, "error": str(e)}

def ensure_backend_running(base_url: str) -> Dict[str, Any]:
    return check_backend_health(base_url)

def parse_resume_api(base_url: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    # 1. Try HTTP backend on port 3001 if available
    url = f"{base_url}/parse"
    files = {"resume": (filename, file_bytes)}
    try:
        resp = requests.post(url, files=files, timeout=60)
        data = resp.json()
        if resp.ok and data.get("success", True):
            return data
    except Exception:
        pass

    # 2. Seamless in-process fallback: directly parse using engine
    try:
        import asyncio
        from src.metaforgeParser import parse_resume_buffer
        candidate = asyncio.run(parse_resume_buffer(file_bytes, filename))
        return {"success": True, "data": candidate}
    except Exception as err:
        raise RuntimeError(f"Extraction error: {err}")

def parse_resumes_bulk_api(base_url: str, uploaded_files: List[Any]) -> Dict[str, Any]:
    # 1. Try HTTP backend on port 3001 if available
    url = f"{base_url}/parse/bulk"
    files = [("resumes", (f.name, f.getvalue())) for f in uploaded_files]
    try:
        resp = requests.post(url, files=files, timeout=120)
        data = resp.json()
        if resp.ok and data.get("success", True):
            return data
    except Exception:
        pass

    # 2. Seamless in-process fallback: directly parse using engine
    try:
        import asyncio
        from src.metaforgeParser import parse_resume_buffers_bulk
        items = [{"filename": f.name, "buffer": f.getvalue()} for f in uploaded_files]
        results = asyncio.run(parse_resume_buffers_bulk(items))
        return {"success": True, "results": results}
    except Exception as err:
        raise RuntimeError(f"Bulk extraction error: {err}")

    try:
        data = resp.json()
    except Exception:
        data = {}
    if not resp.ok or not data.get("success", True):
        msg = data.get("message") or data.get("error") or f"HTTP {resp.status_code} error from server"
        raise RuntimeError(msg)
    return data

def render_candidate(cand: Dict[str, Any], filename: str):
    parser_used = cand.get("parser", "legacy")
    badge_class = "badge-ai" if parser_used == "metaforge" else "badge-fallback"
    badge_label = "Gemini AI" if parser_used == "metaforge" else "Local Fallback Parser"

    # Candidate Header
    name = cand.get("candidateName") or "Name Not Detected"
    role = cand.get("role") or cand.get("technologiesRaw") or "Role Not Specified"

    st.markdown(f"""
    <div class="candidate-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div class="candidate-name">{name}</div>
                <div class="candidate-role">{role}</div>
            </div>
            <span class="{badge_class}">Engine: {badge_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2-Column Field Breakdown
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**📧 Email:**")
        st.write(cand.get("email") or "Not found")

        st.markdown("**📞 Phone:**")
        st.write(cand.get("contactNumber") or "Not found")

        st.markdown("**📍 Location:**")
        st.write(cand.get("currentLocation") or cand.get("location") or "Not found")

        st.markdown("**🔗 LinkedIn:**")
        linkedin = cand.get("linkedinUrl")
        if linkedin:
            st.markdown(f"[{linkedin}]({linkedin})")
        else:
            st.write("Not found")

    with c2:
        st.markdown("**💼 Total Experience:**")
        st.write(cand.get("totalExperience") or "Not found")

        st.markdown("**🎓 Highest Qualification:**")
        st.write(cand.get("highestQualification") or "Not found")

        st.markdown("**🏢 Current Employer:**")
        st.write(cand.get("currentEmployer") or "Not specified")

        st.markdown("**📄 Source File:**")
        st.write(cand.get("sourceFile") or filename)

    # Skills Section (Chips)
    st.markdown("---")
    st.markdown("### 🛠️ Skills & Technologies")
    skills_list = cand.get("skills") if isinstance(cand.get("skills"), list) else None
    if not skills_list and cand.get("skillsRaw"):
        skills_list = [s.strip() for s in cand["skillsRaw"].split(",") if s.strip()]
    if skills_list:
        chips_html = "".join([f'<span class="skill-tag">{skill}</span>' for skill in skills_list])
        st.markdown(chips_html, unsafe_allow_html=True)
    else:
        st.info("No specific skills extracted from dedicated section.")

    # Expandable JSON View
    with st.expander("🔍 View Raw Parsed JSON"):
        st.json(cand)

# -----------------------------------------------------------------------------
# Application Header & Status Check
# -----------------------------------------------------------------------------
st.title("📄 Resume Parser")
st.caption("Extract structured candidate data from PDF, DOCX, DOC, or TXT resumes.")

health = ensure_backend_running(DEFAULT_BACKEND_URL)
if health.get("online"):
    ai_ready = bool(health.get("aiParserAvailable"))
    if ai_ready:
        st.caption("🟢 **Engine**: Gemini AI (Connected on port 3001)")
    else:
        st.caption("🟠 **Engine**: Local Fallback Parser")
else:
    from src.metaforgeParser import is_metaforge_parser_available
    if is_metaforge_parser_available():
        st.caption("🟢 **Engine**: Gemini AI (Ready)")
    else:
        st.caption("🟠 **Engine**: Local Fallback Parser (Ready)")

# -----------------------------------------------------------------------------
# File Upload Section (Single Resume & Bulk Upload Tabs)
# -----------------------------------------------------------------------------
tab_single, tab_bulk = st.tabs(["📄 Single Resume", "📁 Bulk Upload"])

# ----------------- Tab 1: Single Resume Upload -----------------
with tab_single:
    st.markdown("### Single Resume Upload")
    st.caption("Upload an individual resume to parse and view structured candidate fields.")

    single_file = st.file_uploader(
        "Choose a resume file",
        type=["pdf", "docx", "doc", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=False,
        key="single_resume_uploader",
        help="Supports PDF, Word Documents (.docx, .doc), Plain Text (.txt), and scanned image files."
    )

    if single_file:
        file_bytes = single_file.getvalue()
        filename = single_file.name

        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            parse_btn = st.button("🚀 Parse Resume", type="primary", use_container_width=True, key="parse_single_btn")
        with col_info:
            st.write(f"📁 **File:** `{filename}` ({round(len(file_bytes)/1024, 1)} KB)")

        if parse_btn:
            with st.spinner("Extracting candidate fields..."):
                try:
                    result = parse_resume_api(DEFAULT_BACKEND_URL, file_bytes, filename)
                    candidate = result.get("data", {})
                    st.session_state["single_candidate"] = candidate
                    st.session_state["single_filename"] = filename
                except Exception as e:
                    st.error(f"{e}")

    if "single_candidate" in st.session_state:
        st.markdown("---")
        col_res_header, col_res_clear = st.columns([3, 1])
        with col_res_header:
            st.subheader("Extracted Candidate Profile")
        with col_res_clear:
            if st.button("🗑️ Clear Result", key="clear_single"):
                st.session_state.pop("single_candidate", None)
                st.session_state.pop("single_filename", None)
                st.rerun()

        if "single_candidate" in st.session_state:
            render_candidate(st.session_state["single_candidate"], st.session_state.get("single_filename", "resume"))


# ----------------- Tab 2: Bulk Resume Upload -----------------
with tab_bulk:
    st.markdown("### 📁 Bulk Resume Upload")
    st.caption("Upload multiple resumes (up to 5 files) simultaneously for batch extraction.")

    bulk_files = st.file_uploader(
        "Choose resume file(s) for bulk parsing",
        type=["pdf", "docx", "doc", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="bulk_resume_uploader",
        help="Select between 1 and 5 resumes (PDF, DOCX, DOC, TXT, or scanned images)."
    )

    if bulk_files:
        if len(bulk_files) > 5:
            st.error(f"⚠️ Maximum 5 resumes allowed per batch upload. You selected {len(bulk_files)} files. Please select up to 5 files.")
        else:
            col_btn, col_info = st.columns([1, 2])
            with col_btn:
                btn_text = f"🚀 Parse {len(bulk_files)} Resume" + ("s" if len(bulk_files) > 1 else "")
                parse_bulk_btn = st.button(btn_text, type="primary", use_container_width=True, key="parse_bulk_btn")
            with col_info:
                st.write(f"📁 **Batch:** {len(bulk_files)} of 5 files selected")
                for bf in bulk_files:
                    st.caption(f"• `{bf.name}` ({round(len(bf.getvalue())/1024, 1)} KB)")

            if parse_bulk_btn:
                with st.spinner(f"Extracting candidate fields from {len(bulk_files)} file(s)..."):
                    try:
                        result = parse_resumes_bulk_api(DEFAULT_BACKEND_URL, bulk_files)
                        st.session_state["bulk_results"] = result.get("results", [])
                    except Exception as e:
                        st.error(f"{e}")

    if "bulk_results" in st.session_state and st.session_state["bulk_results"]:
        st.markdown("---")
        results = st.session_state["bulk_results"]
        total = len(results)
        succeeded = sum(1 for item in results if item.get("status") == "done")
        failed = total - succeeded

        col_res_header, col_res_clear = st.columns([3, 1])
        with col_res_header:
            st.subheader(f"📊 Batch Results ({total} files)")
        with col_res_clear:
            if st.button("🗑️ Clear Results", key="clear_bulk"):
                st.session_state.pop("bulk_results", None)
                st.rerun()

        if "bulk_results" in st.session_state:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Resumes", total)
            m2.metric("Successfully Parsed", succeeded)
            m3.metric("Failed", failed)

            st.write("")
            for idx, item in enumerate(results):
                src_name = item.get("sourceFile", f"File #{idx+1}")
                status = item.get("status")
                if status == "done":
                    cand_data = item.get("data", {})
                    cand_name = cand_data.get("candidateName") or "Candidate"
                    with st.expander(f"✅ [{idx+1}/{total}] {src_name} — {cand_name}", expanded=(idx == 0)):
                        render_candidate(cand_data, src_name)
                else:
                    err_msg = item.get("error", "Failed to parse")
                    st.error(f"❌ **[{idx+1}/{total}] {src_name}**: {err_msg}")

if __name__ == "__main__" and not st.runtime.exists():
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", __file__, "--server.headless", "true"]
    sys.exit(stcli.main())
