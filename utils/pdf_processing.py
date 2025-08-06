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
    # collapse all whitespace (incl. newlines) to single space
    return re.sub(r"\s+", " ", text).strip()

def make_unique_columns(columns_list):
    seen = collections.defaultdict(int)
    unique = []
    for col in columns_list:
        name = normalize_text(col)
        if not name or len(name) < 2:
            base = "Column"
            idx = 1
            while f"{base}_{idx}" in unique:
                idx += 1
            name = f"{base}_{idx}"
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
    cols = [re.sub(r"\s+", "", c).lower() for c in df.columns]
    return (
        any("科目" in c or "subject" in c for c in cols)
        and (any("學分" in c or "credit" in c for c in cols)
             or any("gpa" in c or "成績" in c for c in cols))
        and any("學年" in c or "year" in c for c in cols)
        and any("學期" in c or "semester" in c for c in cols)
    )

def process_pdf_file(uploaded_file):
    """
    1) 先用 extract_tables 把所有识别为成绩表的 DataFrame 收集到 list
    2) 同时合并全文到 full_text
    3) 全表格抽取后，再对 full_text 运行 Regex fallback
       - 如果 Regex 能抓到任何记录，就返回单个 DataFrame（优先）
       - 否则返回表格抽取得到的 list of DataFrame
    """
    table_dfs = []
    full_text = ""

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                # 1) 累积全文
                txt = page.extract_text() or ""
                full_text += normalize_text(txt) + "\n"

                # 2) 表格抽取
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
                    except Exception:
                        continue

        # 3) Regex fallback：只要能匹配到完整记录，就用它的结果覆盖表格抽取
        pattern = re.compile(
            r"(\d{3,4})\s*(上|下|春|夏|秋|冬)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+([A-F][+\-]?|通過|抵免)",
            re.UNICODE
        )
        matches = pattern.findall(full_text)
        if matches:
            all_rows = []
            for year, sem, subj, cred, gpa in matches:
                # subj 已经是 normalize_text 后的单行
                all_rows.append([year, sem, normalize_text(subj), cred, gpa])
            regex_df = pd.DataFrame(
                all_rows, columns=["學年度", "學期", "科目名稱", "學分", "GPA"]
            )
            st.success("Regex fallback 已處理整份 PDF，优先返回此部分结果。")
            return [regex_df]

    except pdfplumber.PDFSyntaxError as e:
        st.error(f"PDF 语法错误: {e}")
    except Exception as e:
        st.error(f"处理 PDF 时发生错误: {e}")

    # 若 Regex 没匹配到任何记录，就回归表格抽取结果
    return table_dfs
