# utils/pdf_processing.py

import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re

def normalize_text(cell_content):
    if cell_content is None:
        return ""
    if hasattr(cell_content, "text"):
        text = str(cell_content.text)
    elif isinstance(cell_content, str):
        text = cell_content
    else:
        text = str(cell_content)
    return re.sub(r"\s+", " ", text).strip()

def make_unique_columns(columns_list):
    seen = collections.defaultdict(int)
    unique = []
    for col in columns_list:
        name = normalize_text(col)
        if len(name) < 2:
            base = "Column"
            i = 1
            while f"{base}_{i}" in unique:
                i += 1
            name = f"{base}_{i}"
        final = name
        cnt = seen[name]
        while final in unique:
            cnt += 1
            final = f"{name}_{cnt}"
        unique.append(final)
        seen[name] = cnt
    return unique

def is_grades_table(df):
    if df.empty or df.shape[1] < 3:
        return False
    low = [re.sub(r"\s+", "", c).lower() for c in df.columns]
    return (
        any("科目" in c or "subject" in c for c in low) and
        (any("學分" in c or "credit" in c for c in low) or any("gpa" in c or "成績" in c for c in low)) and
        any("學年" in c or "year" in c for c in low) and
        any("學期" in c or "semester" in c for c in low)
    )

def process_pdf_file(uploaded_file):
    table_dfs = []
    full_text = ""

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                txt = page.extract_text() or ""
                full_text += normalize_text(txt) + "\n"

                settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 5,
                    "edge_min_length": 3,
                    "text_tolerance": 2,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                }
                tables = page.extract_tables(settings)
                if not tables:
                    continue

                for tbl_idx, table in enumerate(tables):
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
                            cleaned.append(r[: len(cols)])
                        elif len(r) < len(cols):
                            cleaned.append(r + [""] * (len(cols) - len(r)))
                        else:
                            cleaned.append(r)

                    try:
                        df = pd.DataFrame(cleaned, columns=cols)
                        if is_grades_table(df):
                            table_dfs.append(df)
                            st.success(f"頁面 {page_idx+1} 表格 {tbl_idx+1} 已處理")
                    except:
                        continue

        # 无论是否有 table_dfs，都尝试一次 Regex fallback，补全漏掉的课程
        pattern = re.compile(
            r"(\d{3,4})\s*(上|下|春|夏|秋|冬)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+([A-F][+\-]?|通過|抵免)",
            re.UNICODE
        )
        matches = pattern.findall(full_text)
        if matches:
            all_rows = []
            for year, sem, subj, cred, gpa in matches:
                all_rows.append([
                    year,
                    sem,
                    normalize_text(subj),
                    cred,
                    gpa
                ])
            regex_df = pd.DataFrame(
                all_rows,
                columns=["學年度", "學期", "科目名稱", "學分", "GPA"]
            )
            st.info("⚡ Regex fallback 補全課程資料")
            # 把 regex_df 插到列表最後，calculate_total_credits 会去重
            table_dfs.append(regex_df)

    except pdfplumber.PDFSyntaxError as e:
        st.error(f"PDF 語法錯誤: {e}")
    except Exception as e:
        st.error(f"處理 PDF 時發生錯誤: {e}")

    return table_dfs
