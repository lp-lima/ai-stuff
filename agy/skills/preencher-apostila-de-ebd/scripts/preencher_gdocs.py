import argparse
import json
import os
import re
import sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_PATH = "/home/lp-lima/.gemini/skills/import-nubank-expenses/assets/credentials.json"


def extract_doc_id_and_tab(url_or_id):
    if not url_or_id:
        return "", None
    m_doc = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url_or_id)
    doc_id = m_doc.group(1) if m_doc else url_or_id.strip()
    m_tab = re.search(r"[?&]tab=([a-zA-Z0-9._-]+)", url_or_id)
    tab_id = m_tab.group(1) if m_tab else None
    return doc_id, tab_id


def resolve_tab(doc, tab_id=None, tab_title=None):
    tabs = doc.get("tabs", [])
    if tab_title:
        for t in tabs:
            if t.get("tabProperties", {}).get("title", "").strip().lower() == tab_title.strip().lower():
                return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    if tab_id:
        for t in tabs:
            if t.get("tabProperties", {}).get("tabId") == tab_id:
                return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    if tabs:
        t = tabs[0]
        return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    raise ValueError(f"Nenhuma aba encontrada no documento {doc.get('title')}")


def extract_text_and_links(p):
    raw_parts = []
    links = []
    pos = 0
    for e in p.get("elements", []):
        tr = e.get("textRun", {})
        content = tr.get("content", "")
        if not content:
            continue
        style = tr.get("textStyle", {})
        if "link" in style:
            links.append({
                "start": pos,
                "end": pos + len(content),
                "link": style["link"],
                "foregroundColor": style.get("foregroundColor"),
                "underline": style.get("underline", True),
            })
        raw_parts.append(content)
        pos += len(content)

    full_raw = "".join(raw_parts)
    leading_ws = len(full_raw) - len(full_raw.lstrip())
    stripped = full_raw.strip()
    adjusted_links = []
    for lk in links:
        ns = max(0, lk["start"] - leading_ws)
        ne = min(len(stripped), lk["end"] - leading_ws)
        if ne > ns:
            adjusted_links.append({
                "start": ns,
                "end": ne,
                "link": lk["link"],
                "foregroundColor": lk["foregroundColor"],
                "underline": lk["underline"],
            })
    return stripped, adjusted_links


def shift_links(links, offset):
    return [
        {
            **lk,
            "start": lk["start"] + offset,
            "end": lk["end"] + offset,
        }
        for lk in links
    ]


def parse_diretrizes(dir_body):
    aulas = {}
    current_num = None
    current_topico_title = None
    current_topico_title_links = []

    for el in dir_body:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text, links = extract_text_and_links(p)
        if not text:
            continue

        if style == "HEADING_1":
            m = re.match(r"Aula\s+0?(\d+)\s*[–:-]\s*(.*)", text, re.IGNORECASE)
            if m:
                current_num = int(m.group(1))
                aulas[current_num] = {
                    "title": m.group(2).strip(),
                    "direcao": "",
                    "direcao_links": [],
                    "ref": "",
                    "intro": "",
                    "intro_links": [],
                    "topicos": []
                }
                current_topico_title = None
                current_topico_title_links = []
            else:
                current_num = None
            continue

        if current_num is None:
            continue

        data = aulas[current_num]
        if style == "HEADING_2":
            if text.lower().startswith("versículo-chave:"):
                ref_raw = text.split(":", 1)[1].strip()
                # Garantir separador "." em vez de ":" entre capítulo e versículo
                data["ref"] = ref_raw.replace(":", ".")
            else:
                current_topico_title = text
                current_topico_title_links = links
        elif style == "NORMAL_TEXT":
            if not data["ref"] and not data["direcao"]:
                data["direcao"] = text
                data["direcao_links"] = links
            elif data["ref"] and not data["intro"]:
                m_intro = re.match(r"^Introdução:\s*", text, flags=re.IGNORECASE)
                if m_intro:
                    cut = m_intro.end()
                    data["intro"] = text[cut:]
                    data["intro_links"] = [
                        {**lk, "start": max(0, lk["start"] - cut), "end": lk["end"] - cut}
                        for lk in links
                        if lk["end"] > cut
                    ]
                else:
                    data["intro"] = text
                    data["intro_links"] = links
            elif current_topico_title:
                data["topicos"].append({
                    "title": current_topico_title,
                    "title_links": current_topico_title_links,
                    "body": text,
                    "body_links": links,
                })
                current_topico_title = None
                current_topico_title_links = []

    return aulas


