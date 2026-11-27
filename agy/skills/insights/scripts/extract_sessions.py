#!/usr/bin/env python3
"""
Extract quantitative metrics and compact per-session digests from local
Antigravity (AGY) transcripts, conversation_summaries.db, history.jsonl,
and current user customization files.

Standard-library only. Read-only against ~/.gemini/.
"""

import argparse
import collections
import datetime
import glob
import json
import os
import re
import sqlite3
import statistics
from pathlib import Path

GEMINI_DIR = Path.home() / ".gemini"
AGY_DIR = GEMINI_DIR / "antigravity-cli"
BRAIN_DIR = AGY_DIR / "brain"
DB_PATH = AGY_DIR / "conversation_summaries.db"
HISTORY_PATH = AGY_DIR / "history.jsonl"


def parse_iso(ts: str):
    if not ts:
        return None
    ts = ts.strip()
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        # Handle nanoseconds in sqlite timestamps like 2026-11-27 13:22:18.181870474+00:00
        m = re.match(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})(?:\.(\d+))?(.*)$", ts)
        if m:
            base, frac, tz = m.groups()
            base = base.replace(" ", "T")
            frac = ("." + frac[:6].ljust(6, "0")) if frac else ""
            ts = base + frac + (tz or "+00:00")
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        return None


def extract_user_request(content: str) -> str:
    if not content:
        return ""
    m = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Strip trailing metadata if closing tag was truncated
    m2 = re.search(r"<USER_REQUEST>\s*(.*)", content, re.DOTALL)
    if m2:
        txt = m2.group(1)
        txt = re.split(r"<ADDITIONAL_METADATA>|<USER_SETTINGS_CHANGE>", txt)[0]
        return txt.strip()
    return content.strip()


def truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def load_db_metadata():
    meta = {}
    if not DB_PATH.exists():
        return meta
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT conversation_id, title, preview, step_count, last_modified_time,
                   workspace_uris, status, source, project_id, agent_name,
                   parent_conversation_id, nesting_depth, killed
            FROM conversation_summaries
            """
        )
        for row in cur.fetchall():
            (
                cid,
                title,
                preview,
                step_count,
                last_mod,
                workspaces,
                status,
                source,
                project_id,
                agent_name,
                parent_cid,
                depth,
                killed,
            ) = row
            meta[cid] = {
                "title": title or "",
                "preview": preview or "",
                "db_step_count": step_count or 0,
                "last_modified_time": last_mod or "",
                "workspace_uris": workspaces or "",
                "status": status or "",
                "source": source or "",
                "project_id": project_id or "",
                "agent_name": agent_name or "",
                "parent_conversation_id": parent_cid or "",
                "nesting_depth": depth or 0,
                "killed": bool(killed),
            }
        conn.close()
    except Exception as e:
        meta["_db_error"] = str(e)
    return meta


def classify_error(tool_name: str, status: str, err_text: str, content: str) -> str:
    combined = f"{err_text}\n{content}".lower()
    if "denied" in combined or "not allowed" in combined or "permission" in combined or "rejected by user" in combined:
        return "permission_or_user_denied"
    if "canceled" in combined or "cancelled" in combined or "interrupted" in combined:
        return "cancelled_or_interrupted"
    if "invalid arguments" in combined or status == "INVALID":
        return "invalid_tool_args"
    if "timeout" in combined or "timed out" in combined:
        return "timeout"
    if "no such file" in combined or "not found" in combined or "does not exist" in combined:
        return "not_found"
    if "gpg" in combined or "signing" in combined or "pinentry" in combined:
        return "gpg_or_git_signing"
    if "401" in combined or "403" in combined or "unauthorized" in combined or "token" in combined or "oauth" in combined:
        return "auth_or_api_error"
    if "syntaxerror" in combined or "traceback" in combined or "exception" in combined:
        return "script_or_runtime_error"
    if re.search(r"command exited with code [1-9]", combined):
        return "nonzero_shell_exit"
    return "other_error"


def load_customizations_inventory():
    inv = {
        "rules_files": [],
        "skills": [],
        "hooks": {},
        "mcp_servers": [],
        "settings_summary": {},
    }
    for p in [
        GEMINI_DIR / "GEMINI.md",
        GEMINI_DIR / "AGY.md",
        GEMINI_DIR / "config" / "AGENTS.md",
        GEMINI_DIR / "config" / "GEMINI.md",
    ]:
        if p.exists():
            inv["rules_files"].append({"path": str(p), "size_bytes": p.stat().st_size})

    skills_dir = GEMINI_DIR / "skills"
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                inv["skills"].append(d.name)

    hooks_path = GEMINI_DIR / "config" / "hooks.json"
    if hooks_path.exists():
        try:
            inv["hooks"] = json.loads(hooks_path.read_text(errors="replace"))
        except Exception:
            pass

    mcp_path = GEMINI_DIR / "config" / "mcp_config.json"
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(errors="replace"))
            inv["mcp_servers"] = list(data.get("mcpServers", {}).keys())
        except Exception:
            pass

    settings_path = AGY_DIR / "settings.json"
    if settings_path.exists():
        try:
            s = json.loads(settings_path.read_text(errors="replace"))
            inv["settings_summary"] = {
                "agentMode": s.get("agentMode"),
                "model": s.get("model"),
                "allowNonWorkspaceAccess": s.get("allowNonWorkspaceAccess"),
                "artifactReviewPolicy": s.get("artifactReviewPolicy"),
                "allow_permissions_count": len(s.get("permissions", {}).get("allow", [])),
                "deny_permissions_count": len(s.get("permissions", {}).get("deny", [])),
                "trustedWorkspaces": s.get("trustedWorkspaces", []),
            }
        except Exception:
            pass
    return inv


def parse_history(cutoff_dt: datetime.datetime):
    slash_cmds = collections.Counter()
    skill_invocations = collections.Counter()
    history_entries = 0
    if not HISTORY_PATH.exists():
        return {"entries": 0, "slash_commands": {}, "skill_invocations": {}}
    cutoff_ms = int(cutoff_dt.timestamp() * 1000)
    with HISTORY_PATH.open("r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            ts = obj.get("timestamp", 0)
            if ts and ts < cutoff_ms:
                continue
            history_entries += 1
            disp = (obj.get("display") or "").strip()
            if disp.startswith("/"):
                cmd = disp.split()[0].lower()
                if obj.get("type") == "slash_command":
                    slash_cmds[cmd] += 1
                else:
                    skill_invocations[cmd] += 1
    return {
        "entries": history_entries,
        "slash_commands": dict(slash_cmds.most_common(40)),
        "skill_invocations": dict(skill_invocations.most_common(40)),
    }


def unquote_arg(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return str(json.loads(s))
        except Exception:
            return s[1:-1]
    return s


def parse_transcript(path: Path, cid: str, db_info: dict):
    steps = []
    with path.open("r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except Exception:
                continue

    user_messages = []
    assistant_messages = []
    models_used = collections.Counter()
    current_ui_model = None
    tool_calls_counter = collections.Counter()
    tool_errors = []
    mcp_tools_used = collections.Counter()
    subagent_spawns = 0
    workflow_runs = 0
    skills_read = set()
    slash_in_prompts = collections.Counter()

    tokens = {"input": 0, "cache_read": 0, "output": 0}
    first_ts = None
    last_ts = None

    pending_tools = []  # queue of (name, args) from latest PLANNER_RESPONSE

    for st in steps:
        ts = parse_iso(st.get("created_at", ""))
        if ts:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

        stype = st.get("type", "")
        status = st.get("status", "")

        if stype == "USER_INPUT":
            raw = st.get("content", "")
            mm = re.search(r"Model Selection`\s+from\s+.*?\s+to\s+([^.\n]+)\.", raw)
            if mm:
                current_ui_model = mm.group(1).strip()
            req = extract_user_request(raw)
            if req:
                user_messages.append(req)
                if req.startswith("/"):
                    slash_in_prompts[req.split()[0].lower()] += 1
        elif stype == "PLANNER_RESPONSE":
            m = st.get("model") or current_ui_model or "unknown"
            models_used[m] += 1
            tokens["input"] += int(st.get("input_tokens") or 0)
            tokens["cache_read"] += int(st.get("cache_read_tokens") or 0)
            tokens["output"] += int(st.get("output_tokens") or 0)

            content = (st.get("content") or "").strip()
            if content:
                assistant_messages.append(content)

            pending_tools = []
            for tc in st.get("tool_calls") or []:
                tname = tc.get("name", "unknown")
                targs = tc.get("args") or {}
                tool_calls_counter[tname] += 1
                pending_tools.append((tname, targs))
                if tname == "invoke_subagent":
                    subagent_spawns += 1
                elif tname == "run_workflow":
                    workflow_runs += 1
                elif tname == "call_mcp_tool":
                    srv = unquote_arg(targs.get("ServerName") or targs.get("server_name") or "?")
                    mtool = unquote_arg(targs.get("ToolName") or targs.get("tool_name") or "?")
                    mcp_tools_used[f"{srv}/{mtool}"] += 1
                elif tname == "read_file":
                    p = unquote_arg(targs.get("Path") or targs.get("path") or "")
                    sm = re.search(r"/skills/([^/]+)/SKILL\.md", p)
                    if sm:
                        skills_read.add(sm.group(1))
        elif stype in ("GENERIC", "RUN_COMMAND", "CODE_ACTION", "VIEW_FILE", "GREP_SEARCH", "SEARCH_WEB", "READ_URL_CONTENT"):
            tname, targs = pending_tools.pop(0) if pending_tools else (stype.lower(), {})
            err_field = str(st.get("error") or "")
            content = str(st.get("content") or "")
            exit_match = re.search(r"Command exited with code (\d+)", content)
            nonzero = exit_match and int(exit_match.group(1)) != 0
            is_err = (status in ("ERROR", "INVALID")) or bool(err_field) or bool(nonzero)
            if is_err:
                cat = classify_error(tname, status, err_field, content)
                cmd_snippet = ""
                if tname == "run_command":
                    cmd_snippet = truncate(unquote_arg(targs.get("CommandLine") or ""), 140)
                elif tname == "call_mcp_tool":
                    cmd_snippet = f"{unquote_arg(targs.get('ServerName',''))}/{unquote_arg(targs.get('ToolName',''))}"
                elif targs:
                    cmd_snippet = truncate(json.dumps(targs, ensure_ascii=False), 120)
                err_snippet = truncate(err_field or content[-300:], 180)
                tool_errors.append(
                    {
                        "tool": tname,
                        "status": status,
                        "category": cat,
                        "args": cmd_snippet,
                        "error": err_snippet,
                    }
                )

    mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc)
    start_dt = first_ts or mtime
    end_dt = last_ts or mtime
    duration_min = max(0.0, (end_dt - start_dt).total_seconds() / 60.0)

    # Friction score heuristic for surfacing notable sessions
    friction_score = (
        len(tool_errors) * 2
        + max(0, len(user_messages) - 4) * 1.5
        + (5 if db_info.get("killed") else 0)
        + sum(3 for e in tool_errors if e["category"] in ("permission_or_user_denied", "cancelled_or_interrupted", "gpg_or_git_signing"))
    )

    return {
        "conversation_id": cid,
        "title": db_info.get("title") or (truncate(user_messages[0], 60) if user_messages else "(untitled)"),
        "workspace": db_info.get("workspace_uris") or "",
        "parent_conversation_id": db_info.get("parent_conversation_id") or "",
        "is_subagent": bool(db_info.get("parent_conversation_id")),
        "killed": bool(db_info.get("killed")),
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "date": start_dt.strftime("%Y-%m-%d"),
        "duration_min": round(duration_min, 1),
        "total_steps": len(steps),
        "user_turns": len(user_messages),
        "user_messages": user_messages,
        "final_assistant_snippet": truncate(assistant_messages[-1], 320) if assistant_messages else "",
        "models": dict(models_used),
        "tokens": tokens,
        "tool_calls": dict(tool_calls_counter),
        "tool_errors": tool_errors,
        "mcp_tools": dict(mcp_tools_used),
        "skills_read": sorted(skills_read),
        "slash_in_prompts": dict(slash_in_prompts),
        "subagent_spawns": subagent_spawns,
        "workflow_runs": workflow_runs,
        "friction_score": round(friction_score, 1),
    }


def build_batches(sessions, out_dir: Path, max_batch_chars: int = 34000, max_sessions_per_batch: int = 20):
    batches_dir = out_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    batch_files = []
    cur_lines = []
    cur_chars = 0
    cur_count = 0
    batch_idx = 1

    def flush():
        nonlocal cur_lines, cur_chars, cur_count, batch_idx
        if not cur_lines:
            return
        p = batches_dir / f"batch_{batch_idx:02d}.md"
        p.write_text("\n".join(cur_lines), encoding="utf-8")
        batch_files.append(str(p))
        batch_idx += 1
        cur_lines = []
        cur_chars = 0
        cur_count = 0

    for s in sessions:
        block = []
        block.append(f"## Session `{s['conversation_id']}` | {s['date']} | {s['title']}")
        top_models = ", ".join(f"{k}({v})" for k, v in sorted(s["models"].items(), key=lambda x: -x[1])[:2])
        meta_bits = [
            f"turns={s['user_turns']}",
            f"steps={s['total_steps']}",
            f"dur={s['duration_min']}m",
            f"errors={len(s['tool_errors'])}",
            f"friction={s['friction_score']}",
        ]
        if s["killed"]:
            meta_bits.append("KILLED")
        if s["skills_read"]:
            meta_bits.append(f"skills={','.join(s['skills_read'])}")
        if s["workspace"]:
            meta_bits.append(f"ws={s['workspace']}")
        if top_models:
            meta_bits.append(f"models={top_models}")
        block.append("- Meta: " + " | ".join(meta_bits))

        # Include all user messages (capped per message to keep concise)
        block.append("- User turns:")
        for i, um in enumerate(s["user_messages"][:25], 1):
            block.append(f"  {i}. {truncate(um, 450)}")
        if len(s["user_messages"]) > 25:
            block.append(f"  ... ({len(s['user_messages']) - 25} more turns)")

        if s["tool_errors"]:
            block.append("- Tool errors (up to 6):")
            for e in s["tool_errors"][:6]:
                block.append(f"  - [{e['category']}] `{e['tool']}` args=`{e['args']}` -> {e['error']}")
            if len(s["tool_errors"]) > 6:
                block.append(f"  - ... (+{len(s['tool_errors']) - 6} more errors)")

        if s["final_assistant_snippet"]:
            block.append(f"- Final outcome snippet: {s['final_assistant_snippet']}")
        block.append("")

        chunk = "\n".join(block)
        if cur_lines and (cur_chars + len(chunk) > max_batch_chars or cur_count >= max_sessions_per_batch):
            flush()
        cur_lines.append(chunk)
        cur_chars += len(chunk)
        cur_count += 1

    flush()
    return batch_files


def main():
    parser = argparse.ArgumentParser(description="Extract Antigravity session metrics and digests for /insights.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of top-level sessions (0 = unlimited)")
    parser.add_argument("--exclude-cid", default=os.environ.get("ANTIGRAVITY_CONVERSATION_ID", ""), help="Conversation ID to exclude")
    parser.add_argument("--out-dir", required=True, help="Directory to write metrics.json and batches/")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=args.days)

    db_meta = load_db_metadata()

    transcript_files = glob.glob(str(BRAIN_DIR / "*" / ".system_generated" / "logs" / "transcript.jsonl"))
    parsed_top = []
    parsed_sub = []

    for tf in transcript_files:
        p = Path(tf)
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime, tz=datetime.timezone.utc)
        if mtime < cutoff:
            continue
        cid = p.parts[p.parts.index("brain") + 1]
        if args.exclude_cid and cid == args.exclude_cid:
            continue
        info = db_meta.get(cid, {})
        rec = parse_transcript(p, cid, info)
        # Skip completely empty sessions with 0 user turns and 0 steps
        if rec["total_steps"] == 0:
            continue
        if rec["is_subagent"]:
            parsed_sub.append(rec)
        else:
            parsed_top.append(rec)

    parsed_top.sort(key=lambda r: r["start_time"], reverse=True)
    if args.limit and args.limit > 0:
        parsed_top = parsed_top[: args.limit]

    # Aggregate quantitative metrics
    all_sessions = parsed_top + parsed_sub
    active_days = sorted({s["date"] for s in parsed_top})
    sessions_by_month = collections.Counter(s["date"][:7] for s in parsed_top)
    workspaces = collections.Counter(s["workspace"] or "(none)" for s in parsed_top)
    models_steps = collections.Counter()
    models_sessions = collections.Counter()
    tool_totals = collections.Counter()
    tool_err_by_tool = collections.Counter()
    tool_err_by_cat = collections.Counter()
    failed_cmd_prefixes = collections.Counter()
    mcp_totals = collections.Counter()
    skills_used = collections.Counter()
    prompt_slashes = collections.Counter()

    total_tokens = {"input": 0, "cache_read": 0, "output": 0}
    turns_list = []
    turn_buckets = collections.Counter()

    for s in parsed_top:
        t = s["user_turns"]
        turns_list.append(t)
        if t <= 1:
            turn_buckets["1_turn"] += 1
        elif t <= 5:
            turn_buckets["2_to_5_turns"] += 1
        elif t <= 15:
            turn_buckets["6_to_15_turns"] += 1
        else:
            turn_buckets["16_plus_turns"] += 1

        for m, cnt in s["models"].items():
            models_sessions[m] += 1
        for sk in s["skills_read"]:
            skills_used[sk] += 1
        for sc, cnt in s["slash_in_prompts"].items():
            prompt_slashes[sc] += cnt

    for s in all_sessions:
        for m, cnt in s["models"].items():
            models_steps[m] += cnt
        for k in total_tokens:
            total_tokens[k] += s["tokens"][k]
        for tn, cnt in s["tool_calls"].items():
            tool_totals[tn] += cnt
        for mt, cnt in s["mcp_tools"].items():
            mcp_totals[mt] += cnt
        for e in s["tool_errors"]:
            tool_err_by_tool[e["tool"]] += 1
            tool_err_by_cat[e["category"]] += 1
            if e["tool"] == "run_command" and e["args"]:
                first_tok = e["args"].strip().split()[0]
                failed_cmd_prefixes[first_tok] += 1

    total_in_plus_cache = total_tokens["input"] + total_tokens["cache_read"]
    cache_hit_rate = round((total_tokens["cache_read"] / total_in_plus_cache) * 100, 1) if total_in_plus_cache else 0.0

    top_friction = sorted(parsed_top, key=lambda s: -s["friction_score"])[:15]
    top_friction_summary = [
        {
            "conversation_id": s["conversation_id"],
            "date": s["date"],
            "title": s["title"],
            "user_turns": s["user_turns"],
            "tool_errors": len(s["tool_errors"]),
            "killed": s["killed"],
            "friction_score": s["friction_score"],
            "skills": s["skills_read"],
        }
        for s in top_friction
    ]

    metrics = {
        "window": {
            "days": args.days,
            "from": cutoff.strftime("%Y-%m-%d"),
            "to": now.strftime("%Y-%m-%d"),
        },
        "counts": {
            "top_level_sessions": len(parsed_top),
            "subagent_sessions": len(parsed_sub),
            "active_days": len(active_days),
            "total_user_turns": sum(turns_list),
            "median_turns_per_session": round(statistics.median(turns_list), 1) if turns_list else 0,
            "max_turns_in_session": max(turns_list) if turns_list else 0,
            "killed_sessions": sum(1 for s in parsed_top if s["killed"]),
            "total_tool_calls": sum(tool_totals.values()),
            "total_tool_errors": sum(tool_err_by_tool.values()),
            "tool_error_rate_pct": round((sum(tool_err_by_tool.values()) / sum(tool_totals.values())) * 100, 1)
            if sum(tool_totals.values())
            else 0.0,
            "subagent_spawns_from_top": sum(s["subagent_spawns"] for s in parsed_top),
            "workflow_runs_from_top": sum(s["workflow_runs"] for s in parsed_top),
        },
        "sessions_by_month": dict(sorted(sessions_by_month.items())),
        "turn_buckets": dict(turn_buckets),
        "workspaces": dict(workspaces.most_common(15)),
        "models_by_planner_steps": dict(models_steps.most_common(15)),
        "models_by_top_sessions": dict(models_sessions.most_common(15)),
        "tokens": {**total_tokens, "cache_hit_rate_pct": cache_hit_rate},
        "top_tools": dict(tool_totals.most_common(20)),
        "tool_errors_by_tool": dict(tool_err_by_tool.most_common(15)),
        "tool_errors_by_category": dict(tool_err_by_cat.most_common(15)),
        "top_failed_shell_prefixes": dict(failed_cmd_prefixes.most_common(15)),
        "mcp_tools_used": dict(mcp_totals.most_common(20)),
        "skills_loaded": dict(skills_used.most_common(20)),
        "slash_in_prompts": dict(prompt_slashes.most_common(20)),
        "history_jsonl": parse_history(cutoff),
        "highest_friction_sessions": top_friction_summary,
        "customizations_inventory": load_customizations_inventory(),
    }

    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    # Compact jsonl of all top-level sessions
    sessions_path = out_dir / "sessions_compact.jsonl"
    with sessions_path.open("w", encoding="utf-8") as fh:
        for s in parsed_top:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    batch_files = build_batches(parsed_top, out_dir)

    print(
        json.dumps(
            {
                "metrics_path": str(metrics_path),
                "sessions_path": str(sessions_path),
                "batch_count": len(batch_files),
                "batch_files": batch_files,
                "counts": metrics["counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
