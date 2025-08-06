# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    return False  # 目前 debug 先固定回傳 False

def parse_credit_and_gpa(text):
    return 0.0, ""  # 目前 debug 先固定回傳 0 和空字串

def calculate_total_credits(df_list):
    print("【DEBUG】這是目前正確的 grade_analysis.py 被呼叫")
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []
    print("【DEBUG】即將 return 3 個值")
    return total_credits, calculated_courses, failed_courses
