# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    gpa_clean = normalize_text(gpa_str).upper()
    failing = ["D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"]
    if not gpa_clean:
        return False
    if gpa_clean in ["通過", "抵免", "PASS", "EXEMPT"]:
        return True
    if gpa_clean in failing:
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

    # 關鍵字列表
    credit_keys = ["學分", "學分數", "學分(GPA)", "credits", "credit"]
    subject_keys = ["科目名稱", "課程名稱", "course name", "subject"]
    gpa_keys     =
