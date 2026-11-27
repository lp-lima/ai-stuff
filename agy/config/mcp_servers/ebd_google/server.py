#!/usr/bin/env python3
"""
Local MCP stdio server (`ebd-google`) for EBD Google Docs & Google Drive workflows.

Reuses the existing Service Account credentials for Google Docs/Drive read/edit
and delegates personal-Drive file duplication (`files.copy` for Teleprompter)
to a lightweight Google Apps Script Web App configured in `apps_script_secret.json`.
"""

import hashlib
import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = "/home/lp-lima/.gemini/skills/import-nubank-expenses/assets/credentials.json"
COURSES_REGISTRY_PATH = "/mnt/c/Users/lplim/repos/revisao_ebd/cursos_registrados.json"
APPS_SCRIPT_SECRET_PATH = os.path.join(SERVER_DIR, "apps_script_secret.json")
DOWNLOADS_DIR = "/mnt/c/Users/lplim/Downloads"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

_SESSION: Optional[AuthorizedSession] = None


def get_session() -> AuthorizedSession:
    global _SESSION
    if _SESSION is None:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        _SESSION = AuthorizedSession(creds)
    return _SESSION


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower().strip())


def extract_doc_id(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def load_courses_registry() -> Dict[str, Any]:
    if not os.path.exists(COURSES_REGISTRY_PATH):
        raise FileNotFoundError(f"Registro de cursos não encontrado: {COURSES_REGISTRY_PATH}")
    with open(COURSES_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_course(course_query: str) -> Tuple[str, Dict[str, Any]]:
    registry = load_courses_registry()
    q = norm_key(course_query)
    if not q:
        raise ValueError("Nome do curso vazio.")

    # Exact normalized key match
    for k, v in registry.items():
        if norm_key(k) == q:
            return k, v

    # Substring match against key or canva_folder_path or path basename
    candidates = []
    for k, v in registry.items():
        nk = norm_key(k)
        npath = norm_key(os.path.basename(v.get("path", "")))
        ncanva = norm_key(v.get("canva_folder_path") or "")
        if q in nk or nk in q or q in npath or (ncanva and q in ncanva):
            candidates.append((k, v))

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Prefer shortest key containing query or exact token match
        candidates.sort(key=lambda item: len(item[0]))
        return candidates[0]

    raise ValueError(
        f"Curso '{course_query}' não encontrado em {COURSES_REGISTRY_PATH}. "
        f"Cursos disponíveis: {list(registry.keys())}"
    )


def fetch_doc(doc_id: str) -> Dict[str, Any]:
    s = get_session()
    resp = s.get(f"https://docs.googleapis.com/v1/documents/{doc_id}?includeTabsContent=true")
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao acessar Google Doc {doc_id} ({resp.status_code}): {resp.text}")
    return resp.json()


def get_tab_by_title(doc: Dict[str, Any], tab_title: str) -> Optional[Dict[str, Any]]:
    target = norm_key(tab_title)
    for t in doc.get("tabs", []):
        title = t.get("tabProperties", {}).get("title", "")
        if norm_key(title) == target:
            return t
    return None


def paragraph_plain_text(p: Dict[str, Any]) -> str:
    parts = []
    for el in p.get("elements", []):
        tr = el.get("textRun")
        if tr:
            parts.append(tr.get("content", ""))
    return "".join(parts)


def paragraph_clean_text(p: Dict[str, Any]) -> str:
    # Replace vertical tabs (soft line breaks inside a paragraph) with space, strip trailing newline
    raw = paragraph_plain_text(p)
    raw = raw.replace("\v", " ").replace("\r", "")
    return re.sub(r"[ \t]+", " ", raw).strip()


def parse_lesson_num_from_heading(text: str) -> Optional[int]:
    m = re.match(r"^\s*Aula\s+0*(\d+)\b", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def find_lessons_in_tab(tab: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return ordered list of lesson slices found via HEADING_1 in a tab."""
    body = tab.get("documentTab", {}).get("body", {}).get("content", [])
    lessons = []
    for idx, el in enumerate(body):
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        st = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        if st != "HEADING_1":
            continue
        txt = paragraph_clean_text(p)
        if not txt:
            continue
        num = parse_lesson_num_from_heading(txt)
        if num is not None:
            lessons.append({"lesson_num": num, "title": txt, "body_idx": idx})
        elif norm_key(txt).startswith("introducao ao curso"):
            lessons.append({"lesson_num": 0, "title": txt, "body_idx": idx})

    # Compute end body_idx for each lesson
    for i, item in enumerate(lessons):
        item["end_body_idx"] = lessons[i + 1]["body_idx"] if i + 1 < len(lessons) else len(body)
    return lessons


def resolve_active_tab(
    doc: Dict[str, Any], lesson_num: int, requested_tab: str = "auto"
) -> Tuple[Dict[str, Any], str, Optional[int], str]:
    """
    Resolve which tab (`Revisada` or `Tmp`) should be used for `lesson_num`.
    Rule:
      - Inspect `Revisada`: find highest lesson_num and set of lesson numbers present.
      - If requested_tab != "auto", use that explicit tab.
      - Otherwise, if `lesson_num` is already in `Revisada` (including matching the last lesson),
        use `Revisada` so existing comments are preserved.
      - Otherwise use `Tmp`.
    """
    rev_tab = get_tab_by_title(doc, "Revisada")
    tmp_tab = get_tab_by_title(doc, "Tmp")

    rev_lessons = find_lessons_in_tab(rev_tab) if rev_tab else []
    rev_nums = [x["lesson_num"] for x in rev_lessons]
    rev_last = max(rev_nums) if rev_nums else None

    req = norm_key(requested_tab or "auto")
    if req != "auto":
        explicit = get_tab_by_title(doc, requested_tab)
        if not explicit:
            avail = [t.get("tabProperties", {}).get("title") for t in doc.get("tabs", [])]
            raise ValueError(f"Aba '{requested_tab}' não encontrada. Abas disponíveis: {avail}")
        tname = explicit["tabProperties"]["title"]
        return explicit, tname, rev_last, f"Aba '{tname}' selecionada explicitamente."

    if rev_tab and lesson_num in rev_nums:
        return (
            rev_tab,
            "Revisada",
            rev_last,
            f"Aula {lesson_num:02d} já está na aba 'Revisada' (última aula lá: {rev_last:02d}); usando 'Revisada' para preservar comentários e formatação.",
        )

    if not tmp_tab:
        raise ValueError(
            f"Aula {lesson_num:02d} não encontrada na aba 'Revisada' (última aula: {rev_last}) "
            f"e a aba 'Tmp' não existe no documento."
        )

    # Check if Tmp has content
    tmp_body = tmp_tab.get("documentTab", {}).get("body", {}).get("content", [])
    has_text = any(
        "paragraph" in el and paragraph_clean_text(el["paragraph"])
        for el in tmp_body
    )
    if not has_text:
        raise ValueError(
            f"Aula {lesson_num:02d} não está na aba 'Revisada' (última aula: {rev_last}) e a aba 'Tmp' está vazia."
        )

    return (
        tmp_tab,
        "Tmp",
        rev_last,
        f"Última aula na 'Revisada' é {rev_last if rev_last is not None else 'nenhuma'} (≠ {lesson_num:02d}); usando aba 'Tmp'.",
    )


def get_lesson_elements(
    tab: Dict[str, Any], tab_name: str, lesson_num: int
) -> List[Dict[str, Any]]:
    body = tab.get("documentTab", {}).get("body", {}).get("content", [])
    lessons = find_lessons_in_tab(tab)

    for item in lessons:
        if item["lesson_num"] == lesson_num:
            return body[item["body_idx"] : item["end_body_idx"]]

    # If in Tmp and there's only one lesson or no explicit matching number check
    if norm_key(tab_name) == "tmp":
        if lessons:
            found_nums = [x["lesson_num"] for x in lessons]
            raise ValueError(
                f"A aba 'Tmp' contém a(s) aula(s) {found_nums}, não a Aula {lesson_num:02d}."
            )
        # Fallback: return all body elements if Tmp has content without HEADING_1
        return body

    found_nums = [x["lesson_num"] for x in lessons]
    raise ValueError(
        f"Aula {lesson_num:02d} não encontrada na aba '{tab_name}'. Aulas encontradas: {found_nums}"
    )


def render_paragraph_markdown(p: Dict[str, Any], lists_map: Dict[str, Any], list_counters: Dict[str, int]) -> Optional[str]:
    clean = paragraph_clean_text(p)
    if not clean:
        return None

    style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")

    # Build inline formatted text
    parts = []
    for el in p.get("elements", []):
        tr = el.get("textRun")
        if not tr:
            continue
        content = tr.get("content", "").replace("\v", " ").replace("\r", "")
        if content == "\n":
            continue
        content = content.rstrip("\n")
        if not content:
            continue
        ts = tr.get("textStyle", {})
        bold = bool(ts.get("bold"))
        italic = bool(ts.get("italic"))
        # Do not wrap pure whitespace in markdown emphasis
        if content.strip() and style == "NORMAL_TEXT":
            lead = content[: len(content) - len(content.lstrip())]
            trail = content[len(content.rstrip()) :]
            core = content.strip()
            if bold and italic:
                content = f"{lead}***{core}***{trail}"
            elif bold:
                content = f"{lead}**{core}**{trail}"
            elif italic:
                content = f"{lead}*{core}*{trail}"
        parts.append(content)

    line = re.sub(r"[ \t]+", " ", "".join(parts)).strip()
    if not line:
        return None

    if style == "HEADING_1":
        return f"# {line}"
    if style == "HEADING_2":
        return f"## {line}"
    if style == "HEADING_3":
        return f"### {line}"

    bullet = p.get("bullet")
    if bullet:
        lid = bullet.get("listId", "")
        glyph_type = (
            lists_map.get(lid, {})
            .get("listProperties", {})
            .get("nestingLevels", [{}])[0]
            .get("glyphType", "")
        )
        if glyph_type == "DECIMAL":
            list_counters[lid] = list_counters.get(lid, 0) + 1
            return f"{list_counters[lid]}. {line}"
        return f"- {line}"

    return line


def extract_theme_and_ref(title_full: str) -> Tuple[str, str]:
    """Extract clean theme and trailing scripture reference from 'Aula 06: Tema (Fp 3.12-21)'."""
    s = re.sub(r"^\s*Aula\s+0*\d+\s*[:–-]\s*", "", title_full, flags=re.IGNORECASE).strip()
    ref = ""
    m = re.search(r"\(([^()]+)\)\s*$", s)
    if m:
        ref = m.group(1).strip()
        s = s[: m.start()].strip()
    return s, ref


def parse_key_verse(text: str) -> Optional[Dict[str, str]]:
    """Detect and parse key verse paragraph like '“Texto...” (1 Pedro 2.11)'."""
    m = re.search(r"\(([^()]{2,50})\)\s*$", text.strip())
    if not m:
        return None
    ref = m.group(1).strip()
    # Must look like a Bible reference (contains a digit)
    if not re.search(r"\d", ref):
        return None
    verse_raw = text[: m.start()].strip()
    # Usually wrapped in quotes or relatively short opening verse
    if not (verse_raw.startswith(("“", '"', "'", "«")) or len(verse_raw) < 600):
        return None
    verse_clean = verse_raw.strip('“”"\'«» ')
    return {
        "full_text": text.strip(),
        "verse_text": verse_clean,
        "reference": ref,
    }


def classify_special_section(heading_text: str) -> Optional[str]:
    nk = norm_key(heading_text)
    if nk.startswith("ideia central"):
        return "ideia_central"
    if "reflexao" in nk and "pergunta" in nk:
        return "perguntas_reflexao"
    if "discussao" in nk and "pergunta" in nk:
        return "perguntas_discussao"
    if "tarefa" in nk and "casa" in nk:
        return "tarefas_de_casa"
    return None


def parse_lesson_structure(
    elements: List[Dict[str, Any]], lists_map: Dict[str, Any]
) -> Dict[str, Any]:
    title_full = ""
    key_verse: Optional[Dict[str, str]] = None
    introduction: List[str] = []
    topics: List[Dict[str, Any]] = []
    ideia_central_paras: List[str] = []
    perguntas_reflexao: List[str] = []
    perguntas_discussao: List[str] = []
    tarefas_de_casa: List[str] = []

    current_section: str = "intro"  # "intro", "topic", or special key
    current_topic: Optional[Dict[str, Any]] = None
    md_lines: List[str] = []
    list_counters: Dict[str, int] = {}

    for el in elements:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        st = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        clean = paragraph_clean_text(p)
        md_line = render_paragraph_markdown(p, lists_map, list_counters)
        if md_line:
            md_lines.append(md_line)

        if not clean:
            continue

        if st == "HEADING_1":
            if not title_full:
                title_full = clean
            continue

        if st == "HEADING_2":
            special = classify_special_section(clean)
            if special:
                current_section = special
                current_topic = None
            else:
                current_section = "topic"
                current_topic = {
                    "index": len(topics) + 1,
                    "title": clean,
                    "paragraphs": [],
                }
                topics.append(current_topic)
            continue

        # Normal text / bullet / H3
        if current_section == "intro":
            if key_verse is None and not introduction:
                kv = parse_key_verse(clean)
                if kv:
                    key_verse = kv
                    continue
            introduction.append(clean)
        elif current_section == "topic" and current_topic is not None:
            current_topic["paragraphs"].append(clean)
        elif current_section == "ideia_central":
            ideia_central_paras.append(clean)
        elif current_section == "perguntas_reflexao":
            perguntas_reflexao.append(re.sub(r"^\d+\.\s*", "", clean))
        elif current_section == "perguntas_discussao":
            perguntas_discussao.append(re.sub(r"^\d+\.\s*", "", clean))
        elif current_section == "tarefas_de_casa":
            tarefas_de_casa.append(re.sub(r"^\d+\.\s*", "", clean))

    for t in topics:
        t["paragraph_count"] = len(t["paragraphs"])

    theme, scripture_ref = extract_theme_and_ref(title_full)
    return {
        "title_full": title_full,
        "theme": theme,
        "scripture_ref": scripture_ref,
        "key_verse": key_verse,
        "introduction": introduction,
        "topics": topics,
        "ideia_central": "\n\n".join(ideia_central_paras),
        "perguntas_reflexao": perguntas_reflexao,
        "perguntas_discussao": perguntas_discussao,
        "tarefas_de_casa": tarefas_de_casa,
        "markdown": "\n\n".join(md_lines) + "\n",
    }


def resolve_local_lesson_md_path(
    course_dir: str, course_display_name: str, lesson_num: int
) -> str:
    """Find existing Aula XX *.md in course_dir or build canonical filename."""
    os.makedirs(course_dir, exist_ok=True)
    pattern = re.compile(rf"^Aula\s+0*{lesson_num}\b.*\.md$", re.IGNORECASE)
    for fname in sorted(os.listdir(course_dir)):
        if pattern.match(fname):
            return os.path.join(course_dir, fname)
    clean_course = re.sub(r"^Apostila\s*[-–:]\s*", "", course_display_name, flags=re.IGNORECASE).strip()
    return os.path.join(course_dir, f"Aula {lesson_num:02d} - {clean_course}.md")


def get_parent_folder_id(file_id: str) -> str:
    s = get_session()
    r = s.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"fields": "id,name,parents", "supportsAllDrives": "true"},
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erro ao obter pasta pai no Drive ({r.status_code}): {r.text}")
    parents = r.json().get("parents", [])
    if not parents:
        raise RuntimeError(f"Arquivo {file_id} não possui pasta pai visível no Google Drive.")
    return parents[0]


def list_drive_children(folder_id: str, mime_type: Optional[str] = None) -> List[Dict[str, Any]]:
    s = get_session()
    q = f"'{folder_id}' in parents and trashed=false"
    if mime_type:
        q += f" and mimeType='{mime_type}'"
    r = s.get(
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": q,
            "fields": "files(id,name,mimeType)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "pageSize": 100,
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"Erro ao listar pasta {folder_id} no Drive ({r.status_code}): {r.text}")
    return r.json().get("files", [])


def find_sibling_folder(apostila_doc_id: str, keyword: str) -> Dict[str, Any]:
    parent_id = get_parent_folder_id(apostila_doc_id)
    folders = list_drive_children(parent_id, mime_type="application/vnd.google-apps.folder")
    kw = norm_key(keyword)
    for f in folders:
        if kw in norm_key(f["name"]):
            return f
    names = [f["name"] for f in folders]
    raise FileNotFoundError(
        f"Nenhuma subpasta contendo '{keyword}' encontrada ao lado da apostila. Pastas disponíveis: {names}"
    )


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------


def tool_list_courses(_args: Dict[str, Any]) -> Dict[str, Any]:
    return {"registry_path": COURSES_REGISTRY_PATH, "courses": load_courses_registry()}


def tool_read_lesson(args: Dict[str, Any]) -> Dict[str, Any]:
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])
    requested_tab = args.get("tab", "auto")
    save_local_md = bool(args.get("save_local_md", False))

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(
            f"O curso '{course_key}' não possui 'google_doc' configurado em {COURSES_REGISTRY_PATH}."
        )
    doc_id = extract_doc_id(doc_url)
    doc = fetch_doc(doc_id)

    tab, active_tab, rev_last, reason = resolve_active_tab(doc, lesson_num, requested_tab)
    elements = get_lesson_elements(tab, active_tab, lesson_num)
    lists_map = tab.get("documentTab", {}).get("lists", {})
    parsed = parse_lesson_structure(elements, lists_map)

    local_md_path = None
    if save_local_md and course_info.get("path"):
        local_md_path = resolve_local_lesson_md_path(
            course_info["path"], doc.get("title", course_key), lesson_num
        )
        with open(local_md_path, "w", encoding="utf-8") as f:
            f.write(parsed["markdown"])

    tab_id = tab["tabProperties"]["tabId"]
    return {
        "course": course_key,
        "doc_title": doc.get("title", ""),
        "doc_id": doc_id,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}",
        "lesson_num": lesson_num,
        "active_tab": active_tab,
        "revisada_last_lesson": rev_last,
        "resolution_reason": reason,
        "local_course_dir": course_info.get("path"),
        "canva_folder_id": course_info.get("canva_folder_id"),
        "canva_folder_path": course_info.get("canva_folder_path"),
        "local_md_path": local_md_path,
        **parsed,
    }


def tool_read_guidelines(args: Dict[str, Any]) -> Dict[str, Any]:
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(f"O curso '{course_key}' não possui 'google_doc' configurado.")
    apostila_id = extract_doc_id(doc_url)

    dir_folder = find_sibling_folder(apostila_id, "diretriz")
    docs = list_drive_children(dir_folder["id"], mime_type="application/vnd.google-apps.document")
    if not docs:
        raise FileNotFoundError(
            f"Nenhum Google Doc encontrado na pasta '{dir_folder['name']}'."
        )
    # Prefer doc whose name includes diretriz/ementa
    dir_file = next(
        (d for d in docs if "diretriz" in norm_key(d["name"]) or "ementa" in norm_key(d["name"])),
        docs[0],
    )
    dir_doc = fetch_doc(dir_file["id"])

    # If lesson_num == 0, read Ementa tab (or first tab)
    if lesson_num == 0:
        ementa_tab = get_tab_by_title(dir_doc, "Ementa") or dir_doc["tabs"][0]
        body = ementa_tab["documentTab"]["body"]["content"]
        paras = [paragraph_clean_text(el["paragraph"]) for el in body if "paragraph" in el]
        paras = [p for p in paras if p]
        return {
            "course": course_key,
            "lesson_num": 0,
            "doc_id": dir_file["id"],
            "doc_title": dir_doc.get("title", dir_file["name"]),
            "doc_url": f"https://docs.google.com/document/d/{dir_file['id']}/edit",
            "tab": ementa_tab["tabProperties"]["title"],
            "raw_text": "\n\n".join(paras),
        }

    dir_tab = get_tab_by_title(dir_doc, "Diretrizes") or dir_doc["tabs"][0]
    body = dir_tab["documentTab"]["body"]["content"]
    lessons = find_lessons_in_tab(dir_tab)
    target = next((x for x in lessons if x["lesson_num"] == lesson_num), None)
    if not target:
        avail = [x["lesson_num"] for x in lessons]
        raise ValueError(
            f"Diretrizes da Aula {lesson_num:02d} não encontradas em '{dir_doc.get('title')}'. Aulas encontradas: {avail}"
        )

    slice_els = body[target["body_idx"] : target["end_body_idx"]]
    direcao = ""
    versiculo_chave = ""
    introducao = ""
    topicos: List[Dict[str, str]] = []
    cur_topic_title: Optional[str] = None
    raw_lines: List[str] = []

    for el in slice_els:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        st = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        txt = paragraph_clean_text(p)
        if not txt:
            continue
        if st == "HEADING_1":
            raw_lines.append(f"# {txt}")
            continue
        if st == "HEADING_2":
            raw_lines.append(f"## {txt}")
            if norm_key(txt).startswith("versiculo-chave:") or norm_key(txt).startswith("versiculo chave:"):
                versiculo_chave = txt.split(":", 1)[1].strip().replace(":", ".")
                cur_topic_title = None
            else:
                cur_topic_title = txt
            continue

        raw_lines.append(txt)
        if cur_topic_title:
            # Append to existing topic if multiple paragraphs under same H2
            if topicos and topicos[-1]["title"] == cur_topic_title:
                topicos[-1]["guidelines"] += "\n\n" + txt
            else:
                topicos.append({"title": cur_topic_title, "guidelines": txt})
        elif not versiculo_chave and not direcao:
            direcao = txt
        elif versiculo_chave and not introducao:
            introducao = re.sub(r"^Introdu[çc][ãa]o:\s*", "", txt, flags=re.IGNORECASE)
        elif introducao:
            introducao += "\n\n" + txt

    return {
        "course": course_key,
        "lesson_num": lesson_num,
        "doc_id": dir_file["id"],
        "doc_title": dir_doc.get("title", dir_file["name"]),
        "doc_url": f"https://docs.google.com/document/d/{dir_file['id']}/edit?tab={dir_tab['tabProperties']['tabId']}",
        "tab": dir_tab["tabProperties"]["title"],
        "lesson_title": target["title"],
        "direcao": direcao,
        "versiculo_chave": versiculo_chave,
        "introducao": introducao,
        "topicos": topicos,
        "raw_text": "\n\n".join(raw_lines),
    }


def _collect_paragraph_run_map(p: Dict[str, Any]) -> Tuple[str, List[int]]:
    """
    Build the paragraph's textRun string AND a parallel list mapping each Python
    character index `i` to its exact UTF-16 document index in Google Docs.
    Non-textRun elements (like pageBreak) are skipped cleanly without shifting indices.
    """
    chars: List[str] = []
    doc_indices: List[int] = []
    for elem in p.get("elements", []):
        tr = elem.get("textRun")
        if not tr:
            continue
        content = tr.get("content", "")
        cur_u16 = elem.get("startIndex", 0)
        for ch in content:
            chars.append(ch)
            doc_indices.append(cur_u16)
            cur_u16 += utf16_len(ch)
    return "".join(chars), doc_indices


def tool_apply_lesson_edits(args: Dict[str, Any]) -> Dict[str, Any]:
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])
    replacements = args.get("replacements") or []
    requested_tab = args.get("tab", "auto")
    update_local_md = bool(args.get("update_local_md", False))

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(f"O curso '{course_key}' não possui 'google_doc' configurado.")
    doc_id = extract_doc_id(doc_url)
    doc = fetch_doc(doc_id)

    tab, active_tab, rev_last, reason = resolve_active_tab(doc, lesson_num, requested_tab)
    tab_id = tab["tabProperties"]["tabId"]
    elements = get_lesson_elements(tab, active_tab, lesson_num)

    edits: List[Tuple[int, int, str, str, int]] = []
    counts = {i: 0 for i in range(len(replacements))}

    for el in elements:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        raw_txt, idx_map = _collect_paragraph_run_map(p)
        if not raw_txt.strip():
            continue

        p_edits = []
        for idx_r, item in enumerate(replacements):
            old_t = item.get("old", "")
            new_t = item.get("new", "")
            if not old_t or old_t == new_t:
                continue
            pos = 0
            while True:
                found = raw_txt.find(old_t, pos)
                if found == -1:
                    break
                end_char = found + len(old_t) - 1
                abs_start = idx_map[found]
                abs_end = idx_map[end_char] + utf16_len(raw_txt[end_char])
                p_edits.append((abs_start, abs_end, old_t, new_t, idx_r))
                pos = found + len(old_t)

        # Avoid overlapping edits within the same paragraph
        p_edits.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        last_end = -1
        for ed in p_edits:
            if ed[0] >= last_end:
                edits.append(ed)
                last_end = ed[1]
                counts[ed[4]] += 1

    requests_payload: List[Dict[str, Any]] = []
    if edits:
        # Reverse order by startIndex so earlier indices stay valid
        edits.sort(key=lambda x: x[0], reverse=True)
        for abs_start, abs_end, _old_t, new_t, _idx_r in edits:
            new_u16 = utf16_len(new_t)
            # Insert at abs_start + 1 to inherit exact inline textStyle of first replaced char
            if abs_end > abs_start + 1 and new_u16 > 0:
                requests_payload.append(
                    {
                        "insertText": {
                            "location": {"index": abs_start + 1, "tabId": tab_id},
                            "text": new_t,
                        }
                    }
                )
                requests_payload.append(
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": abs_start + 1 + new_u16,
                                "endIndex": abs_end + new_u16,
                                "tabId": tab_id,
                            }
                        }
                    }
                )
                requests_payload.append(
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": abs_start,
                                "endIndex": abs_start + 1,
                                "tabId": tab_id,
                            }
                        }
                    }
                )
            else:
                if new_u16 > 0:
                    requests_payload.append(
                        {
                            "insertText": {
                                "location": {"index": abs_start, "tabId": tab_id},
                                "text": new_t,
                            }
                        }
                    )
                requests_payload.append(
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": abs_start + new_u16,
                                "endIndex": abs_end + new_u16,
                                "tabId": tab_id,
                            }
                        }
                    }
                )

        s = get_session()
        upd = s.post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            json={"requests": requests_payload},
        )
        if upd.status_code != 200:
            raise RuntimeError(
                f"Erro ao aplicar edições no Google Docs ({upd.status_code}): {upd.text}"
            )

    local_md_path = None
    if update_local_md and course_info.get("path"):
        fresh_doc = fetch_doc(doc_id)
        fresh_tab = get_tab_by_title(fresh_doc, active_tab)
        fresh_els = get_lesson_elements(fresh_tab, active_tab, lesson_num)
        fresh_lists = fresh_tab.get("documentTab", {}).get("lists", {})
        parsed = parse_lesson_structure(fresh_els, fresh_lists)
        local_md_path = resolve_local_lesson_md_path(
            course_info["path"], fresh_doc.get("title", course_key), lesson_num
        )
        with open(local_md_path, "w", encoding="utf-8") as f:
            f.write(parsed["markdown"])

    details = []
    unmatched = []
    for i, item in enumerate(replacements):
        c = counts[i]
        details.append({"old": item.get("old", ""), "new": item.get("new", ""), "occurrences": c})
        if c == 0:
            unmatched.append(item.get("old", ""))

    return {
        "status": "ok",
        "course": course_key,
        "lesson_num": lesson_num,
        "active_tab": active_tab,
        "resolution_reason": reason,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}",
        "total_occurrences_applied": sum(counts.values()),
        "unmatched_replacements": unmatched,
        "details": details,
        "local_md_path": local_md_path,
    }


def _build_rich_append_requests(
    src_elements: List[Dict[str, Any]],
    src_lists: Dict[str, Any],
    dest_tab_id: str,
    insert_index: int,
    prepend_page_break: bool = False,
    preserve_full_styles: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Build Google Docs batchUpdate requests to append rich paragraphs (headings,
    lists/bullets, bold/italic/underline/links, and optionally full paragraph/font
    formatting such as alignment, indentation, spacing, and fontSize) starting at
    `insert_index`.
    """
    reqs: List[Dict[str, Any]] = []
    cur = insert_index

    # Extract clean paragraph specs
    para_specs = []
    for el in src_elements:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        runs = []
        full_text_parts = []
        for elem in p.get("elements", []):
            tr = elem.get("textRun")
            if not tr:
                continue
            content = tr.get("content", "")
            if not content:
                continue
            ts = tr.get("textStyle", {})
            runs.append((content, ts))
            full_text_parts.append(content)
        full_text = "".join(full_text_parts)
        if not full_text:
            continue
        if not full_text.endswith("\n"):
            full_text += "\n"
            runs.append(("\n", {}))

        ps = p.get("paragraphStyle", {})
        named_style = ps.get("namedStyleType", "NORMAL_TEXT")
        bullet = p.get("bullet")
        list_preset = None
        list_id = None
        if bullet:
            list_id = bullet.get("listId", "")
            glyph = (
                src_lists.get(list_id, {})
                .get("listProperties", {})
                .get("nestingLevels", [{}])[0]
                .get("glyphType", "")
            )
            list_preset = (
                "NUMBERED_DECIMAL_ALPHA_ROMAN"
                if glyph == "DECIMAL"
                else "BULLET_DISC_CIRCLE_SQUARE"
            )

        para_specs.append(
            {
                "text": full_text,
                "runs": runs,
                "named_style": named_style,
                "paragraph_style": ps,
                "list_id": list_id,
                "list_preset": list_preset,
            }
        )

    # Drop leading/trailing empty paragraphs
    while para_specs and not para_specs[0]["text"].strip():
        para_specs.pop(0)
    while para_specs and not para_specs[-1]["text"].strip():
        para_specs.pop()

    if not para_specs:
        return [], cur

    # Insert full text in one insertText call so indices are 100% deterministic
    combined_text = "".join(sp["text"] for sp in para_specs)
    reqs.append(
        {
            "insertText": {
                "location": {"index": cur, "tabId": dest_tab_id},
                "text": combined_text,
            }
        }
    )

    p_override_keys = (
        "alignment",
        "direction",
        "spaceAbove",
        "spaceBelow",
        "lineSpacing",
        "spacingMode",
        "indentFirstLine",
        "indentStart",
        "indentEnd",
        "keepLinesTogether",
        "keepWithNext",
    )
    t_style_keys = (
        ("bold", "italic", "underline", "strikethrough", "link", "foregroundColor", "backgroundColor", "fontSize", "weightedFontFamily")
        if preserve_full_styles
        else ("bold", "italic", "underline", "strikethrough", "link", "foregroundColor")
    )

    # Track paragraph ranges for paragraph styles, inline text styles, and list grouping
    p_cursor = cur
    list_runs: List[Tuple[int, int, str]] = []  # (start, end, preset)
    cur_list_group = None  # (list_id, preset, start, end)

    for idx_p, sp in enumerate(para_specs):
        p_len = utf16_len(sp["text"])
        p_start = p_cursor
        p_end = p_cursor + p_len

        # 1. Apply namedStyleType first (resets defaults cleanly)
        p_style_obj: Dict[str, Any] = {"namedStyleType": sp["named_style"]}
        fields = ["namedStyleType"]
        if idx_p == 0 and prepend_page_break:
            p_style_obj["pageBreakBefore"] = True
            fields.append("pageBreakBefore")

        reqs.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": p_start,
                        "endIndex": p_end,
                        "tabId": dest_tab_id,
                    },
                    "paragraphStyle": p_style_obj,
                    "fields": ",".join(fields),
                }
            }
        )

        # 2. Apply explicit paragraph overrides (alignment, indents, spacing) when preserve_full_styles=True
        if preserve_full_styles:
            src_ps = sp["paragraph_style"]
            ov_obj: Dict[str, Any] = {}
            ov_fields: List[str] = []
            for key in p_override_keys:
                if key in src_ps:
                    # Skip indent overrides on list items (bullets manage their own indent)
                    if sp["list_id"] and key in ("indentFirstLine", "indentStart"):
                        continue
                    ov_obj[key] = src_ps[key]
                    ov_fields.append(key)
            if ov_fields:
                reqs.append(
                    {
                        "updateParagraphStyle": {
                            "range": {
                                "startIndex": p_start,
                                "endIndex": p_end,
                                "tabId": dest_tab_id,
                            },
                            "paragraphStyle": ov_obj,
                            "fields": ",".join(ov_fields),
                        }
                    }
                )

        # 3. Inline text styles
        r_cursor = p_start
        for content, ts in sp["runs"]:
            r_len = utf16_len(content)
            r_start = r_cursor
            r_end = r_cursor + r_len
            r_cursor = r_end
            if not content.strip():
                continue
            style_update: Dict[str, Any] = {}
            t_fields: List[str] = []
            for key in t_style_keys:
                if key in ts:
                    style_update[key] = ts[key]
                    t_fields.append(key)
            if t_fields:
                reqs.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": r_start,
                                "endIndex": r_end,
                                "tabId": dest_tab_id,
                            },
                            "textStyle": style_update,
                            "fields": ",".join(t_fields),
                        }
                    }
                )

        # 4. Group contiguous list items sharing the same list_id so numbering stays 1, 2, 3
        if sp["list_id"] and sp["list_preset"]:
            if cur_list_group and cur_list_group[0] == sp["list_id"]:
                cur_list_group = (
                    cur_list_group[0],
                    cur_list_group[1],
                    cur_list_group[2],
                    p_end,
                )
            else:
                if cur_list_group:
                    list_runs.append((cur_list_group[2], cur_list_group[3], cur_list_group[1]))
                cur_list_group = (sp["list_id"], sp["list_preset"], p_start, p_end)
        else:
            if cur_list_group:
                list_runs.append((cur_list_group[2], cur_list_group[3], cur_list_group[1]))
                cur_list_group = None

        p_cursor = p_end

    if cur_list_group:
        list_runs.append((cur_list_group[2], cur_list_group[3], cur_list_group[1]))

    for l_start, l_end, preset in list_runs:
        reqs.append(
            {
                "createParagraphBullets": {
                    "range": {
                        "startIndex": l_start,
                        "endIndex": l_end,
                        "tabId": dest_tab_id,
                    },
                    "bulletPreset": preset,
                }
            }
        )

    return reqs, p_cursor


