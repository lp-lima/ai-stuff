import json
import os
import re
import subprocess
import sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_PATH = "/home/lp-lima/.gemini/skills/import-nubank-expenses/assets/credentials.json"


def extract_doc_id(url_or_id):
    if not url_or_id:
        return ""
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def normalize_text(text):
    """Normaliza um parágrafo removendo marcações Markdown para comparar com o texto puro do Google Docs."""
    # Remover barras invertidas de escape do Markdown
    t = text.replace("\\", "")
    # Remover cabeçalhos Markdown no início da linha (#, ##, ###) e marcadores de lista (*, -)
    t = re.sub(r"^\s*([*+-]\s+)?#{1,6}\s+", "", t)
    # Remover numeração de lista ordenada no início da linha (ex: "1. ", "2. ") pois no Google Docs listas ficam em bullet/list properties
    t = re.sub(r"^\s*\d+\.\s+", "", t)
    # Remover asteriscos de negrito/itálico
    t = t.replace("*", "")
    # Normalizar espaços em branco
    t = re.sub(r"\s+", " ", t).strip()
    return t


def get_gdocs_tmp_paragraphs(doc):
    tabs = doc.get("tabs", [])
    tmp_tab = None
    for t in tabs:
        props = t.get("tabProperties", {})
        if props.get("title", "").strip().lower() == "tmp":
            tmp_tab = t
            break

    if not tmp_tab:
        return None, None

    tab_id = tmp_tab["tabProperties"]["tabId"]
    body = tmp_tab.get("documentTab", {}).get("body", {}).get("content", [])
    paragraphs = []
    raw_paragraphs = []
    for el in body:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        txt = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        if txt.strip():
            raw_paragraphs.append(txt.rstrip("\n"))
            norm = normalize_text(txt)
            if norm:
                paragraphs.append(norm)
    return tab_id, (paragraphs, raw_paragraphs)


def get_md_paragraphs(md_text):
    paragraphs = []
    for line in md_text.splitlines():
        if line.strip():
            norm = normalize_text(line)
            if norm:
                paragraphs.append(norm)
    return paragraphs


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"Erro: Arquivo de configuração não encontrado em {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    doc_url = config.get("google_doc", "")
    md_path = config.get("md_path", "")
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

    # Tentar obter também a versão inicial (HEAD~1) no Git para aceitar parágrafos antes ou depois da correção
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
            md_initial_text = subprocess.check_output(
                ["git", "show", f"HEAD~1:{rel_path}"],
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
    tab_id, tab_data = get_gdocs_tmp_paragraphs(doc)
    if not tab_id:
        tabs_found = [t.get("tabProperties", {}).get("title") for t in doc.get("tabs", [])]
        print(f"ABORTADO: A aba 'Tmp' não foi encontrada no documento '{doc.get('title')}'. Abas existentes: {tabs_found}")
        sys.exit(1)

    gdocs_paras, raw_gdocs_paras = tab_data
    md_init_paras = get_md_paragraphs(md_initial_text)
    md_corr_paras = get_md_paragraphs(md_corrected_text)

    # Validar se o conteúdo da aba Tmp bate com o arquivo .md (aceitando parágrafos na versão inicial ou corrigida)
    divergences = []
    if len(gdocs_paras) != len(md_corr_paras):
        divergences.append(
            f"Quantidade de parágrafos divergente: aba 'Tmp' possui {len(gdocs_paras)} parágrafos, enquanto o arquivo .md possui {len(md_corr_paras)}."
        )

    min_len = min(len(gdocs_paras), len(md_corr_paras))
    for i in range(min_len):
        gp = gdocs_paras[i]
        mp_init = md_init_paras[i] if i < len(md_init_paras) else ""
        mp_corr = md_corr_paras[i]
        if gp != mp_init and gp != mp_corr:
            # Localizar ponto exato de divergência em relação à versão inicial
            diff_pos = 0
            while diff_pos < len(gp) and diff_pos < len(mp_init) and gp[diff_pos] == mp_init[diff_pos]:
                diff_pos += 1
            start_slice = max(0, diff_pos - 30)
            divergences.append(
                f"Parágrafo {i + 1} diverge (a partir do caractere {diff_pos}):\n"
                f"  - Aba 'Tmp': ...{gp[start_slice:start_slice + 160]}...\n"
                f"  - Arquivo .md: ...{mp_init[start_slice:start_slice + 160]}..."
            )

    if divergences:
        print("ABORTADO: O conteúdo da aba 'Tmp' no Google Docs não bate com o arquivo .md da aula!")
        for d in divergences:
            print("  *", d)
        sys.exit(1)

    if not replacements:
        print("Validação concluída com sucesso (conteúdo idêntico). Nenhuma substituição pendente.")
        return

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

    print(f"Sucesso! {total_applied} ocorrências corrigidas na aba 'Tmp' do Google Docs.")


if __name__ == "__main__":
    main()
