# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    gpa = normalize_text(gpa_str).upper()
    failing = {"D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"}
    if not gpa:
        return False
    if gpa in {"通過", "抵免", "PASS", "EXEMPT"}:
        return True
    if gpa in failing:
        return False
    if re.fullmatch(r'[A-C][+\-]?', gpa):
        return True
    # 數字成績視 >=60 為及格
    if re.fullmatch(r'\d+(\.\d+)?', gpa):
        try:
            return float(gpa) >= 60.0
        except:
            pass
    return False

def parse_credit_and_gpa(text):
    t = normalize_text(text)
    if t.lower() in {"通過", "抵免", "pass", "exempt"}:
        return 0.0, t
    # G 2
    m = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', t)
    if m:
        return float(m.group(2)), m.group(1).upper()
    # 2 G
    m = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', t)
    if m:
        return float(m.group(1)), m.group(3).upper()
    # 只有學分
    m = re.search(r'(\d+(\.\d+)?)', t)
    if m:
        return float(m.group(1)), ""
    # 只有GPA
    m = re.search(r'([A-Fa-f][+\-]?)', t)
    if m:
        return 0.0, m.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    credit_keys = ["學分", "學分數", "credit"]
    subject_keys = ["科目名稱", "課程名稱", "subject"]
    gpa_keys = ["GPA", "成績", "grade"]
    year_keys = ["學年", "year"]
    sem_keys = ["學期", "semester"]

    for idx, df in enumerate(df_list):
        if df.empty or df.shape[1] < 3:
            continue

        # 找欄位名
        cols_norm = {re.sub(r'\s+', '', c).lower(): c for c in df.columns}
        found = {}
        for keys, name in [(credit_keys, 'credit'),
                           (subject_keys, 'subject'),
                           (gpa_keys, 'gpa'),
                           (year_keys, 'year'),
                           (sem_keys, 'sem')]:
            for k in keys:
                if k.lower() in cols_norm:
                    found[name] = cols_norm[k.lower()]
                    break

        credit_col = found.get('credit')
        subject_col = found.get('subject')
        gpa_col = found.get('gpa')
        year_col = found.get('year')
        sem_col = found.get('sem')

        if not subject_col or (not credit_col and not gpa_col):
            continue

        buffer_name = ""  # 緩衝：存放前一行不完整課名
        for _, row in df.iterrows():
            data = {c: normalize_text(row[c]) if pd.notna(row[c]) else "" for c in df.columns}
            subj_raw = data.get(subject_col, "")
            cred_text = data.get(credit_col, "") if credit_col else ""
            gpa_text = data.get(gpa_col, "") if gpa_col else ""

            cred, gpa = parse_credit_and_gpa(cred_text)
            pc, pg = parse_credit_and_gpa(gpa_text)
            if pg:
                gpa = pg
            if pc > 0 and cred == 0:
                cred = pc

            # 檢視是否屬於完整課程
            complete = (
                cred > 0
                or is_passing_gpa(gpa)
                or cred_text.lower() in {"通過", "抵免"}
                or gpa_text.lower() in {"通過", "抵免"}
            )

            # 空行清除 buffer
            if all(not data.get(c, "") for c in [subject_col, credit_col, gpa_col] if c):
                buffer_name = ""
                continue

            if complete:
                # 只有當本行學分==0 時，才將 buffer_name 合併
                if buffer_name and cred == 0:
                    name = f"{buffer_name} {subj_raw}".strip()
                else:
                    name = subj_raw
                buffer_name = ""

                # 取學年度、學期
                acad = data.get(year_col, "")
                sem = data.get(sem_col, "")
                # 補抓學年或學期正則，可按需擴充

                record = {
                    "學年度": acad,
                    "學期": sem,
                    "科目名稱": name or "未知科目",
                    "學分": cred,
                    "GPA": gpa,
                    "來源表格": idx + 1
                }

                if gpa and not is_passing_gpa(gpa):
                    failed_courses.append(record)
                else:
                    total_credits += cred
                    calculated_courses.append(record)
            else:
                # 累到 buffer
                if subj_raw:
                    buffer_name = (buffer_name + " " + subj_raw).strip() if buffer_name else subj_raw

        # page 結束後若 buffer 未清，警告
        if buffer_name:
            import streamlit as st
            st.warning(f"表格{idx+1}殘留科目名稱「{buffer_name}」，已跳過")

    return total_credits, calculated_courses, failed_courses
