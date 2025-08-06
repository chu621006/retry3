# utils/grade_analysis.py

import pandas as pd
import re
# 把 normalize_text 改为从 pdf_processing 导入 normalize，重命名为 normalize_text
from .pdf_processing import normalize as normalize_text

def is_passing_gpa(gpa_str):
    """
    判斷給定的 GPA 字串是否為通過成績。
    """
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
        except:
            pass
    return False

def parse_credit_and_gpa(text):
    """
    從單元格文本中解析學分和 GPA。
    返回 (學分, GPA)。
    """
    text_clean = normalize_text(text)
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]:
        return 0.0, text_clean
    m1 = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if m1:
        return float(m1.group(2)), m1.group(1).upper()
    m2 = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', text_clean)
    if m2:
        return float(m2.group(1)), m2.group(3).upper()
    m3 = re.search(r'(\d+(\.\d+)?)', text_clean)
    if m3:
        return float(m3.group(1)), ""
    m4 = re.search(r'([A-Fa-f][+\-]?)', text_clean)
    if m4:
        return 0.0, m4.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    for idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        # 嘗試找到這幾個欄位
        def find_col(keywords):
            for c in df.columns:
                for k in keywords:
                    if k.lower() in re.sub(r'\s+', '', c).lower():
                        return c
            return None

        col_subj = find_col(["科目名稱", "課程名稱", "subject"])
        col_credit = find_col(["學分", "credit"])
        col_gpa = find_col(["gpa", "成績"])
        col_year = find_col(["學年", "year"])
        col_sem = find_col(["學期", "semester"])

        if not col_subj or not col_credit:
            continue

        for _, row in df.iterrows():
            subj = normalize_text(row.get(col_subj, ""))
            credit_txt = normalize_text(row.get(col_credit, ""))
            gpa_txt = normalize_text(row.get(col_gpa, "")) if col_gpa else ""
            credit, gpa = parse_credit_and_gpa(credit_txt + " " + gpa_txt)

            # 判斷不及格
            if gpa and not is_passing_gpa(gpa):
                failed_courses.append({
                    "學年度": normalize_text(row.get(col_year, "")),
                    "學期": normalize_text(row.get(col_sem, "")),
                    "科目名稱": subj or "未知科目",
                    "學分": credit,
                    "GPA": gpa,
                    "來源表格": idx+1
                })
            elif credit > 0 or is_passing_gpa(gpa):
                total_credits += credit
                calculated_courses.append({
                    "學年度": normalize_text(row.get(col_year, "")),
                    "學期": normalize_text(row.get(col_sem, "")),
                    "科目名稱": subj or "未知科目",
                    "學分": credit,
                    "GPA": gpa,
                    "來源表格": idx+1
                })

    return total_credits, calculated_courses, failed_courses
