import json
import os
import re
import subprocess
import sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_CONFIG_PATH = "/mnt/c/Users/lplim/.gemini/gdocs_tmp_config.json"
FALLBACK_CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_PATH = "/home/lp-lima/.gemini/skills/import-nubank-expenses/assets/credentials.json"


def resolve_config_path():
    candidates = [p for p in (WORKSPACE_CONFIG_PATH, FALLBACK_CONFIG_PATH) if os.path.exists(p)]
    if not candidates:
        return WORKSPACE_CONFIG_PATH
    return max(candidates, key=os.path.getmtime)


def extract_doc_id(url_or_id):
    if not url_or_id:
        return ""
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def normalize_text(text):
    """Normaliza um parágrafo removendo marcações Markdown para comparar com o texto puro do Google Docs."""
    t = text.replace("\\", "")
    t = re.sub(r"^\s*([*+-]\s+)?#{1,6}\s+", "", t)
    t = re.sub(r"^\s*\d+\.\s+", "", t)
    t = t.replace("*", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def get_gdocs_tab_paragraphs(doc, target_tab_name="Tmp"):
    tabs = doc.get("tabs", [])
    target_tab = None
    for t in tabs:
        props = t.get("tabProperties", {})
        if props.get("title", "").strip().lower() == target_tab_name.strip().lower():
            target_tab = t
            break

    if not target_tab:
        return None, None

    tab_id = target_tab["tabProperties"]["tabId"]
    body = target_tab.get("documentTab", {}).get("body", {}).get("content", [])
    paragraphs = []
    raw_paragraphs = []
    para_meta = []
    for el in body:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        txt = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        if txt.strip():
            norm = normalize_text(txt)
            if norm:
                paragraphs.append(norm)
                raw_paragraphs.append(txt.rstrip("\n"))
                para_meta.append(
                    {
                        "startIndex": el.get("startIndex", 0),
                        "endIndex": el.get("endIndex", 0),
                        "raw": txt,
                    }
                )
    return tab_id, (paragraphs, raw_paragraphs, para_meta)


def get_md_paragraphs(md_text):
    paragraphs = []
    for line in md_text.splitlines():
        if line.strip():
            norm = normalize_text(line)
            if norm:
                paragraphs.append(norm)
    return paragraphs


def find_lesson_slice(gdocs_paras, md_init_paras, md_corr_paras):
    """Localiza o intervalo [start_idx, end_idx) da aula dentro de uma aba com múltiplas aulas (ex: 'Revisada')."""
    if not md_corr_paras:
        return 0, len(gdocs_paras)

    first_corr = md_corr_paras[0]
    first_init = md_init_paras[0] if md_init_paras else first_corr
    m = re.match(r"^(Aula\s+0*(\d+))\b", first_corr, re.IGNORECASE)
    lesson_num = int(m.group(2)) if m else None

    start_idx = None
    for i, gp in enumerate(gdocs_paras):
        if gp == first_corr or gp == first_init:
            start_idx = i
            break
        if lesson_num is not None:
            gm = re.match(r"^Aula\s+0*(\d+)\b", gp, re.IGNORECASE)
            if gm and int(gm.group(1)) == lesson_num:
                start_idx = i
                break

    if start_idx is None:
        return None, None

    end_idx = len(gdocs_paras)
    for j in range(start_idx + 1, len(gdocs_paras)):
        gm = re.match(r"^Aula\s+0*(\d+)\b", gdocs_paras[j], re.IGNORECASE)
        if gm and (lesson_num is None or int(gm.group(1)) != lesson_num):
            end_idx = j
            break

    return start_idx, end_idx


def main():
    config_path = resolve_config_path()
    if not os.path.exists(config_path):
        print(f"Erro: Arquivo de configuração não encontrado em {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    doc_url = config.get("google_doc", "")
    md_path = config.get("md_path", "")
    tab_name = config.get("tab_name", "Tmp")
    strict_validation = config.get("strict_validation", tab_name.strip().lower() == "tmp")
    replacements = config.get("replacements", [])

    doc_id = extract_doc_id(doc_url)
    if not doc_id:
        print("Erro: 'google_doc' inválido ou ausente no config.json.")
        sys.exit(1)

    if not md_path or not os.path.exists(md_path):
        print(f"Erro: Arquivo Markdown não encontrado: {md_path}")
        sys.exit(1)

    with open(md_path, "r", encoding="utf-8") as f:
        md_corrected_text = f.read()

    md_initial_text = md_corrected_text
    try:
        repo_dir = os.path.dirname(md_path)
        rel_path = subprocess.check_output(
            ["git", "ls-files", "--full-name", md_path],
            cwd=repo_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if rel_path:
            commits = (
                subprocess.check_output(
                    ["git", "log", "--format=%H", "--", rel_path],
                    cwd=repo_dir,
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                .strip()
                .splitlines()
            )
            if len(commits) >= 2:
                md_initial_text = subprocess.check_output(
                    ["git", "show", f"{commits[-1]}:{rel_path}"],
                    cwd=repo_dir,
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
    except Exception:
        pass

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/documents"],
    )
    session = AuthorizedSession(creds)

    resp = session.get(f"https://docs.googleapis.com/v1/documents/{doc_id}?includeTabsContent=true")
    if resp.status_code != 200:
        print(f"ABORTADO: Erro ao acessar o Google Docs ({resp.status_code}): {resp.text}")
        sys.exit(1)

    doc = resp.json()
    tab_id, tab_data = get_gdocs_tab_paragraphs(doc, tab_name)
    if not tab_id:
        tabs_found = [t.get("tabProperties", {}).get("title") for t in doc.get("tabs", [])]
        print(
            f"ABORTADO: A aba '{tab_name}' não foi encontrada no documento '{doc.get('title')}'. Abas existentes: {tabs_found}"
        )
        sys.exit(1)

    all_gdocs_paras, all_raw_gdocs_paras, all_para_meta = tab_data
    md_init_paras = get_md_paragraphs(md_initial_text)
    md_corr_paras = get_md_paragraphs(md_corrected_text)

    is_multi_lesson_tab = len(all_gdocs_paras) > len(md_corr_paras) and tab_name.strip().lower() != "tmp"
    if is_multi_lesson_tab:
        s_idx, e_idx = find_lesson_slice(all_gdocs_paras, md_init_paras, md_corr_paras)
        if s_idx is None:
            print(f"ABORTADO: Não foi possível localizar a aula '{md_corr_paras[0]}' na aba '{tab_name}'.")
            sys.exit(1)
        gdocs_paras = all_gdocs_paras[s_idx:e_idx]
        raw_gdocs_paras = all_raw_gdocs_paras[s_idx:e_idx]
        para_meta = all_para_meta[s_idx:e_idx]
    else:
        gdocs_paras = all_gdocs_paras
        raw_gdocs_paras = all_raw_gdocs_paras
        para_meta = all_para_meta

    divergences = []
    if len(gdocs_paras) != len(md_corr_paras):
        divergences.append(
            f"Quantidade de parágrafos divergente: trecho na aba '{tab_name}' possui {len(gdocs_paras)} parágrafos, enquanto o arquivo .md possui {len(md_corr_paras)}."
        )

    min_len = min(len(gdocs_paras), len(md_corr_paras))
    for i in range(min_len):
        gp = gdocs_paras[i]
        mp_init = md_init_paras[i] if i < len(md_init_paras) else ""
        mp_corr = md_corr_paras[i]

        gp_sim = raw_gdocs_paras[i]
        for item in replacements:
            old_t = item["old"].replace("*", "")
            new_t = item["new"].replace("*", "")
            gp_sim = gp_sim.replace(old_t, new_t)
        gp_sim_norm = normalize_text(gp_sim)

        if gp != mp_init and gp != mp_corr and gp_sim_norm != mp_corr:
            diff_pos = 0
            while diff_pos < len(gp_sim_norm) and diff_pos < len(mp_corr) and gp_sim_norm[diff_pos] == mp_corr[diff_pos]:
                diff_pos += 1
            start_slice = max(0, diff_pos - 30)
            divergences.append(
                f"Parágrafo {i + 1} diverge (a partir do caractere {diff_pos}):\n"
                f"  - Aba '{tab_name}': ...{gp[start_slice:start_slice + 160]}...\n"
                f"  - Arquivo .md: ...{mp_corr[start_slice:start_slice + 160]}..."
            )

    if divergences:
        if strict_validation:
            print(f"ABORTADO: O conteúdo da aba '{tab_name}' no Google Docs não bate com o arquivo .md da aula!")
            for d in divergences:
                print("  *", d)
            sys.exit(1)
        else:
            print(f"AVISO: Diferenças detectadas na aba '{tab_name}' (modo não-estrito, prosseguindo com as substituições):")
            for d in divergences:
                print("  *", d)

    if not replacements:
        print(f"Validação concluída com sucesso na aba '{tab_name}'. Nenhuma substituição pendente.")
        return

    if not is_multi_lesson_tab:
        requests = []
        for item in replacements:
            old_t = item["old"].replace("*", "")
            new_t = item["new"].replace("*", "")
            requests.append(
                {
                    "replaceAllText": {
                        "containsText": {
                            "text": old_t,
                            "matchCase": True,
                        },
                        "replaceText": new_t,
                        "tabsCriteria": {
                            "tabIds": [tab_id],
                        },
                    }
                }
            )

        upd = session.post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            json={"requests": requests},
        )
        if upd.status_code != 200:
            print(f"ABORTADO: Erro ao aplicar correções no Google Docs ({upd.status_code}): {upd.text}")
            sys.exit(1)

        replies = upd.json().get("replies", [])
        total_applied = 0
        for item, rep in zip(replacements, replies):
            count = rep.get("replaceAllText", {}).get("occurrencesChanged", 0)
            total_applied += count
            print(f"[{count}] {item['old']!r} -> {item['new']!r}")

        print(f"Sucesso! {total_applied} ocorrências corrigidas na aba '{tab_name}' do Google Docs.")
    else:
        # Em aba com múltiplas aulas (ex: 'Revisada'), aplicar substituições estritamente nos índices da aula
        # em ordem reversa de startIndex para preservar 100% da formatação inline e não afetar outras aulas.
        edits = []
        counts = {i: 0 for i in range(len(replacements))}
        for pm in para_meta:
            p_start = pm["startIndex"]
            raw_txt = pm["raw"]
            # Coletar ocorrências de todos os replacements neste parágrafo sem sobreposição
            p_edits = []
            for idx_r, item in enumerate(replacements):
                old_t = item["old"].replace("*", "")
                new_t = item["new"].replace("*", "")
                if not old_t or old_t == new_t:
                    continue
                pos = 0
                while True:
                    found = raw_txt.find(old_t, pos)
                    if found == -1:
                        break
                    abs_start = p_start + found
                    abs_end = abs_start + len(old_t)
                    p_edits.append((abs_start, abs_end, old_t, new_t, idx_r))
                    pos = found + len(old_t)

            # Ordenar e filtrar sobreposições dentro do parágrafo
            p_edits.sort(key=lambda x: (x[0], -(x[1] - x[0])))
            filtered = []
            last_end = -1
            for ed in p_edits:
                if ed[0] >= last_end:
                    filtered.append(ed)
                    last_end = ed[1]
                    counts[ed[4]] += 1
            edits.extend(filtered)

        if not edits:
            print(f"Nenhuma ocorrência pendente encontrada na aula dentro da aba '{tab_name}'.")
            return

        # Ordenar em ordem decrescente de índice para não deslocar posições anteriores
        edits.sort(key=lambda x: x[0], reverse=True)
        requests = []
        for abs_start, abs_end, old_t, new_t, _ in edits:
            # Inserir o novo texto primeiro na posição inicial (herdando a formatação exata do trecho original)
            # e em seguida remover o texto antigo deslocado.
            requests.append(
                {
                    "insertText": {
                        "location": {"index": abs_start, "tabId": tab_id},
                        "text": new_t,
                    }
                }
            )
            requests.append(
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": abs_start + len(new_t),
                            "endIndex": abs_end + len(new_t),
                            "tabId": tab_id,
                        }
                    }
                }
            )

        upd = session.post(
            f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
            json={"requests": requests},
        )
        if upd.status_code != 200:
            print(f"ABORTADO: Erro ao aplicar correções na aba '{tab_name}' ({upd.status_code}): {upd.text}")
            sys.exit(1)

        total_applied = 0
        for idx_r, item in enumerate(replacements):
            c = counts[idx_r]
            total_applied += c
            print(f"[{c}] {item['old']!r} -> {item['new']!r}")

        print(f"Sucesso! {total_applied} ocorrências corrigidas na aula dentro da aba '{tab_name}' do Google Docs.")


if __name__ == "__main__":
    main()
