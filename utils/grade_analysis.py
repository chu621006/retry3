import streamlit as st
import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    g = normalize_text(gpa_str).upper()
    failing = {"D","D-","E","F","X","不通過","未通過","不及格"}
    if not g:
        return False
    if g in {"通過","抵免","PASS","EXEMPT"}:
        return True
    if g in failing:
        return False
    if re.fullmatch(r"[A-C][+\-]?", g):
        return True
    if re.fullmatch(r"\d+(\.\d+)?", g):
        return float(g) >= 60.0
    return False

def parse_credit_and_gpa(text):
    t = normalize_text(text)
    if t.lower() in {"通過","抵免","pass","exempt"}:
        return 0.0, t
    m = re.match(r"([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)", t)
    if m:
        return float(m.group(2)), m.group(1).upper()
    m = re.match(r"(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)", t)
    if m:
        return float(m.group(1)), m.group(3).upper()
    m = re.search(r"(\d+(\.\d+)?)", t)
    if m:
        return float(m.group(1)), ""
    m = re.search(r"([A-Fa-f][+\-]?)", t)
    if m:
        return 0.0, m.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total = 0.0
    passed = []
    failed = []
    seen = set()

    credit_keys = ["學分","credit"]
    subject_keys = ["科目名稱","課程名稱","subject"]
    gpa_keys     = ["GPA","成績","grade"]
    year_keys    = ["學年","year"]
    sem_keys     = ["學期","semester"]

    for i, df in enumerate(df_list):
        if df.empty or df.shape[1] < 3:
            continue

        cols = {re.sub(r"\s+","",c).lower(): c for c in df.columns}
        def pick(keys):
            for k in keys:
                if k.lower() in cols:
                    return cols[k.lower()]
            return None

        ccol = pick(credit_keys)
        scol = pick(subject_keys)
        gcol = pick(gpa_keys)
        ycol = pick(year_keys)
        mcol = pick(sem_keys)
        if not scol or (not ccol and not gcol):
            continue

        buf = ""
        for _, row in df.iterrows():
            rd = {c: normalize_text(row[c]) if pd.notna(row[c]) else "" for c in df.columns}
            raw = rd.get(scol, "")
            subj = re.sub(r"^[^\u4e00-\u9fa5]+", "", raw).strip()
            # 跳過不含中文的行
            if not re.search(r"[\u4e00-\u9fa5]", subj):
                buf = ""
                continue

            ct, gt = 0.0, ""
            if ccol:
                ct, gt = parse_credit_and_gpa(rd.get(ccol, ""))
            if gcol:
                ct2, gt2 = parse_credit_and_gpa(rd.get(gcol, ""))
                if gt2:
                    gt = gt2
                if ct2 > 0 and ct == 0:
                    ct = ct2

            complete = (
                ct > 0
                or is_passing_gpa(gt)
                or rd.get(ccol, "").lower() in {"通過","抵免"}
                or rd.get(gcol, "").lower() in {"通過","抵免"}
            )

            if not complete:
                buf = subj if not buf else f"{buf} {subj}"
                continue

            name = f"{buf} {subj}".strip() if buf else subj
            buf = ""

            year = rd.get(ycol, "")
            sem  = rd.get(mcol, "")
            key = (year, sem, name)
            if key in seen:
                continue
            seen.add(key)

            rec = {
                "學年度": year,
                "學期": sem,
                "科目名稱": name,
                "學分": ct,
                "GPA": gt,
                "來源表格": i+1
            }

            if gt and not is_passing_gpa(gt):
                failed.append(rec)
            else:
                total += ct
                passed.append(rec)

        if buf:
            st.warning(f"表格{i+1} 殘留未合并科目「{buf}」")

    return total, passed, failed
