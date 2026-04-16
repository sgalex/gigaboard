"""Имя ZIP при экспорте: ProjectName_YYYYMMDD_hhmm.zip (локальное время сервера)."""

import re
from datetime import datetime


def build_project_export_zip_filename(project_name: str) -> str:
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")

    base = (project_name or "").strip() or "project"
    base = re.sub(r'[\\/:*?"<>|]', "_", base)
    base = re.sub(r"\s+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        base = "project"
    if len(base) > 120:
        base = base[:120]

    return f"{base}_{ts}.zip"
