# -*- coding: utf-8 -*-
"""Flask + tiny local LLM standardizer with incremental JSONL CLI output."""

from __future__ import annotations

import json
import os
import re
import sys
import difflib
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request
from huggingface_hub import hf_hub_download
from llama_cpp import Llama  # CPU-only by default if N_GPU_LAYERS=0

app = Flask(__name__)

# ---------------- Model config ----------------
MODEL_REPO = os.getenv(
    "MODEL_REPO",
    "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",
)
MODEL_FILE = os.getenv(
    "MODEL_FILE",
    "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
)

N_THREADS = int(os.getenv("N_THREADS", str(os.cpu_count() or 2)))
N_CTX = int(os.getenv("N_CTX", "2048"))
N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "0"))  # 0 → CPU-only

CANON_UNIS_PATH = os.getenv("CANON_UNIS_PATH", "canon_universities.txt")
CANON_PROGS_PATH = os.getenv("CANON_PROGS_PATH", "canon_programs.txt")

# Precompiled, non-greedy JSON object matcher to tolerate chatter around JSON
JSON_OBJ_RE = re.compile(r"\{.*?\}", re.DOTALL)

# ---------------- Canonical lists + abbrev maps ----------------
def _read_lines(path: str) -> List[str]:
    """Read non-empty, stripped lines from a file (UTF-8)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


CANON_UNIS = _read_lines(CANON_UNIS_PATH)
CANON_PROGS = _read_lines(CANON_PROGS_PATH)

ABBREV_UNI: Dict[str, str] = {
    r"(?i)^mcg(\.|ill)?$": "McGill University",
    r"(?i)^(ubc|u\.?b\.?c\.?)$": "University of British Columbia",
    r"(?i)^uoft$": "University of Toronto",
}

COMMON_UNI_FIXES: Dict[str, str] = {
    "McGiill University": "McGill University",
    "Mcgill University": "McGill University",
    # Normalize 'Of' → 'of'
    "University Of British Columbia": "University of British Columbia",
}

COMMON_PROG_FIXES: Dict[str, str] = {
    "Mathematic": "Mathematics",
    "Info Studies": "Information Studies",
}

# ---------------- Few-shot prompt ----------------
# SYSTEM_PROMPT = (
#     "You are a data cleaning assistant. Standardize degree program and university "
#     "names.\n\n"
#     "Rules:\n"
#     "- Input provides 'program' and 'university' in their respective fields.\n"
#     "- Trim extra spaces and commas.\n"
#     '- Expand obvious abbreviations (e.g., "McG" -> "McGill University", '
#     '"UBC" -> "University of British Columbia").\n'
#     "- Use Title Case for program; use official capitalization for university "
#     "names (e.g., \"University of X\").\n"
#     '- Ensure correct spelling (e.g., "McGill", not "McGiill").\n'
#     '- If university cannot be inferred, return "Unknown".\n\n'
#     "Return JSON ONLY with keys:\n"
#     "  standardized_program, standardized_university\n"
# )

SYSTEM_PROMPT = (
"### Role\n"
"You are a precise Data Normalization Specialist. Your task is to clean and standardize academic data from The GradCafe.\n"
"### Task\n"
"Standardize the 'program' and 'university' fields into their most complete, formal academic versions.\n"
"### Rules for Standardization\n"
"1. Program Name:\n"
   "- Convert to Title Case (e.g., 'physics' -> 'Physics').\n"
   "- Expand abbreviations (e.g., 'PoliSci' -> 'Political Science', 'Mech E' -> 'Mechanical Engineering', 'CS' -> 'Computer Science').\n"
   "- Remove irrelevant details like 'Interdisciplinary' or 'Department of' unless it is part of the formal name.\n"

"2. University Name:\n"
   "- Use the full, formal name (e.g., 'U of T' -> 'University of Toronto').\n"
   "- Correct common typos (e.g., 'McGiill' -> 'McGill University').\n"
   "- Standardize 'UOfX' or 'U of X' to 'University of X'.\n"
   "- If the name is ambiguous (e.g., 'UofA' could be Arizona or Alberta), prioritize the most likely North American institution unless context suggests otherwise.\n"

"### Constraints\n"
"- DO NOT add conversational filler or commentary.\n"
"- If the university is missing or impossible to determine, return 'Unknown'.\n"

"### Output Format\n"
"Return JSON ONLY with exactly these two keys:\n"
"{\n"
  "\"standardized_program\": \"<Clean Name>\",\n"
  "\"standardized_university\": \"<Clean Name>\"\n"
"}"
)
FEW_SHOTS: List[Tuple[Dict[str, str], Dict[str, str]]] = [
    (
        {"program": "Information Studies",
         "university": "McGill University"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Information",
         "university": "McG"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Mathematics",
         "university": "University Of British Columbia"},
        {
            "standardized_program": "Mathematics",
            "standardized_university": "University of British Columbia",
        },
    ),
    (
        {"program": "physics",
         "university": "UofA"},
        {
            "standardized_program": "Physics",
            "standardized_university": "University of Arizona",
        },
    ),
    (
        {"program": "PoliSci",
         "university": "Georgetown"},
        {
            "standardized_program": "Political Science",
            "standardized_university": "Georgetown University",
        },
    ),
    (
        {"program": "Mech E",
         "university": "U Rochester"},
        {
            "standardized_program": "Mechanical Engineering",
            "standardized_university": "University of Rochester",
        },
    ),
    (
    {"program": "Bio-med sci",
     "university": "SUNY SB"},
    {
        "standardized_program": "Biomedical Sciences",
        "standardized_university": "Stony Brook University, The State University of New York",
    }
    ),
    (
    {"program": "clinical psych",
     "university": "MIT"},
    {
        "standardized_program": "Clinical Psychology",
        "standardized_university": "Massachusetts Institute of Technology",
    }
    ),
]

# SYSTEM_PROMPT = (
#     "You are a data cleaning assistant. Standardize degree program and university "
#     "names.\n\n"
#     "Rules:\n"
#     "- Input provides a single string under key `program` that may contain both "
#     "program and university.\n"
#     "- Split into (program name, university name).\n"
#     "- Trim extra spaces and commas.\n"
#     '- Expand obvious abbreviations (e.g., "McG" -> "McGill University", '
#     '"UBC" -> "University of British Columbia").\n'
#     "- Use Title Case for program; use official capitalization for university "
#     "names (e.g., \"University of X\").\n"
#     '- Ensure correct spelling (e.g., "McGill", not "McGiill").\n'
#     '- If university cannot be inferred, return "Unknown".\n\n'
#     "Return JSON ONLY with keys:\n"
#     "  standardized_program, standardized_university\n"
# )

# FEW_SHOTS: List[Tuple[Dict[str, str], Dict[str, str]]] = [
#     (
#         {"program": "Information Studies, McGill University"},
#         {
#             "standardized_program": "Information Studies",
#             "standardized_university": "McGill University",
#         },
#     ),
#     (
#         {"program": "Information, McG"},
#         {
#             "standardized_program": "Information Studies",
#             "standardized_university": "McGill University",
#         },
#     ),
#     (
#         {"program": "Mathematics, University Of British Columbia"},
#         {
#             "standardized_program": "Mathematics",
#             "standardized_university": "University of British Columbia",
#         },
#     ),
# ]

_LLM: Llama | None = None


def _load_llm() -> Llama:
    """Download (or reuse) the GGUF file and initialize llama.cpp."""
    global _LLM
    if _LLM is not None:
        return _LLM

    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir="models",
        local_dir_use_symlinks=False,
        force_filename=MODEL_FILE,
    )

    _LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _LLM


def _split_fallback(text: str) -> Tuple[str, str]:
    """Simple, rules-first parser if the model returns non-JSON."""
    s = re.sub(r"\s+", " ", (text or "")).strip().strip(",")
    parts = [p.strip() for p in re.split(r",| at | @ ", s) if p.strip()]
    prog = parts[0] if parts else ""
    uni = parts[1] if len(parts) > 1 else ""

    # High-signal expansions
    if re.fullmatch(r"(?i)mcg(ill)?(\.)?", uni or ""):
        uni = "McGill University"
    if re.fullmatch(
        r"(?i)(ubc|u\.?b\.?c\.?|university of british columbia)",
        uni or "",
    ):
        uni = "University of British Columbia"

    # Title-case program; normalize 'Of' → 'of' for universities
    prog = prog.title()
    if uni:
        uni = re.sub(r"\bOf\b", "of", uni.title())
    else:
        uni = "Unknown"
    return prog, uni


def _best_match(name: str, candidates: List[str], cutoff: float = 0.86) -> str | None:
    """Fuzzy match via difflib (lightweight, Replit-friendly)."""
    if not name or not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _post_normalize_program(prog: str) -> str:
    """Apply common fixes, title case, then canonical/fuzzy mapping."""
    p = (prog or "").strip()
    p = COMMON_PROG_FIXES.get(p, p)
    p = p.title()
    if p in CANON_PROGS:
        return p
    match = _best_match(p, CANON_PROGS, cutoff=0.84)
    return match or p


def _post_normalize_university(uni: str) -> str:
    """Expand abbreviations, apply common fixes, capitalization, and canonical map."""
    u = (uni or "").strip()
    
    # Abbreviations
    for pat, full in ABBREV_UNI.items():
        if re.fullmatch(pat, u):
            u = full
            break
    
    # Common spelling fixes
    u = COMMON_UNI_FIXES.get(u, u)

    # Normalize 'Of' → 'of'
    if u:
        u = re.sub(r"\bOf\b", "of", u.title())

    # Canonical or fuzzy map
    if u in CANON_UNIS:
        return u
    match = _best_match(u, CANON_UNIS, cutoff=0.86)
    return match or u or "Unknown"


def _call_llm(program_text: str, school_text: str) -> Dict[str, str]:
    """Query the tiny LLM and return standardized fields."""
    llm = _load_llm()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for x_in, x_out in FEW_SHOTS:
        messages.append(
            {"role": "user", "content": json.dumps(x_in, ensure_ascii=False)}
        )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(x_out, ensure_ascii=False),
            }
        )
    messages.append(
        {
            "role": "user",
            "content": json.dumps({"program": program_text, "university": school_text}, ensure_ascii=False),
        }
    )

    out = llm.create_chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=128,
        top_p=1.0,
    )

    text = (out["choices"][0]["message"]["content"] or "").strip()
    try:
        match = JSON_OBJ_RE.search(text)
        obj = json.loads(match.group(0) if match else text)
        std_prog = str(obj.get("standardized_program", "")).strip()
        std_uni = str(obj.get("standardized_university", "")).strip()
    except Exception:
        std_prog, std_uni = _split_fallback(program_text)

    std_prog = _post_normalize_program(std_prog)
    std_uni = _post_normalize_university(std_uni)
    return {
        "standardized_program": std_prog,
        "standardized_university": std_uni,
    }


def _normalize_input(payload: Any) -> List[Dict[str, Any]]:
    """Accept either a list of rows or {'rows': [...]}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return []


