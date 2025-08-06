# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    gpa_clean = normalize_text(gpa_str).upper()
    failing_grades = ["D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"]
    if not gpa_clean:
        return False
    if gpa_clean in ["通過", "抵免", "PASS", "EXEMPT"]:
        return True
    if gpa_clean in failing_grades:
        return False
    if re.match(r'^[A-C][+\-]?$', gpa_clean):
        return True
    if gpa_clean.replace('.', '', 1).isdigit():
        try:
            return float(gpa_clean) >= 60.0
        except ValueError:
            pass
    return False

def parse_credit_and_gpa(text):
    text_clean = normalize_text(text)
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]:
        return 0.0, text_clean
    m = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if m:
        return float(m.group(2)), m.group(1).upper()
    m = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', text_clean)
    if m:
        return float(m.group(1)), m.group(3).upper()
    m = re.search(r'(\d+(\.\d+)?)', text_clean)
    if m:
        return float(m.group(1)), ""
    m = re.search(r'([A-Fa-f][+\-]?)', text_clean)
    if m:
        return 0.0, m.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    # 欄位關鍵字設定
    credit_keys = ["學分", "學分數", "學分(GPA)", "學 分", "credits", "credit"]
    subject_keys = ["科目名稱", "課程名稱", "course name", "subject", "科目", "課程"]
    gpa_keys     = ["GPA", "成績", "grade"]
    year_keys    = ["學年", "year"]
    sem_keys     = ["學期", "semester"]

    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        # 尋找各欄位名稱
        cols = {re.sub(r'\s+', '', c).lower(): c for c in df.columns}
        found = {}
        for key_list, name in [(credit_keys, 'credit'),
                               (subject_keys, 'subject'),
                               (gpa_keys,     'gpa'),
                               (year_keys,    'year'),
                               (sem_keys,     'sem')]:
            for k in key_list:
                if k.lower() in cols:
                    found[name] = cols[k.lower()]
                    break

        subject_col = found.get('subject')
        credit_col  = found.get('credit')
        gpa_col     = found.get('gpa')
        year_col    = found.get('year')
        sem_col     = found.get('sem')

        if not subject_col or (not credit_col and not gpa_col):
            continue

        buffer_row = None
        for _, row in df.iterrows():
            rd = {c: normalize_text(row[c]) if pd.notna(row[c]) else "" for c in df.columns}
            subj = rd.get(subject_col, "")
            cred_txt = rd.get(credit_col, "") if credit_col else ""
            gpa_txt  = rd.get(gpa_col, "")    if gpa_col else ""

            cred, gpa = parse_credit_and_gpa(cred_txt)
            pc, pg = parse_credit_and_gpa(gpa_txt)
            if pg:
                gpa = pg
            if pc and not cred:
                cred = pc

            is_complete = (
                cred > 0
                or is_passing_gpa(gpa)
                or cred_txt.lower() in ["通過", "抵免"]
                or gpa_txt.lower() in ["通過", "抵免"]
            )

            if is_complete:
                # 合併 buffer
                if buffer_row:
                    subj_full = (buffer_row['科目名稱'] + " " + subj).strip()
                    acad_year = buffer_row['學年度'] or rd.get(year_col, "")
                    semester  = buffer_row['學期']   or rd.get(sem_col, "")
                else:
                    subj_full = subj
                    acad_year = rd.get(year_col, "")
                    semester  = rd.get(sem_col, "")

                record = {
                    "學年度": acad_year,
                    "學期": semester,
                    "科目名稱": subj_full or "未知科目",
                    "學分": cred,
                    "GPA": gpa,
                    "來源表格": df_idx + 1
                }
                if gpa and not is_passing_gpa(gpa):
                    failed_courses.append(record)
                elif cred > 0 or is_passing_gpa(gpa):
                    total_credits += cred
                    calculated_courses.append(record)
                buffer_row = None
            else:
                # 累積到 buffer
                if buffer_row:
                    buffer_row['科目名稱'] += " " + subj
                else:
                    buffer_row = {
                        "科目名稱": subj,
                        "學年度":   rd.get(year_col, ""),
                        "學期":     rd.get(sem_col, "")
                    }

        # 若最後還有 buffer，跳過並顯警告
        if buffer_row and buffer_row['科目名稱'].strip():
            import streamlit as st
            st.warning(
                f"表格{df_idx+1}偵測到未完成的科目名稱「{buffer_row['科目名稱']}」，已跳過"
            )

    return total_credits, calculated_courses, failed_courses