def collect_replacements(orig_body, target_aulas, diretrizes_aulas, nvi_verses):
    replacements = []
    current_num = None
    topico_idx = 0

    for i, el in enumerate(orig_body):
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        p_start = el["startIndex"]
        p_end = el["endIndex"]
        full_text = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        stripped = full_text.strip()
        if not stripped:
            continue

        if style == "HEADING_1":
            m = re.match(r"(Aula\s+0?(\d+)\s*:\s*)(.*)", stripped, re.IGNORECASE)
            if m:
                num = int(m.group(2))
                if num in target_aulas and num in diretrizes_aulas:
                    current_num = num
                    topico_idx = 0
                    prefix = m.group(1)
                    old_title = m.group(3)
                    if old_title != diretrizes_aulas[num]["title"]:
                        s = p_start + len(prefix)
                        e = s + len(old_title)
                        replacements.append((s, e, old_title, diretrizes_aulas[num]["title"], f"Aula {num:02d} - Título da aula", []))
                else:
                    current_num = None
            else:
                current_num = None
            continue

        if current_num is None:
            continue

        aula_data = diretrizes_aulas[current_num]
        verse_text = nvi_verses.get(str(current_num), "")

        # 2. Versículo-chave e Referência sob o título
        if "conteúdo do versículo na versão nvi" in stripped.lower():
            for elem in p.get("elements", []):
                run_content = elem.get("textRun", {}).get("content", "")
                r_start = elem.get("startIndex", 0)
                idx_v = run_content.find("conteúdo do versículo na versão NVI")
                if idx_v != -1:
                    target_str = "conteúdo do versículo na versão NVI"
                    s = r_start + idx_v
                    e = s + len(target_str)
                    replacements.append((s, e, target_str, verse_text, f"Aula {current_num:02d} - Texto do versículo (NVI 2011)", []))
                idx_r = run_content.find("Referência")
                if idx_r != -1:
                    target_str = "Referência"
                    s = r_start + idx_r
                    e = s + len(target_str)
                    replacements.append((s, e, target_str, aula_data["ref"], f"Aula {current_num:02d} - Referência do versículo-chave", []))
            continue

        # 3 & 4. Direção da aula + Diretrizes da Introdução (template novo ou atualização)
        if stripped.lower() == "(texto da introdução)" or ("lorem ipsum" in stripped.lower() and topico_idx == 0):
            s = p_start
            e = p_end - 1
            dir_prefix = "(DIREÇÃO DA AULA: "
            intro_prefix = f"{dir_prefix}{aula_data['direcao']})\n(DIRETRIZES DA INTRODUÇÃO: "
            new_intro_block = (
                f"{dir_prefix}{aula_data['direcao']})\n"
                f"(DIRETRIZES DA INTRODUÇÃO: {aula_data['intro']})"
            )
            block_links = (
                shift_links(aula_data.get("direcao_links", []), len(dir_prefix)) +
                shift_links(aula_data.get("intro_links", []), len(intro_prefix))
            )
            replacements.append((s, e, stripped, new_intro_block, f"Aula {current_num:02d} - Direção + Introdução", block_links))
            continue

        if stripped.startswith("(DIREÇÃO DA AULA:"):
            s = p_start
            e = p_end - 1
            dir_prefix = "(DIREÇÃO DA AULA: "
            new_dir_text = f"{dir_prefix}{aula_data['direcao']})"
            dir_links = shift_links(aula_data.get("direcao_links", []), len(dir_prefix))
            replacements.append((s, e, stripped, new_dir_text, f"Aula {current_num:02d} - Direção da aula", dir_links))
            continue

        if stripped.startswith("(DIRETRIZES DA INTRODUÇÃO:"):
            s = p_start
            e = p_end - 1
            intro_prefix = "(DIRETRIZES DA INTRODUÇÃO: "
            new_intro_text = f"{intro_prefix}{aula_data['intro']})"
            intro_links = shift_links(aula_data.get("intro_links", []), len(intro_prefix))
            replacements.append((s, e, stripped, new_intro_text, f"Aula {current_num:02d} - Diretrizes da Introdução", intro_links))
            continue

        # 5 & 6. Títulos e Corpos dos tópicos
        if stripped.lower() == "(corpo do tópico)" or stripped.startswith("(DIRETRIZES:"):
            if topico_idx < len(aula_data["topicos"]):
                t_info = aula_data["topicos"][topico_idx]
                prev_el = orig_body[i - 1]
                if "paragraph" in prev_el:
                    prev_p = prev_el["paragraph"]
                    prev_style = prev_p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
                    prev_text = "".join(e.get("textRun", {}).get("content", "") for e in prev_p.get("elements", [])).strip()
                    if prev_style == "HEADING_2" and prev_text != t_info["title"]:
                        t_s = prev_el["startIndex"]
                        t_e = prev_el["endIndex"] - 1
                        replacements.append((t_s, t_e, prev_text, t_info["title"], f"Aula {current_num:02d} - Título do tópico {topico_idx + 1}", t_info.get("title_links", [])))

                b_s = p_start
                b_e = p_end - 1
                body_prefix = "(DIRETRIZES: "
                body_links = shift_links(t_info.get("body_links", []), len(body_prefix))
                replacements.append((b_s, b_e, stripped, f"{body_prefix}{t_info['body']})", f"Aula {current_num:02d} - Corpo do tópico {topico_idx + 1}", body_links))
                topico_idx += 1
            continue

        # 7. Terceira tarefa de casa
        if "memorize o versículo-chave:" in stripped.lower():
            idx_ref = full_text.lower().find("referência")
            if idx_ref != -1:
                old_ref = full_text[idx_ref:idx_ref + len("referência")]
                s = p_start + idx_ref
                e = s + len("referência")
                replacements.append((s, e, old_ref, aula_data["ref"], f"Aula {current_num:02d} - Referência na tarefa de casa 3", []))
            continue

    return replacements


