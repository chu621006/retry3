# utils/pdf_processing.py

import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re
from .grade_analysis import parse_credit_and_gpa  # 用到 normalize_text、parse_credit_and_gpa

def normalize_text(cell_content):
    if cell_content is None:
        return ""
    if hasattr(cell_content, 'text'):
        text = str(cell_content.text)
    elif isinstance(cell_content, str):
        text = cell_content
    else:
        text = str(cell_content)
    return re.sub(r'\s+', ' ', text).strip()

def make_unique_columns(columns_list):
    seen = collections.defaultdict(int)
    unique_columns = []
    for col in columns_list:
        original = normalize_text(col)
        if not original or len(original) < 2:
            base = "Column"
            idx = 1
            while f"{base}_{idx}" in unique_columns:
                idx += 1
            name = f"{base}_{idx}"
        else:
            name = original
        final = name
        cnt = seen[name]
        while final in unique_columns:
            cnt += 1
            final = f"{name}_{cnt}"
        unique_columns.append(final)
        seen[name] = cnt
    return unique_columns

def is_grades_table(df):
    # (保持你原本的判斷邏輯)
    if df.empty or len(df.columns) < 3:
        return False
    normalized_columns = [re.sub(r'\s+', '', c).lower() for c in df.columns]
    credit_kw = ["學分", "credit"]
    gpa_kw    = ["gpa", "成績", "grade"]
    subject_kw= ["科目名稱", "課程名稱", "subject", "course"]
    year_kw   = ["學年", "year"]
    sem_kw    = ["學期", "semester"]

    has_credit = any(any(k in c for k in credit_kw) for c in normalized_columns)
    has_gpa    = any(any(k in c for k in gpa_kw)    for c in normalized_columns)
    has_subj   = any(any(k in c for k in subject_kw)for c in normalized_columns)
    has_year   = any(any(k in c for k in year_kw)   for c in normalized_columns)
    has_sem    = any(any(k in c for k in sem_kw)    for c in normalized_columns)

    return has_subj and (has_credit or has_gpa) and has_year and has_sem

def process_pdf_file(uploaded_file):
    all_grades_data = []

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 5,
                    "edge_min_length": 3,
                    "text_tolerance": 2,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                }

                # 嘗試用 extract_tables
                tables = page.extract_tables(table_settings)
                if tables:
                    for tidx, table in enumerate(tables):
                        # 清洗 table
                        rows = []
                        for row in table:
                            norm = [normalize_text(c) for c in row]
                            if any(cell for cell in norm):
                                rows.append(norm)
                        if not rows or len(rows[0]) < 3:
                            continue
                        header, data_rows = rows[0], rows[1:]
                        cols = make_unique_columns(header)
                        cleaned = []
                        for r in data_rows:
                            if len(r) > len(cols):
                                cleaned.append(r[:len(cols)])
                            elif len(r) < len(cols):
                                cleaned.append(r + [""] * (len(cols) - len(r)))
                            else:
                                cleaned.append(r)
                        try:
                            df = pd.DataFrame(cleaned, columns=cols)
                            if is_grades_table(df):
                                all_grades_data.append(df)
                                st.success(f"頁面 {page_num+1} 的表格 {tidx+1} 已識別並處理。")
                        except Exception:
                            continue
                else:
                    # fallback: 純文字解析學年度/學期/科目/學分/GPA
                    text = page.extract_text()
                    if text and "學年度" in text and "GPA" in text:
                        # 逐行分割
                        lines = [normalize_text(l) for l in text.splitlines() if normalize_text(l)]
                        # 找到 header 行
                        for idx, line in enumerate(lines):
                            if re.search(r'學年度.*學分.*GPA', line):
                                hdr = re.split(r'\s{2,}', line)
                                data = []
                                for row in lines[idx+1:]:
                                    # 一般 data 行會以學年度開頭 (3或4位數)
                                    if not re.match(r'^\d{3,4}\s', row):
                                        break
                                    parts = re.split(r'\s{2,}', row)
                                    if len(parts) >= len(hdr):
                                        data.append(parts[:len(hdr)])
                                if data:
                                    cols = make_unique_columns(hdr)
                                    df = pd.DataFrame(data, columns=cols)
                                    all_grades_data.append(df)
                                    st.success(f"頁面 {page_num+1} 純文字解析已處理。")
                                break
    except pdfplumber.PDFSyntaxError as e:
        st.error(f"PDF 語法錯誤: {e}")
    except Exception as e:
        st.error(f"處理 PDF 時發生錯誤: {e}")

    return all_grades_data