def tool_promote_tmp_to_revisada(args: Dict[str, Any]) -> Dict[str, Any]:
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])
    clear_tmp = bool(args.get("clear_tmp", False))

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(f"O curso '{course_key}' não possui 'google_doc' configurado.")
    doc_id = extract_doc_id(doc_url)
    doc = fetch_doc(doc_id)

    tmp_tab = get_tab_by_title(doc, "Tmp")
    rev_tab = get_tab_by_title(doc, "Revisada")
    if not tmp_tab or not rev_tab:
        raise ValueError("Documento precisa possuir tanto a aba 'Tmp' quanto a aba 'Revisada'.")

    rev_lessons = find_lessons_in_tab(rev_tab)
    if any(x["lesson_num"] == lesson_num for x in rev_lessons):
        raise ValueError(
            f"ABORTADO: A Aula {lesson_num:02d} já existe na aba 'Revisada'. "
            "Para preservar comentários existentes, edite-a diretamente na aba 'Revisada' via apply_lesson_edits."
        )

    tmp_els = get_lesson_elements(tmp_tab, "Tmp", lesson_num)
    tmp_lists = tmp_tab.get("documentTab", {}).get("lists", {})

    rev_body = rev_tab["documentTab"]["body"]["content"]
    rev_end_index = rev_body[-1]["endIndex"]
    insert_at = max(1, rev_end_index - 1)
    rev_tab_id = rev_tab["tabProperties"]["tabId"]

    # Ensure previous paragraph ends with newline before pageBreakBefore
    needs_leading_nl = False
    if len(rev_body) > 1 and "paragraph" in rev_body[-1]:
        last_txt = paragraph_plain_text(rev_body[-1])
        if last_txt.strip():
            needs_leading_nl = True

    reqs: List[Dict[str, Any]] = []
    if needs_leading_nl:
        reqs.append(
            {"insertText": {"location": {"index": insert_at, "tabId": rev_tab_id}, "text": "\n"}}
        )
        insert_at += 1

    append_reqs, _ = _build_rich_append_requests(
        src_elements=tmp_els,
        src_lists=tmp_lists,
        dest_tab_id=rev_tab_id,
        insert_index=insert_at,
        prepend_page_break=bool(rev_lessons),
    )
    reqs.extend(append_reqs)

    if clear_tmp:
        tmp_body = tmp_tab["documentTab"]["body"]["content"]
        tmp_end = tmp_body[-1]["endIndex"]
        if tmp_end > 2:
            reqs.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": 1,
                            "endIndex": tmp_end - 1,
                            "tabId": tmp_tab["tabProperties"]["tabId"],
                        }
                    }
                }
            )

    s = get_session()
    upd = s.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": reqs},
    )
    if upd.status_code != 200:
        raise RuntimeError(f"Erro ao promover Tmp -> Revisada ({upd.status_code}): {upd.text}")

    return {
        "status": "ok",
        "course": course_key,
        "lesson_num": lesson_num,
        "promoted_to": "Revisada",
        "tmp_cleared": clear_tmp,
        "doc_url": f"https://docs.google.com/document/d/{doc_id}/edit?tab={rev_tab_id}",
    }


