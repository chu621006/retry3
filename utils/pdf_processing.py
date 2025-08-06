import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re

def normalize_text(cell_content):
    """
    将 pdfplumber 提取内容统一为纯文本，去除多余空白。
    """
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
    """
    将标题行变为唯一列名，处理重复和空白。
    """
    seen = collections.defaultdict(int)
    unique = []
    for col in columns_list:
        name = normalize_text(col)
        if len(name) < 2:
            name = f"Column_{len(unique)+1}"
        final = name
        cnt = seen[name]
        while final in unique:
            cnt += 1
            final = f"{name}_{cnt}"
        unique.append(final)
        seen[name] = cnt
    return unique

def is_grades_table(df):
    """
    简单判断一个 DataFrame 是否可能是成绩单：包含科目、学分/GPA、学年、学期等关键词。
    """
    if df.empty or df.shape[1] < 3:
        return False
    lc = [re.sub(r"\s+", "", c).lower() for c in df.columns]
    return (
        any("科目" in c or "subject" in c for c in lc)
        and (any("學分" in c or "credit" in c for c in lc)
             or any("gpa" in c or "成績" in c for c in lc))
        and any("學年" in c or "year" in c for c in lc)
        and any("學期" in c or "semester" in c for c in lc)
    )

def process_pdf_file(uploaded_file):
    """
    核心流程：
    1. 用 pdfplumber.extract_tables 提取所有页面的表格；
    2. 仅保留 is_grades_table 识别为成绩单的表格；
    3. 如果**完全没有**提取到任何表格，则用一次性 Regex fallback 全文抽课（保底）；
    4. **额外**在全文用第二个 Regex 再补一次“跨行长名课程”（不依赖表格结构）；
    5. 返回所有 DataFrame 列表。
    """
    table_dfs = []
    full_text = ""

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for pi, page in enumerate(pdf.pages):
                # 累积全文文本，用于后续 Regex fallback
                txt = page.extract_text() or ""
                full_text += normalize_text(txt) + "\n"

                # 表格抽取设置
                settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 5,
                    "edge_min_length": 3,
                    "text_tolerance": 2,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1
                }
                tables = page.extract_tables(settings)
                if not tables:
                    continue

                for ti, table in enumerate(tables):
                    # 归一化每行
                    rows = []
                    for row in table:
                        norm = [normalize_text(c) for c in row]
                        if any(norm):
                            rows.append(norm)
                    if not rows or len(rows[0]) < 3:
                        continue

                    header, data = rows[0], rows[1:]
                    cols = make_unique_columns(header)
                    cleaned = []
                    for r in data:
                        if len(r) > len(cols):
                            cleaned.append(r[:len(cols)])
                        elif len(r) < len(cols):
                            cleaned.append(r + [""] * (len(cols) - len(r)))
                        else:
                            cleaned.append(r)
                    try:
                        df = pd.DataFrame(cleaned, columns=cols)
                        if is_grades_table(df):
                            table_dfs.append(df)
                            st.success(f"頁面{pi+1} 表格{ti+1} 已處理")
                    except:
                        continue

        # ① 完全没提取到任何表格时，做一次性全文 Regex fallback
        if not table_dfs:
            pattern = re.compile(
                r"(\d{3,4})\s*(上|下|春|夏|秋|冬)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+([A-F][+\-]?|通過|抵免)",
                re.UNICODE
            )
            matches = pattern.findall(full_text)
            if matches:
                rows = []
                for y, s, subj, cr, g in matches:
                    rows.append([y, s, normalize_text(subj), cr, g])
                df_fallback = pd.DataFrame(
                    rows, columns=["學年度","學期","科目名稱","學分","GPA"]
                )
                st.info("⚡ Regex fallback 補全整份 PDF")
                return [df_fallback]

        # ② **额外**再用全文 Regex 抽一次“长名跨行课程”，补入一个单独的 DataFrame
        extra = []
        pattern2 = re.compile(
            r"([^0-9\n]{4,}?)\s*([0-9]+(?:\.\d+)?)\s+([A-F][+\-]?|通過|抵免)(?!\S)",
            re.UNICODE
        )
        for subj, cr, g in pattern2.findall(full_text):
            extra.append({
                "學年度": "",
                "學期": "",
                "科目名稱": normalize_text(subj).strip(),
                "學分": float(cr),
                "GPA": g,
                "來源表格": 0
            })
        if extra:
            df_extra = pd.DataFrame(extra)
            table_dfs.append(df_extra)

        return table_dfs

    except pdfplumber.PDFSyntaxError as e:
        st.error(f"PDF 語法錯誤: {e}")
    except Exception as e:
        st.error(f"處理 PDF 時出錯: {e}")

    return []
