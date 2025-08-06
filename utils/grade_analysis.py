# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    gpa = normalize_text(gpa_str).upper()
    failing = {"D","D-","E","F","X","不通過","未通過","不及格"}
    if not gpa: return False
    if gpa in {"通過","抵免","PASS","EXEMPT"}: return True
    if gpa in failing: return False
    if re.fullmatch(r"[A-C][+\-]?", gpa): return True
    if re.fullmatch(r"\d+(\.\d+)?", gpa):
        try: return float(gpa) >= 60.0
        except: pass
    return False

def parse_credit_and_gpa(text):
    t = normalize_text(text)
    if t.lower() in {"通過","抵免","pass","exempt"}:
        return 0.0, t
    m = re.match(r"([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)", t)
    if m: return float(m.group(2)), m.group(1).upper()
    m = re.match(r"(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)", t)
    if m: return float(m.group(1)), m.group(3).upper()
    m = re.search(r"(\d+(\.\d+)?)", t)
    if m: return float(m.group(1)), ""
    m = re.search(r"([A-Fa-f][+\-]?)", t)
    if m: return 0.0, m.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    # 各種欄位關鍵字
    credit_keys = ["學分","credit"]
    subject_keys = ["科目名稱","課程名稱","subject"]
    gpa_keys     = ["GPA","成績","grade"]
    year_keys    = ["學年","year"]
    sem_keys     = ["學期","semester"]

    for df_idx, df in enumerate(df_list):
        if df.empty or df.shape[1] < 3:
            continue

        # 正規化欄位名稱
        cols_norm = {re.sub(r"\s+","",c).lower(): c for c in df.columns}

        def find_col(keys):
            for k in keys:
                if k.lower() in cols_norm:
                    return cols_norm[k.lower()]
            return None

        credit_col  = find_col(credit_keys)
        subject_col = find_col(subject_keys)
        gpa_col     = find_col(gpa_keys)
        year_col    = find_col(year_keys)
        sem_col     = find_col(sem_keys)

        if not subject_col or (not credit_col and not gpa_col):
            continue

        # ── 新增：抓出所有屬於“科目名稱”的連續欄位範圍 ──
        cols = list(df.columns)
        subj_idx = cols.index(subject_col)
        if credit_col:
            cred_idx = cols.index(credit_col)
        else:
            cred_idx = len(cols)
        # 從 subject_col 開始直到 credit_col 前一欄都視為科目欄
        subject_range = cols[subj_idx:cred_idx]

        buffer_name = ""
        for _, row in df.iterrows():
            rd = {c: normalize_text(row[c]) if pd.notna(row[c]) else "" for c in df.columns}

            # ── 先合併同一行的多欄科目名稱 ──
            parts = [ rd[c] for c in subject_range if rd.get(c) ]
            subj_raw = " ".join(parts).strip()

            cred_txt = rd.get(credit_col,"") if credit_col else ""
            gpa_txt  = rd.get(gpa_col,"")    if gpa_col else ""

            cred, gpa = parse_credit_and_gpa(cred_txt)
            pc, pg = parse_credit_and_gpa(gpa_txt)
            if pg: gpa = pg
            if pc>0 and cred==0: cred = pc

            # 判斷是否完整課程
            is_complete = (
                cred>0
                or is_passing_gpa(gpa)
                or cred_txt.lower() in {"通過","抵免"}
                or gpa_txt.lower() in {"通過","抵免"}
            )

            # 空行清 buffer
            if all(not rd.get(c,"") for c in subject_range+[credit_col, gpa_col] if c):
                buffer_name = ""
                continue

            if is_complete:
                # 只有當本行 cred==0 時合併舊 buffer
                if buffer_name and cred==0:
                    final_name = f"{buffer_name} {subj_raw}".strip()
                else:
                    final_name = subj_raw
                buffer_name = ""

                # 學年度 / 學期
                acad = rd.get(year_col,"")
                sem  = rd.get(sem_col,"")

                record = {
                    "學年度": acad,
                    "學期": sem,
                    "科目名稱": final_name or "未知科目",
                    "學分": cred,
                    "GPA": gpa,
                    "來源表格": df_idx+1
                }

                if gpa and not is_passing_gpa(gpa):
                    failed_courses.append(record)
                else:
                    total_credits += cred
                    calculated_courses.append(record)
            else:
                # 累 buffer（只有名稱，credit=0）
                if subj_raw:
                    buffer_name = (buffer_name+" "+subj_raw).strip() if buffer_name else subj_raw

        # page 結束後若有殘留 buffer 警告
        if buffer_name:
            import streamlit as st
            st.warning(f"表格{df_idx+1}偵測到未完成課程名稱「{buffer_name}」，已跳過")

    return total_credits, calculated_courses, failed_courses