def _duplicate_file_via_apps_script(
    template_file_id: str, folder_id: str, new_name: str
) -> Dict[str, Any]:
    if not os.path.exists(APPS_SCRIPT_SECRET_PATH):
        raise RuntimeError(
            "Configuração do Google Apps Script não encontrada em "
            f"{APPS_SCRIPT_SECRET_PATH}. Siga o guia em "
            f"{os.path.join(SERVER_DIR, 'SETUP_APPS_SCRIPT.md')} para concluir a configuração única "
            "(leva ~2 minutos) ou informe 'target_doc_id' de um doc já copiado manualmente."
        )
    with open(APPS_SCRIPT_SECRET_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    webapp_url = (cfg.get("webapp_url") or "").strip()
    secret = (cfg.get("secret") or "").strip()
    if not webapp_url or not secret or "COLE_AQUI" in webapp_url:
        raise RuntimeError(
            f"Preencha 'webapp_url' e 'secret' válidos em {APPS_SCRIPT_SECRET_PATH}."
        )

    resp = requests.post(
        webapp_url,
        json={
            "secret": secret,
            "action": "copy_file",
            "templateFileId": template_file_id,
            "folderId": folder_id,
            "newName": new_name,
        },
        timeout=30,
        allow_redirects=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro ao chamar Apps Script Web App ({resp.status_code}): {resp.text[:400]}"
        )
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"Resposta inválida (não-JSON) do Apps Script Web App: {resp.text[:400]}"
        ) from exc

    if not data.get("ok"):
        raise RuntimeError(f"Apps Script retornou erro: {data.get('error', data)}")
    return data


