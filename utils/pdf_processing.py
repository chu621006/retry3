# utils/pdf_processing.py
import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re

def normalize_text(cell_content):
    if cell_content is None:
        return ""
    text = ""
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
        original_col_cleaned = normalize_text(col)
        if not original_col_cleaned or len(original_col_cleaned) < 2:
            name_base = "Column"
            current_idx = 1
            while f"{name_base}_{current_idx}" in unique_columns:
                current_idx += 1
            name = f"{name_base}_{current_idx}"
        else:
            name = original_col_cleaned
        final_name = name
        counter = seen[name]
        while final_name in unique_columns:
            counter += 1
            final_name = f"{name}_{counter}"
        unique_columns.append(final_name)
        seen[name] = counter
    return unique_columns

def is_grades_table(df):
    if df.empty or len(df.columns) < 3:
        return False
    normalized_columns = [re.sub(r'\s+', '', col).lower() for col in df.columns.tolist()]
    credit_keywords = ["學分", "credits", "credit", "學分數"]
    gpa_keywords = ["gpa", "成績", "grade", "gpa(數值)"]
    subject_keywords = ["科目名稱", "課程名稱", "coursename", "subjectname", "科目", "課程"]
    year_keywords = ["學年", "year"]
    semester_keywords = ["學期", "semester"]
    has_credit_col_header = any(any(k in col for k in credit_keywords) for col in normalized_columns)
    has_gpa_col_header = any(any(k in col for k in gpa_keywords) for col in normalized_columns)
    has_subject_col_header = any(any(k in col for k in subject_keywords) for col in normalized_columns)
    has_year_col_header = any(any(k in col for k in year_keywords) for col in normalized_columns)
    has_semester_col_header = any(any(k in col for k in semester_keywords) for col in normalized_columns)
    if has_subject_col_header and (has_credit_col_header or has_gpa_col_header) and has_year_col_header and has_semester_col_header:
        return True
    # ...下方內容維持原本
    # 保持你原本的動態推測即可

def process_pdf_file(uploaded_file):
    all_grades_data = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                current_page = page
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
                try:
                    tables = current_page.extract_tables(table_settings)
                    if not tables:
                        # 新增：「若無表格」則用全頁純文字，試著補抓第一筆
                        raw_text = current_page.extract_text()
                        if raw_text:
                            lines = [normalize_text(line) for line in raw_text.splitlines() if line.strip()]
                            # 檢查行內是否有「學分」數字、「GPA」或「成績」關鍵字
                            # 這裡建議只做簡單收集，詳細判斷交給後續分析
                            st.info(f"頁面 {page_num+1} 未偵測到表格，僅抓取全頁文字供備用。")
                        continue
                    for table_idx, table in enumerate(tables):
                        processed_table = []
                        for row in table:
                            normalized_row = [normalize_text(cell) for cell in row]
                            if any(cell.strip() != "" for cell in normalized_row):
                                processed_table.append(normalized_row)
                        if not processed_table:
                            st.info(f"頁面 {page_num+1} 的表格 {table_idx+1} 提取後為空。")
                            continue
                        # 【修正點】如果第一行被誤判為標題，但其實就是課程資料，也一併納入資料行
                        header_row = processed_table[0]
                        data_rows = processed_table[1:] if len(processed_table) > 1 else []
                        # 若 data_rows 全部不含關鍵字，而 header_row 明顯是資料，也補進去
                        keywords = ["學分", "GPA", "成績", "分", "grade"]
                        if not any(any(k in h for k in keywords) for h in header_row):
                            # header 不是標題，直接當資料行
                            data_rows = [header_row] + data_rows
                            header_row = [f"Column_{i+1}" for i in range(len(header_row))]
                        unique_columns = make_unique_columns(header_row)
                        if data_rows:
                            num_columns_header = len(unique_columns)
                            cleaned_data_rows = []
                            for row in data_rows:
                                if len(row) > num_columns_header:
                                    cleaned_data_rows.append(row[:num_columns_header])
                                elif len(row) < num_columns_header:
                                    cleaned_data_rows.append(row + [''] * (num_columns_header - len(row)))
                                else:
                                    cleaned_data_rows.append(row)
                            try:
                                df_table = pd.DataFrame(cleaned_data_rows, columns=unique_columns)
                                if is_grades_table(df_table):
                                    all_grades_data.append(df_table)
                                    st.success(f"頁面 {page_num+1} 的表格 {table_idx+1} 已識別為成績單表格並已處理。")
                                else:
                                    st.info(f"頁面 {page_num+1} 的表格 {table_idx+1} (表頭: {header_row}) 未識別為成績單表格，已跳過。")
                            except Exception as e_df:
                                st.error(f"頁面 {page_num+1} 表格 {table_idx+1} 轉換 DataFrame 錯誤: `{e_df}`")
                        else:
                            st.info(f"頁面 {page_num+1} 的表格 {table_idx+1} 沒有數據行。")
                except Exception as e_table:
                    st.error(f"頁面 {page_num+1} 處理表格時發生錯誤: `{e_table}`")
    except pdfplumber.PDFSyntaxError as e_pdf_syntax:
        st.error(f"處理 PDF 語法時發生錯誤: `{e_pdf_syntax}`")
    except Exception as e:
        st.error(f"處理 PDF 檔案時發生錯誤: `{e}`")
    return all_grades_data
