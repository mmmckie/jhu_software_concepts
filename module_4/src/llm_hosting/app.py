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

# Configuration intentionally comes from env vars to support local and CI execution.
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
    """Read non-empty UTF-8 lines from a text file.

    :param path: File path to read.
    :type path: str
    :returns: Stripped non-empty lines, or empty list if file missing.
    :rtype: list[str]
    """
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

_LLM: Llama | None = None


def _load_llm() -> Llama:
    """Load and memoize the local llama.cpp model.

    :returns: Initialized llama.cpp model instance.
    :rtype: llama_cpp.Llama
    """
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

    # Load once and reuse to avoid repeated model init costs per request/row.
    _LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _LLM


def _split_fallback(text: str) -> Tuple[str, str]:
    """Parse program/university with heuristics when model output is invalid.

    :param text: Raw text to parse.
    :type text: str
    :returns: ``(program, university)`` tuple.
    :rtype: tuple[str, str]
    """
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
    """Return best fuzzy match from candidate list.

    :param name: Input string to match.
    :type name: str
    :param candidates: Candidate canonical strings.
    :type candidates: list[str]
    :param cutoff: Similarity threshold in ``[0.0, 1.0]``.
    :type cutoff: float
    :returns: Best candidate or ``None`` if no match meets cutoff.
    :rtype: str | None
    """
    if not name or not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _post_normalize_program(prog: str) -> str:
    """Normalize a program string to canonical output format.

    :param prog: Raw or model-generated program text.
    :type prog: str
    :returns: Canonicalized program name.
    :rtype: str
    """
    p = (prog or "").strip()
    p = COMMON_PROG_FIXES.get(p, p)
    p = p.title()
    if p in CANON_PROGS:
        return p
    match = _best_match(p, CANON_PROGS, cutoff=0.84)
    return match or p


def _post_normalize_university(uni: str) -> str:
    """Normalize a university string to canonical output format.

    :param uni: Raw or model-generated university text.
    :type uni: str
    :returns: Canonicalized university name, or ``\"Unknown\"``.
    :rtype: str
    """
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
    """Call the model and return standardized fields.

    :param program_text: Program value from input row.
    :type program_text: str
    :param school_text: University value from input row.
    :type school_text: str
    :returns: Standardized program and university.
    :rtype: dict[str, str]
    """
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
        # Pull the first JSON object even if the model adds extra wrapper text.
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
    """Normalize accepted request payload formats into a row list.

    :param payload: Raw request/CLI payload.
    :type payload: Any
    :returns: List of row dictionaries.
    :rtype: list[dict[str, Any]]
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return []


@app.get("/")
def health() -> Any:
    """Return service health status.

    :returns: JSON response containing ``{\"ok\": True}``.
    :rtype: flask.Response
    """
    return jsonify({"ok": True})


@app.post("/standardize")
def standardize() -> Any:
    """Standardize request rows and return enriched payloads.

    :returns: JSON response containing standardized rows.
    :rtype: flask.Response
    """
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
    """Process input JSON rows and emit JSONL output incrementally.

    :param in_path: Input JSON path.
    :type in_path: str
    :param out_path: Destination JSONL path when not writing to stdout.
    :type out_path: str | None
    :param append: Whether to append to output file.
    :type append: bool
    :param to_stdout: Whether to write JSONL lines to stdout.
    :type to_stdout: bool
    :returns: ``None``.
    :rtype: None
    """
    with open(in_path, "r", encoding="utf-8") as f:
        rows = _normalize_input(json.load(f))

    sink = sys.stdout if to_stdout else None
    if not to_stdout:
        # Get rid of filename extension before appending .jsonl
        # in_path = re.sub(r'\..*', '', in_path)
        out_path = out_path or ('llm_extend_applicant_data.jsonl')
        mode = "a" if append else "w"
        # File sink path is resolved once; each processed row is streamed immediately.
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
