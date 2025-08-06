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
            numeric_gpa = float(gpa_clean)
            return numeric_gpa >= 60.0
        except ValueError:
            pass
    return False

def parse_credit_and_gpa(text):
    text_clean = normalize_text(text)
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]:
        return 0.0, text_clean
    match_gpa_credit = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if match_gpa_credit:
        gpa = match_gpa_credit.group(1).upper()
        try:
            credit = float(match_gpa_credit.group(2))
            return credit, gpa
        except ValueError:
            pass
    match_credit_gpa = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', text_clean)
    if match_credit_gpa:
        try:
            credit = float(match_credit_gpa.group(1))
            gpa = match_credit_gpa.group(3).upper()
            return credit, gpa
        except ValueError:
            pass
    credit_only_match = re.search(r'(\d+(\.\d+)?)', text_clean)
    if credit_only_match:
        try:
            credit = float(credit_only_match.group(1))
            return credit, ""
        except ValueError:
            pass
    gpa_only_match = re.search(r'([A-Fa-f][+\-]?)', text_clean)
    if gpa_only_match:
        return 0.0, gpa_only_match.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    credit_column_keywords = ["學分", "學分數", "學分(GPA)", "學 分", "Credits", "Credit", "學分數(學分)"]
    subject_column_keywords = ["科目名稱", "課程名稱", "Course Name", "Subject Name", "科目", "課程"]
    gpa_column_keywords = ["GPA", "成績", "Grade", "gpa(數值)"]
    year_column_keywords = ["學年", "year", "學 年"]
    semester_column_keywords = ["學期", "semester", "學 期"]

    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        found_credit_column = None
        found_subject_column = None
        found_gpa_column = None
        found_year_column = None
        found_semester_column = None

        normalized_df_columns = {re.sub(r'\s+', '', col_name).lower(): col_name for col_name in df.columns}
        for k in credit_column_keywords:
            if k in normalized_df_columns:
                found_credit_column = normalized_df_columns[k]
                break
        for k in subject_column_keywords:
            if k in normalized_df_columns:
                found_subject_column = normalized_df_columns[k]
                break
        for k in gpa_column_keywords:
            if k in normalized_df_columns:
                found_gpa_column = normalized_df_columns[k]
                break
        for k in year_column_keywords:
            if k in normalized_df_columns:
                found_year_column = normalized_df_columns[k]
                break
        for k in semester_column_keywords:
            if k in normalized_df_columns:
                found_semester_column = normalized_df_columns[k]
                break

        # 動態推測欄位的部分略去，保留你的自動判斷
        # ...

        # 【核心修正點】跨行課名自動合併（允許多次 buffer 疊加）
        buffer_row = None
        for row_idx, row in df.iterrows():
            row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}
            subject_raw = row_data.get(found_subject_column, "")
            credit_col = row_data.get(found_credit_column, "")
            gpa_col = row_data.get(found_gpa_column, "")

            # 提取學分和GPA
            credit, gpa = parse_credit_and_gpa(credit_col)
            parsed_credit_gpa_col, parsed_gpa_gpa_col = parse_credit_and_gpa(gpa_col)
            if parsed_gpa_gpa_col:
                gpa = parsed_gpa_gpa_col.upper()
            if parsed_credit_gpa_col > 0 and credit == 0.0:
                credit = parsed_credit_gpa_col

            # 判斷當前這一行是不是一筆完整課程資料
            is_complete_row = (
                credit > 0 or is_passing_gpa(gpa)
                or normalize_text(credit_col).lower() in ["通過", "抵免", "pass", "exempt"]
                or normalize_text(gpa_col).lower() in ["通過", "抵免", "pass", "exempt"]
            )

            # 合併多行課名邏輯（buffer 疊加）
            if is_complete_row:
                # 若之前有 buffer_row，合併科目名稱
                if buffer_row:
                    subject_full = buffer_row.get("科目名稱", "") + " " + subject_raw
                    subject_full = subject_full.strip()
                    # 取 buffer 的學年/學期（若有），否則取當前
                    acad_year = buffer_row.get("學年度") or row_data.get(found_year_column, "")
                    semester = buffer_row.get("學期") or row_data.get(found_semester_column, "")
                    # 只用這一行的學分/GPA
                else:
                    subject_full = subject_raw
                    acad_year = row_data.get(found_year_column, "")
                    semester = row_data.get(found_semester_column, "")
                # 存入結果
                record = {
                    "學年度": acad_year,
                    "學期": semester,
                    "科目名稱": subject_full,
                    "學分": credit,
                    "GPA": gpa,
                    "來源表格": df_idx + 1
                }
                if gpa and not is_passing_gpa(gpa):
                    failed_courses.append(record)
                elif credit > 0 or is_passing_gpa(gpa):
                    if credit > 0:
                        total_credits += credit
                    calculated_courses.append(record)
                buffer_row = None  # 清空 buffer
            else:
                # 疊加 buffer，直到遇到完整一筆再處理
                if buffer_row:
                    # 疊加上去
                    new_subject = buffer_row.get("科目名稱", "") + " " + subject_raw
                    buffer_row["科目名稱"] = new_subject.strip()
                    # 學年、學期只用 buffer 最早的
                else:
                    buffer_row = {
                        "科目名稱": subject_raw,
                        "學年度": row_data.get(found_year_column, ""),
                        "學期": row_data.get(found_semester_column, "")
                    }
        # 處理最後一筆可能剩餘的 buffer_row
        if buffer_row and buffer_row.get("科目名稱"):
            import streamlit as st
            st.warning(f"表格 {df_idx+1} 檢測到未完成的科目名稱：'{buffer_row['科目名稱']}'，由於缺乏學分/GPA，已跳過。")

    return total_credits, calculated_courses, failed_courses