def _extract_closing_sections_from_apostila(
    elements: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract verbatim elements for 'Ideia Central', 'Perguntas para reflexão',
    and 'Tarefas de casa' (explicitly skipping 'Perguntas para discussão').
    """
    keep_keys = {"ideia_central", "perguntas_reflexao", "tarefas_de_casa"}
    out: List[Dict[str, Any]] = []
    capturing = False
    for el in elements:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        st = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        clean = paragraph_clean_text(p)
        if st == "HEADING_2":
            sec = classify_special_section(clean)
            capturing = sec in keep_keys
        if capturing:
            out.append(el)
    return out


def _populate_teleprompter_tab(
    s: AuthorizedSession,
    doc_id: str,
    tab: Dict[str, Any],
    title: str,
    paragraphs: List[str],
    closing_els: Optional[List[Dict[str, Any]]] = None,
    src_lists: Optional[Dict[str, Any]] = None,
    preserve_existing_title_style: bool = True,
) -> None:
    """Clear a teleprompter tab, write HEADING_1 title + NORMAL_TEXT paragraphs (+ optional closing sections)."""
    tab_id = tab["tabProperties"]["tabId"]
    body = tab["documentTab"]["body"]["content"]
    first_para = next((el for el in body if "paragraph" in el), None)
    if not first_para:
        raise RuntimeError(f"Aba '{tab['tabProperties'].get('title')}' sem parágrafo inicial.")

    title_start = first_para["startIndex"]
    title_end = first_para["endIndex"]
    doc_end = body[-1]["endIndex"]

    prep_reqs: List[Dict[str, Any]] = []
    if doc_end - 1 > title_end:
        prep_reqs.append(
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": title_end,
                        "endIndex": doc_end - 1,
                        "tabId": tab_id,
                    }
                }
            }
        )

    old_title_len = (title_end - 1) - title_start
    title_u16 = utf16_len(title)
    if preserve_existing_title_style and old_title_len >= 1:
        prep_reqs.append(
            {
                "insertText": {
                    "location": {"index": title_start + 1, "tabId": tab_id},
                    "text": title,
                }
            }
        )
        if old_title_len > 1:
            prep_reqs.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": title_start + 1 + title_u16,
                            "endIndex": title_start + old_title_len + title_u16,
                            "tabId": tab_id,
                        }
                    }
                }
            )
        prep_reqs.append(
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": title_start,
                        "endIndex": title_start + 1,
                        "tabId": tab_id,
                    }
                }
            }
        )
    else:
        if old_title_len > 0:
            prep_reqs.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": title_start,
                            "endIndex": title_end - 1,
                            "tabId": tab_id,
                        }
                    }
                }
            )
        prep_reqs.append(
            {
                "insertText": {
                    "location": {"index": title_start, "tabId": tab_id},
                    "text": title,
                }
            }
        )
        prep_reqs.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": title_start,
                        "endIndex": title_start + title_u16 + 1,
                        "tabId": tab_id,
                    },
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            }
        )

    r1 = s.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": prep_reqs},
    )
    if r1.status_code != 200:
        raise RuntimeError(
            f"Erro ao preparar título/corpo da aba '{tab['tabProperties'].get('title')}' ({r1.status_code}): {r1.text}"
        )

    # Re-fetch exact endIndex after title update, then insert body (+ optional closing sections)
    doc2 = fetch_doc(doc_id)
    fresh_tab = next(
        (t for t in doc2.get("tabs", []) if t["tabProperties"]["tabId"] == tab_id), None
    )
    if not fresh_tab:
        raise RuntimeError(f"Aba {tab_id} não encontrada após atualização do título.")
    body2 = fresh_tab["documentTab"]["body"]["content"]
    insert_at = max(1, body2[-1]["endIndex"] - 1)

    body_lines = ["", *[p.rstrip("\n") for p in paragraphs], "", ""]
    tp_text = "\n".join(body_lines) + "\n"
    tp_u16 = utf16_len(tp_text)

    fill_reqs: List[Dict[str, Any]] = [
        {
            "insertText": {
                "location": {"index": insert_at, "tabId": tab_id},
                "text": tp_text,
            }
        },
        {
            "updateParagraphStyle": {
                "range": {
                    "startIndex": insert_at,
                    "endIndex": insert_at + tp_u16,
                    "tabId": tab_id,
                },
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                "fields": "namedStyleType",
            }
        },
        {
            "updateTextStyle": {
                "range": {
                    "startIndex": insert_at,
                    "endIndex": insert_at + tp_u16,
                    "tabId": tab_id,
                },
                "textStyle": {"bold": False, "italic": False},
                "fields": "bold,italic",
            }
        },
    ]

    if closing_els:
        closing_reqs, _ = _build_rich_append_requests(
            src_elements=closing_els,
            src_lists=src_lists or {},
            dest_tab_id=tab_id,
            insert_index=insert_at + tp_u16,
            prepend_page_break=False,
        )
        fill_reqs.extend(closing_reqs)

    r2 = s.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": fill_reqs},
    )
    if r2.status_code != 200:
        raise RuntimeError(
            f"Erro ao preencher corpo da aba '{tab['tabProperties'].get('title')}' ({r2.status_code}): {r2.text}"
        )


def tool_publish_teleprompter(args: Dict[str, Any]) -> Dict[str, Any]:
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])
    title = (args.get("title") or "").strip()
    teleprompter_paragraphs = args.get("teleprompter_paragraphs") or []
    original_paragraphs = args.get("original_paragraphs") or []
    source_tab_req = args.get("source_tab", "auto")
    target_doc_id = (args.get("target_doc_id") or "").strip()

    if not teleprompter_paragraphs:
        raise ValueError("'teleprompter_paragraphs' não pode ser vazio.")

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(f"O curso '{course_key}' não possui 'google_doc' configurado.")
    apostila_id = extract_doc_id(doc_url)

    # 1. Read Apostila source tab to extract title (fallback) and closing sections
    apostila_doc = fetch_doc(apostila_id)
    src_tab, active_tab, _rev_last, reason = resolve_active_tab(
        apostila_doc, lesson_num, source_tab_req
    )
    src_els = get_lesson_elements(src_tab, active_tab, lesson_num)
    src_lists = src_tab.get("documentTab", {}).get("lists", {})
    closing_els = _extract_closing_sections_from_apostila(src_els)

    if not title:
        parsed_src = parse_lesson_structure(src_els, src_lists)
        title = parsed_src["title_full"]

    # 2. Locate sibling Teleprompter folder & determine target doc
    tp_folder = find_sibling_folder(apostila_id, "teleprompter")
    tp_docs = list_drive_children(
        tp_folder["id"], mime_type="application/vnd.google-apps.document"
    )

    created_new = False
    doc_name = ""

    if target_doc_id:
        tp_doc_id = extract_doc_id(target_doc_id)
    else:
        indexed_docs = []
        existing_match = None
        for d in tp_docs:
            m = re.search(r"Aula\s+0*(\d+)\b", d["name"], re.IGNORECASE)
            if m:
                n = int(m.group(1))
                indexed_docs.append((n, d))
                if n == lesson_num:
                    existing_match = d

        if existing_match:
            tp_doc_id = existing_match["id"]
            doc_name = existing_match["name"]
        else:
            if not indexed_docs:
                raise FileNotFoundError(
                    f"Nenhum arquivo de teleprompter no padrão 'Aula NN' encontrado em '{tp_folder['name']}'."
                )
            indexed_docs.sort(key=lambda x: x[0], reverse=True)
            _highest_num, template_doc = indexed_docs[0]
            new_name = re.sub(
                r"(Aula\s+)0*\d+\b",
                lambda m: f"{m.group(1)}{lesson_num:02d}",
                template_doc["name"],
                count=1,
                flags=re.IGNORECASE,
            )
            copy_res = _duplicate_file_via_apps_script(
                template_file_id=template_doc["id"],
                folder_id=tp_folder["id"],
                new_name=new_name,
            )
            tp_doc_id = copy_res["id"]
            doc_name = copy_res.get("name", new_name)
            created_new = True

    # 3. Ensure tabs exist with canonical names & emojis:
    #    Tab 0: "Revisada" ("✅") -> reduced teleprompter + closing sections
    #    Tab 1: "Original" ("✍🏽") -> long/full teleprompter (when original_paragraphs provided)
    s = get_session()
    tp_doc = fetch_doc(tp_doc_id)
    doc_name = doc_name or tp_doc.get("title", "")

    rev_tab = get_tab_by_title(tp_doc, "Revisada") or tp_doc["tabs"][0]
    rev_tab_id = rev_tab["tabProperties"]["tabId"]
    orig_tab = get_tab_by_title(tp_doc, "Original")

    tab_meta_reqs: List[Dict[str, Any]] = []
    rev_props = rev_tab.get("tabProperties", {})
    if rev_props.get("title") != "Revisada" or rev_props.get("iconEmoji") != "✅":
        tab_meta_reqs.append(
            {
                "updateDocumentTabProperties": {
                    "tabProperties": {
                        "tabId": rev_tab_id,
                        "title": "Revisada",
                        "iconEmoji": "✅",
                    },
                    "fields": "title,iconEmoji",
                }
            }
        )

    added_orig_tab = False
    if original_paragraphs:
        if orig_tab is None:
            tab_meta_reqs.append(
                {
                    "addDocumentTab": {
                        "tabProperties": {
                            "title": "Original",
                            "iconEmoji": "✍🏽",
                            "index": 1,
                        }
                    }
                }
            )
            added_orig_tab = True
        else:
            orig_props = orig_tab.get("tabProperties", {})
            if orig_props.get("title") != "Original" or orig_props.get("iconEmoji") != "✍🏽":
                tab_meta_reqs.append(
                    {
                        "updateDocumentTabProperties": {
                            "tabProperties": {
                                "tabId": orig_props["tabId"],
                                "title": "Original",
                                "iconEmoji": "✍🏽",
                            },
                            "fields": "title,iconEmoji",
                        }
                    }
                )

    if tab_meta_reqs:
        r_meta = s.post(
            f"https://docs.googleapis.com/v1/documents/{tp_doc_id}:batchUpdate",
            json={"requests": tab_meta_reqs},
        )
        if r_meta.status_code != 200:
            raise RuntimeError(
                f"Erro ao configurar abas Revisada/Original no Teleprompter ({r_meta.status_code}): {r_meta.text}"
            )
        tp_doc = fetch_doc(tp_doc_id)
        rev_tab = get_tab_by_title(tp_doc, "Revisada") or tp_doc["tabs"][0]
        rev_tab_id = rev_tab["tabProperties"]["tabId"]
        orig_tab = get_tab_by_title(tp_doc, "Original")

    # 4. Populate Revisada tab (reduced version + Ideia Central / Reflexão / Tarefas)
    _populate_teleprompter_tab(
        s=s,
        doc_id=tp_doc_id,
        tab=rev_tab,
        title=title,
        paragraphs=teleprompter_paragraphs,
        closing_els=closing_els,
        src_lists=src_lists,
        preserve_existing_title_style=True,
    )

    # 5. Populate Original tab (long version) when provided
    orig_tab_id = None
    if original_paragraphs and orig_tab is not None:
        orig_tab_id = orig_tab["tabProperties"]["tabId"]
        # Re-fetch fresh orig_tab before writing
        tp_doc_fresh = fetch_doc(tp_doc_id)
        orig_tab_fresh = next(
            (t for t in tp_doc_fresh.get("tabs", []) if t["tabProperties"]["tabId"] == orig_tab_id),
            orig_tab,
        )
        _populate_teleprompter_tab(
            s=s,
            doc_id=tp_doc_id,
            tab=orig_tab_fresh,
            title=title,
            paragraphs=original_paragraphs,
            closing_els=None,
            src_lists=None,
            preserve_existing_title_style=not added_orig_tab,
        )

    return {
        "status": "ok",
        "course": course_key,
        "lesson_num": lesson_num,
        "source_tab": active_tab,
        "source_resolution_reason": reason,
        "created_new": created_new,
        "doc_id": tp_doc_id,
        "doc_title": doc_name,
        "doc_url": f"https://docs.google.com/document/d/{tp_doc_id}/edit?tab={rev_tab_id}",
        "revisada_tab_url": f"https://docs.google.com/document/d/{tp_doc_id}/edit?tab={rev_tab_id}",
        "original_tab_url": (
            f"https://docs.google.com/document/d/{tp_doc_id}/edit?tab={orig_tab_id}"
            if orig_tab_id
            else None
        ),
        "revisada_paragraphs_count": len(teleprompter_paragraphs),
        "original_paragraphs_count": len(original_paragraphs),
        "closing_sections_copied": bool(closing_els),
    }


def tool_export_lesson_pdf(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finaliza uma aula revisada em 4 passos atômicos:
      1. Limpa todo o conteúdo da aba 'Tmp';
      2. Copia a aula da aba 'Revisada' para a aba 'Tmp' preservando TODA a formatação;
      3. Exporta a aba 'Tmp' como PDF para /mnt/c/Users/lplim/Downloads;
      4. Carrega/atualiza o PDF na pasta irmã 'Aulas em PDF' do Google Drive com validação MD5.
    """
    course_key, course_info = resolve_course(args["course"])
    lesson_num = int(args["lesson_num"])
    downloads_dir = args.get("downloads_dir") or DOWNLOADS_DIR

    doc_url = course_info.get("google_doc")
    if not doc_url:
        raise ValueError(f"O curso '{course_key}' não possui 'google_doc' configurado.")
    doc_id = extract_doc_id(doc_url)
    doc = fetch_doc(doc_id)

    rev_tab = get_tab_by_title(doc, "Revisada")
    tmp_tab = get_tab_by_title(doc, "Tmp")
    if not rev_tab or not tmp_tab:
        raise ValueError("Documento precisa possuir tanto a aba 'Revisada' quanto a aba 'Tmp'.")

    rev_els = get_lesson_elements(rev_tab, "Revisada", lesson_num)
    rev_lists = rev_tab.get("documentTab", {}).get("lists", {})

    tmp_tab_id = tmp_tab["tabProperties"]["tabId"]
    tmp_body = tmp_tab["documentTab"]["body"]["content"]
    tmp_end = tmp_body[-1]["endIndex"]

    s = get_session()

    # Step 1: Clear Tmp tab completely (content + any residual bullets/styles)
    clear_reqs: List[Dict[str, Any]] = []
    if tmp_end > 2:
        clear_reqs.append(
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": tmp_end - 1,
                        "tabId": tmp_tab_id,
                    }
                }
            }
        )
    clear_reqs.append(
        {
            "deleteParagraphBullets": {
                "range": {"startIndex": 1, "endIndex": 2, "tabId": tmp_tab_id}
            }
        }
    )
    clear_reqs.append(
        {
            "updateParagraphStyle": {
                "range": {"startIndex": 1, "endIndex": 2, "tabId": tmp_tab_id},
                "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                "fields": "namedStyleType",
            }
        }
    )
    r_clear = s.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": clear_reqs},
    )
    if r_clear.status_code != 200:
        raise RuntimeError(f"Erro ao limpar aba 'Tmp' ({r_clear.status_code}): {r_clear.text}")

    # Step 2: Copy full lesson from Revisada -> Tmp preserving ALL formatting
    copy_reqs, _ = _build_rich_append_requests(
        src_elements=rev_els,
        src_lists=rev_lists,
        dest_tab_id=tmp_tab_id,
        insert_index=1,
        prepend_page_break=False,
        preserve_full_styles=True,
    )
    if not copy_reqs:
        raise RuntimeError(f"Nenhum conteúdo encontrado na Aula {lesson_num:02d} da aba 'Revisada'.")

    r_copy = s.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": copy_reqs},
    )
    if r_copy.status_code != 200:
        raise RuntimeError(
            f"Erro ao copiar Aula {lesson_num:02d} para a aba 'Tmp' ({r_copy.status_code}): {r_copy.text}"
        )

    # Step 3: Export Tmp tab as PDF to Downloads folder
    pdf_folder = find_sibling_folder(doc_id, "pdf")
    existing_pdfs = list_drive_children(pdf_folder["id"], mime_type="application/pdf")

    # Derive canonical PDF filename matching existing files in Aulas em PDF (or Apostila title)
    suffix = None
    for f in existing_pdfs:
        m_suf = re.match(r"^Aula\s+\d+\s*(-\s*.+?\.pdf)$", f["name"], re.IGNORECASE)
        if m_suf:
            suffix = m_suf.group(1)
            break
    if not suffix:
        clean_course = re.sub(
            r"^Apostila\s*[-–:]\s*", "", doc.get("title", course_key), flags=re.IGNORECASE
        ).strip()
        suffix = f"- {clean_course}.pdf"
    pdf_filename = f"Aula {lesson_num:02d} {suffix}"

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf&tab={tmp_tab_id}"
    exp_resp = s.get(export_url)
    if exp_resp.status_code != 200 or not exp_resp.content.startswith(b"%PDF"):
        raise RuntimeError(
            f"Erro ao exportar aba 'Tmp' como PDF ({exp_resp.status_code}, "
            f"Content-Type={exp_resp.headers.get('Content-Type')}): {exp_resp.text[:300]}"
        )

    pdf_bytes = exp_resp.content
    local_md5 = hashlib.md5(pdf_bytes).hexdigest()
    est_pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

    os.makedirs(downloads_dir, exist_ok=True)
    local_pdf_path = os.path.join(downloads_dir, pdf_filename)
    with open(local_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    # Step 4: Upload (or update in-place) PDF in Drive folder 'Aulas em PDF'
    existing_target = next(
        (
            f
            for f in existing_pdfs
            if norm_key(f["name"]) == norm_key(pdf_filename)
            or re.match(rf"^Aula\s+0*{lesson_num}\b", f["name"], re.IGNORECASE)
        ),
        None,
    )

    updated_existing = False
    created_temp_id = None

    if existing_target:
        target_file_id = existing_target["id"]
        updated_existing = True
    else:
        if not existing_pdfs:
            raise RuntimeError(
                f"A pasta '{pdf_folder['name']}' no Drive não possui nenhum PDF modelo para duplicar via Apps Script. "
                f"O PDF já foi salvo em {local_pdf_path}; suba o primeiro PDF do curso manualmente uma única vez."
            )
        # Pick highest-index existing PDF as template slot owned by personal account
        existing_pdfs_sorted = sorted(existing_pdfs, key=lambda x: x["name"], reverse=True)
        template_pdf = existing_pdfs_sorted[0]
        copy_res = _duplicate_file_via_apps_script(
            template_file_id=template_pdf["id"],
            folder_id=pdf_folder["id"],
            new_name=pdf_filename,
        )
        target_file_id = copy_res["id"]
        created_temp_id = target_file_id

    patch_resp = s.patch(
        f"https://www.googleapis.com/upload/drive/v3/files/{target_file_id}"
        "?uploadType=media&fields=id,name,size,md5Checksum,webViewLink",
        headers={"Content-Type": "application/pdf"},
        data=pdf_bytes,
    )
    if patch_resp.status_code != 200:
        if created_temp_id:
            s.patch(
                f"https://www.googleapis.com/drive/v3/files/{created_temp_id}",
                json={"trashed": True},
            )
        raise RuntimeError(
            f"Erro ao gravar bytes do PDF no Drive ({patch_resp.status_code}): {patch_resp.text}"
        )

    meta = patch_resp.json()
    if int(meta.get("size", -1)) != len(pdf_bytes) or meta.get("md5Checksum") != local_md5:
        raise RuntimeError(
            f"Falha de integridade no upload do PDF: esperado size={len(pdf_bytes)} md5={local_md5}, "
            f"recebido {meta}"
        )

    return {
        "status": "ok",
        "course": course_key,
        "lesson_num": lesson_num,
        "pdf_filename": pdf_filename,
        "local_pdf_path": local_pdf_path,
        "bytes": len(pdf_bytes),
        "estimated_pages": est_pages,
        "md5": local_md5,
        "updated_existing": updated_existing,
        "drive_file_id": meta["id"],
        "drive_file_url": meta.get("webViewLink") or f"https://drive.google.com/file/d/{meta['id']}/view",
        "drive_folder_name": pdf_folder["name"],
        "drive_folder_url": f"https://drive.google.com/drive/folders/{pdf_folder['id']}",
        "tmp_tab_url": f"https://docs.google.com/document/d/{doc_id}/edit?tab={tmp_tab_id}",
    }


# ---------------------------------------------------------------------------
# MCP Schema & JSON-RPC 2.0 Stdio Loop
# ---------------------------------------------------------------------------

TOOLS_SCHEMA = [
    {
        "name": "list_courses",
        "description": "Lista todos os cursos cadastrados em cursos_registrados.json com seus caminhos locais, links do Google Docs e IDs de pastas do Canva.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "read_lesson",
        "description": (
            "Lê uma aula diretamente do Google Docs da apostila do curso. "
            "Com tab='auto' (padrão), verifica se a aula já está na aba 'Revisada' (ex.: casa com a última aula lá) "
            "para preservar comentários; caso contrário, lê da aba 'Tmp'. "
            "Retorna JSON estruturado com título, versículo-chave, introdução, tópicos (parágrafos lógicos limpos), "
            "Ideia Central, Perguntas para reflexão/discussão, Tarefas de casa e Markdown reconstruído. "
            "Se save_local_md=true, salva automaticamente o checkpoint .md local no repositório revisao_ebd."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso (ex.: 'filipenses', 'profetas menores', 'jornada batista')."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula (ex.: 0, 6, 7)."},
                "tab": {"type": "string", "description": "'auto' (padrão), 'Revisada' ou 'Tmp'.", "default": "auto"},
                "save_local_md": {"type": "boolean", "description": "Se true, salva/atualiza o checkpoint .md local da aula.", "default": False},
            },
            "required": ["course", "lesson_num"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_guidelines",
        "description": (
            "Lê as Diretrizes (ou Ementa, se lesson_num=0) de uma aula diretamente do Google Doc na pasta irmã "
            "'Ementa(s) e diretrizes' no Google Drive do curso."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula (0 para Ementa geral)."},
            },
            "required": ["course", "lesson_num"],
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_lesson_edits",
        "description": (
            "Aplica correções mecânicas diretamente na aba ativa ('Revisada' ou 'Tmp') do Google Doc da apostila, "
            "preservando 100% da formatação inline e comentários. Atualiza opcionalmente o arquivo .md checkpoint local."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula."},
                "tab": {"type": "string", "description": "'auto' (padrão), 'Revisada' ou 'Tmp'.", "default": "auto"},
                "update_local_md": {"type": "boolean", "description": "Se true, atualiza o .md local após editar o Google Doc. Padrão: false.", "default": False},
                "replacements": {
                    "type": "array",
                    "description": "Lista de substituições exatas de texto a aplicar apenas dentro do intervalo desta aula.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["old", "new"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["course", "lesson_num", "replacements"],
            "additionalProperties": False,
        },
    },
    {
        "name": "promote_tmp_to_revisada",
        "description": (
            "Copia a aula finalizada da aba 'Tmp' para o final da aba 'Revisada' (com quebra de página e preservando "
            "HEADING_1, HEADING_2, listas numeradas, negrito, itálico e links). "
            "DEVE ser chamada somente após aprovação explícita do usuário. Aborta se a aula já existir na 'Revisada'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula."},
                "clear_tmp": {"type": "boolean", "description": "Se true, limpa a aba 'Tmp' após copiar. Padrão: false.", "default": False},
            },
            "required": ["course", "lesson_num"],
            "additionalProperties": False,
        },
    },
    {
        "name": "publish_teleprompter",
        "description": (
            "Cria (duplicando o arquivo de maior índice na pasta irmã 'Textos para teleprompter' via Apps Script) ou atualiza "
            "o Google Doc de teleprompter da aula com duas abas padronizadas: "
            "(1) primeira aba 'Revisada' (emoji ✅) com a versão reduzida final + 'Ideia Central', 'Perguntas para reflexão' e "
            "'Tarefas de casa' copiados integralmente da apostila; "
            "(2) segunda aba 'Original' (emoji ✍🏽) com a versão longa/completa (quando original_paragraphs for informado)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula."},
                "title": {"type": "string", "description": "Título da aula (HEADING_1) a gravar no topo. Se omitido, usa o da apostila."},
                "teleprompter_paragraphs": {
                    "type": "array",
                    "description": "Lista ordenada de parágrafos da versão REDUZIDA (Etapa 2) para a 1ª aba 'Revisada' (✅).",
                    "items": {"type": "string"},
                },
                "original_paragraphs": {
                    "type": "array",
                    "description": "Lista ordenada de parágrafos da versão LONGA/COMPLETA (Etapa 1) para a 2ª aba 'Original' (✍🏽).",
                    "items": {"type": "string"},
                },
                "source_tab": {"type": "string", "description": "'auto' (padrão), 'Revisada' ou 'Tmp' para buscar Ideia Central/Reflexão/Tarefas.", "default": "auto"},
                "target_doc_id": {"type": "string", "description": "Opcional: URL ou ID de um Doc de teleprompter já existente para atualizar diretamente."},
            },
            "required": ["course", "lesson_num", "teleprompter_paragraphs"],
            "additionalProperties": False,
        },
    },
    {
        "name": "export_lesson_pdf",
        "description": (
            "Finaliza e publica o PDF de uma aula revisada em 1 única chamada (sem prompts): "
            "(1) limpa todo o conteúdo da aba 'Tmp'; "
            "(2) copia a aula completa da aba 'Revisada' para a aba 'Tmp' preservando 100% da formatação; "
            "(3) baixa a aba 'Tmp' como PDF para /mnt/c/Users/lplim/Downloads; "
            "(4) carrega/atualiza o PDF na pasta 'Aulas em PDF' do curso no Google Drive com verificação MD5."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "course": {"type": "string", "description": "Nome do curso (ex.: 'jornada batista', 'filipenses', 'profetas menores')."},
                "lesson_num": {"type": "integer", "description": "Número inteiro da aula a exportar (ex.: 7)."},
                "downloads_dir": {"type": "string", "description": "Opcional: pasta local de destino do PDF (padrão: /mnt/c/Users/lplim/Downloads)."},
            },
            "required": ["course", "lesson_num"],
            "additionalProperties": False,
        },
    },
]