def build_batch_requests(replacements, tab_id):
    sorted_reps = sorted(replacements, key=lambda x: x[0], reverse=True)
    requests = []
    for s, e, old_text, new_text, desc, links in sorted_reps:
        requests.append({
            "insertText": {
                "location": {"index": s + 1, "tabId": tab_id},
                "text": new_text
            }
        })
        if e > s + 1:
            requests.append({
                "deleteContentRange": {
                    "range": {
                        "startIndex": s + 1 + len(new_text),
                        "endIndex": e + len(new_text),
                        "tabId": tab_id
                    }
                }
            })
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": s,
                    "endIndex": s + 1,
                    "tabId": tab_id
                }
            }
        })
        for lk in links:
            text_style = {"link": lk["link"]}
            fields = ["link"]
            if lk.get("foregroundColor"):
                text_style["foregroundColor"] = lk["foregroundColor"]
                fields.append("foregroundColor")
            if lk.get("underline") is not None:
                text_style["underline"] = lk["underline"]
                fields.append("underline")
            requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": s + lk["start"],
                        "endIndex": s + lk["end"],
                        "tabId": tab_id
                    },
                    "textStyle": text_style,
                    "fields": ",".join(fields)
                }
            })
    return requests


def main():
    parser = argparse.ArgumentParser(description="Preenche apostila de EBD no Google Docs a partir das diretrizes.")
    parser.add_argument("--original", help="URL ou ID do Google Doc da apostila (Original)")
    parser.add_argument("--diretrizes", help="URL ou ID do Google Doc das Diretrizes")
    parser.add_argument("--aulas", type=int, nargs="*", help="Números das aulas a processar (vazio = todas)")
    parser.add_argument("--verse", action="append", default=[], help="Versículo NVI no formato NUM=TEXTO (pode repetir)")
    parser.add_argument("--mode", choices=["inspect", "apply"], help="Modo de execução: inspect ou apply")
    args = parser.parse_args()

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    orig_input = args.original if args.original is not None else config.get("original_doc", "")
    dir_input = args.diretrizes if args.diretrizes is not None else config.get("diretrizes_doc", "")
    orig_id, orig_url_tab = extract_doc_id_and_tab(orig_input)
    dir_id, dir_url_tab = extract_doc_id_and_tab(dir_input)
    orig_tab_title = config.get("original_tab_title", "Original")
    dir_tab_title = config.get("diretrizes_tab_title", "Diretrizes")

    if args.aulas is not None:
        target_aulas = [int(a) for a in args.aulas]
    else:
        target_aulas = [int(a) for a in config.get("aulas", [])]

    nvi_verses = dict(config.get("nvi_verses", {}))
    for v_item in args.verse:
        if "=" in v_item:
            k, val = v_item.split("=", 1)
            nvi_verses[str(int(k.strip()))] = val.strip()

    mode = args.mode if args.mode is not None else config.get("mode", "inspect")

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/documents"]
    )
    session = AuthorizedSession(creds)

    dir_resp = session.get(f"https://docs.googleapis.com/v1/documents/{dir_id}?includeTabsContent=true")
    if dir_resp.status_code != 200:
        print(f"Erro ao acessar documento de Diretrizes ({dir_resp.status_code}): {dir_resp.text}")
        sys.exit(1)
    dir_doc = dir_resp.json()
    _, dir_body = resolve_tab(dir_doc, tab_id=dir_url_tab, tab_title=dir_tab_title)

    diretrizes_aulas = parse_diretrizes(dir_body)
    if not target_aulas:
        target_aulas = sorted(diretrizes_aulas.keys())

    if mode == "inspect":
        print("=== AULAS EXTRAÍDAS DAS DIRETRIZES ===")
        for num in target_aulas:
            if num in diretrizes_aulas:
                d = diretrizes_aulas[num]
                print(f"Aula {num:02d}: {d['title']}")
                print(f"  Versículo-chave: {d['ref']}")
                print(f"  Direção (links={len(d['direcao_links'])}): {d['direcao'][:100]}...")
                print(f"  Introdução (links={len(d['intro_links'])}): {d['intro'][:100]}...")
                print(f"  Tópicos ({len(d['topicos'])}): {[t['title'] for t in d['topicos']]}")
        return

    missing_verses = [num for num in target_aulas if not nvi_verses.get(str(num))]
    if missing_verses:
        print(f"Erro: Faltam os textos na NVI 2011 em 'nvi_verses' no config.json para as aulas: {missing_verses}")
        for num in missing_verses:
            if num in diretrizes_aulas:
                print(f"  Aula {num:02d} requer referência: {diretrizes_aulas[num]['ref']}")
        sys.exit(1)

    orig_resp = session.get(f"https://docs.googleapis.com/v1/documents/{orig_id}?includeTabsContent=true")
    if orig_resp.status_code != 200:
        print(f"Erro ao acessar documento Original ({orig_resp.status_code}): {orig_resp.text}")
        sys.exit(1)
    orig_doc = orig_resp.json()
    orig_tab_id, orig_body = resolve_tab(orig_doc, tab_id=orig_url_tab, tab_title=orig_tab_title)

    replacements = collect_replacements(orig_body, target_aulas, diretrizes_aulas, nvi_verses)
    print(f"Total de substituições preparadas: {len(replacements)}")
    for s, e, old_t, new_t, desc, links in replacements:
        print(f"  [{s}:{e}] {desc} (links={len(links)}): {repr(old_t[:40])} -> {repr(new_t[:80])}...")

    if not replacements:
        print("Nenhuma substituição encontrada para as aulas selecionadas.")
        return

    reqs = build_batch_requests(replacements, orig_tab_id)
    update_resp = session.post(
        f"https://docs.googleapis.com/v1/documents/{orig_id}:batchUpdate",
        json={"requests": reqs}
    )
    if update_resp.status_code != 200:
        print(f"Erro no batchUpdate ({update_resp.status_code}): {update_resp.text}")
        sys.exit(1)

    print("Sucesso! Documento atualizado no Google Docs preservando 100% da formatação.")


if __name__ == "__main__":
    main()