@app.get("/")
def health() -> Any:
    """Simple liveness check."""
    return jsonify({"ok": True})


@app.post("/standardize")
def standardize() -> Any:
    """Standardize rows from an HTTP request and return JSON."""
    payload = request.get_json(force=True, silent=True)
    rows = _normalize_input(payload)

    out: List[Dict[str, Any]] = []
    for row in rows:
        program_text = (row or {}).get("program") or ""
        result = _call_llm(program_text)
        row["llm-generated-program"] = result["standardized_program"]
        row["llm-generated-university"] = result["standardized_university"]
        out.append(row)

    return jsonify({"rows": out})


def _cli_process_file(
    in_path: str,
    out_path: str | None,
    append: bool,
    to_stdout: bool,
) -> None:
    """Process a JSON file and write JSONL incrementally."""
    with open(in_path, "r", encoding="utf-8") as f:
        rows = _normalize_input(json.load(f))

    sink = sys.stdout if to_stdout else None
    if not to_stdout:
        # Get rid of filename extension before appending .jsonl
        # in_path = re.sub(r'\..*', '', in_path)
        out_path = out_path or ('llm_extend_applicant_data.jsonl')
        mode = "a" if append else "w"
        sink = open(out_path, mode, encoding="utf-8")

    assert sink is not None  # for type-checkers

    try:
        for row in rows:
            program_text = (row or {}).get("program") or ""
            school_text = (row or {}).get("university") or ""
            result = _call_llm(program_text, school_text)
            row["llm-generated-program"] = result["standardized_program"]
            row["llm-generated-university"] = result["standardized_university"]

            json.dump(row, sink, ensure_ascii=False)
            sink.write("\n")
            sink.flush()
    finally:
        if sink is not sys.stdout:
            sink.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Standardize program/university with a tiny local LLM.",
    )
    parser.add_argument(
        "--file",
        help="Path to JSON input (list of rows or {'rows': [...]})",
        default=None,
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the HTTP server instead of CLI.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for JSON Lines (ndjson). "
        "Defaults to <input>.jsonl when --file is set.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output file instead of overwriting.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write JSON Lines to stdout instead of a file.",
    )
    args = parser.parse_args()

    if args.serve or args.file is None:
        port = int(os.getenv("PORT", "8000"))
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        _cli_process_file(
            in_path=args.file,
            out_path=args.out,
            append=bool(args.append),
            to_stdout=bool(args.stdout),
        )