TOOL_HANDLERS = {
    "list_courses": tool_list_courses,
    "read_lesson": tool_read_lesson,
    "read_guidelines": tool_read_guidelines,
    "apply_lesson_edits": tool_apply_lesson_edits,
    "promote_tmp_to_revisada": tool_promote_tmp_to_revisada,
    "publish_teleprompter": tool_publish_teleprompter,
    "export_lesson_pdf": tool_export_lesson_pdf,
}


def send_response(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle_message(msg: Dict[str, Any]) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications have no id and expect no response
    if req_id is None:
        return

    if method == "initialize":
        proto = params.get("protocolVersion") or "2024-11-05"
        send_response(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": proto,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "ebd-google", "version": "1.0.0"},
                },
            }
        )
        return

    if method == "ping":
        send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return

    if method == "tools/list":
        send_response({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_SCHEMA}})
        return

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            send_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Ferramenta desconhecida: {tool_name}"}],
                        "isError": True,
                    },
                }
            )
            return
        try:
            result = handler(tool_args)
            send_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}
                        ],
                        "isError": False,
                    },
                }
            )
        except Exception as exc:
            send_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Erro em {tool_name}: {exc}"}],
                        "isError": True,
                    },
                }
            )
        return

    send_response(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"[ebd-google] JSON inválido: {exc}\n")
            sys.stderr.flush()
            continue
        handle_message(msg)


if __name__ == "__main__":
    main()
