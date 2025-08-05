# utils/pdf_processing.py
import streamlit as st
import pandas as pd
import pdfplumber
import collections
import re

def normalize_text(cell_content):
    """
    標準化從 pdfplumber 提取的單元格內容。
    處理 None 值、pdfplumber 的 Text 物件和普通字串。
    將多個空白字元（包括換行）替換為單個空格，並去除兩端空白。
    """
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
    """
    將列表中的欄位名稱轉換為唯一的名稱，處理重複和空字串。
    如果遇到重複或空字串，會添加後綴 (例如 'Column_1', '欄位_2')。
    """
    seen = collections.defaultdict(int)
    unique_columns = []
    for col in columns_list:
        original_col_cleaned = normalize_text(col)
        
        # 對於空字串或過短的字串，使用 'Column_X' 格式 
        if not original_col_cleaned or len(original_col_cleaned) < 2: 
            name_base = "Column"
            # 確保生成的 Column_X 是在 unique_columns 中唯一的
            current_idx = 1
            while f"{name_base}_{current_idx}" in unique_columns:
                current_idx += 1
            name = f"{name_base}_{current_idx}"
        else:
            name = original_col_cleaned
        
        # 處理名稱本身的重複
        final_name = name
        counter = seen[name]
        # 如果當前生成的名稱已經存在於 unique_columns 中，則添加後綴
        while final_name in unique_columns:
            counter += 1
            final_name = f"{name}_{counter}" 
        
        unique_columns.append(final_name)
        seen[name] = counter # 更新該基礎名稱的最大計數

    return unique_columns

def is_grades_table(df):
    """
    判斷一個 DataFrame 是否為有效的成績單表格。
    透過檢查是否存在預期的欄位關鍵字和數據內容模式來判斷。
    （此函數需要 parse_credit_and_gpa，因此如果 parse_credit_and_gpa 移出，需要在此處導入）
    """
    if df.empty or len(df.columns) < 3:
        return False

    # 將欄位名稱轉換為小寫並去除空白，以便進行不區分大小寫的匹配
    normalized_columns = [re.sub(r'\s+', '', col).lower() for col in df.columns.tolist()]
    
    # 定義判斷成績表格的核心關鍵字
    credit_keywords = ["學分", "credits", "credit", "學分數"]
    gpa_keywords = ["gpa", "成績", "grade", "gpa(數值)"] 
    subject_keywords = ["科目名稱", "課程名稱", "coursename", "subjectname", "科目", "課程"]
    year_keywords = ["學年", "year"]
    semester_keywords = ["學期", "semester"]

    # 步驟1: 檢查明確的表頭關鍵字匹配
    has_credit_col_header = any(any(k in col for k in credit_keywords) for col in normalized_columns)
    has_gpa_col_header = any(any(k in col for k in gpa_keywords) for col in normalized_columns)
    has_subject_col_header = any(any(k in col for k in subject_keywords) for col in normalized_columns)
    has_year_col_header = any(any(k in col for k in year_keywords) for col in normalized_columns)
    has_semester_col_header = any(any(k in col for k in semester_keywords) for col in normalized_columns)

    if has_subject_col_header and (has_credit_col_header or has_gpa_col_header) and has_year_col_header and has_semester_col_header:
        return True
    
    # 步驟2: 如果沒有明確表頭匹配，則檢查數據行的內容模式 (更具彈性)
    potential_subject_cols = []
    potential_credit_gpa_cols = []
    potential_year_cols = []
    potential_semester_cols = []

    sample_rows_df = df.head(min(len(df), 20)) 

    from .grade_analysis import parse_credit_and_gpa # 局部導入，避免循環依賴

    for col_name in df.columns:
        sample_data = sample_rows_df[col_name].apply(normalize_text).tolist()
        total_sample_count = len(sample_data)
        if total_sample_count == 0:
            continue

        subject_like_cells = sum(1 for item_str in sample_data 
                                 if re.search(r'[\u4e00-\u9fa5]', item_str) and len(item_str) >= 2
                                 and not item_str.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', item_str)
                                 and not item_str.lower() in ["通過", "抵免", "pass", "exempt"])
        if subject_like_cells / total_sample_count >= 0.4:
            potential_subject_cols.append(col_name)

        credit_gpa_like_cells = 0
        for item_str in sample_data:
            credit_val, gpa_val = parse_credit_and_gpa(item_str)
            if (0.0 < credit_val <= 10.0) or (gpa_val and re.match(r'^[A-Fa-f][+\-]?$', gpa_val)) or (item_str.lower() in ["通過", "抵免", "pass", "exempt"]):
                credit_gpa_like_cells += 1
        if credit_gpa_like_cells / total_sample_count >= 0.4:
            potential_credit_gpa_cols.append(col_name)

        year_like_cells = sum(1 for item_str in sample_data 
                                  if (item_str.isdigit() and (len(item_str) == 3 or len(item_str) == 4)))
        if year_like_cells / total_sample_count >= 0.6:
            potential_year_cols.append(col_name)

        semester_like_cells = sum(1 for item_str in sample_data 
                                  if item_str.lower() in ["上", "下", "春", "夏", "秋", "冬", "1", "2", "3", "春季", "夏季", "秋季", "冬季", "spring", "summer", "fall", "winter"])
        if semester_like_cells / total_sample_count >= 0.6:
            potential_semester_cols.append(col_name)

    if potential_subject_cols and potential_credit_gpa_cols and potential_year_cols and potential_semester_cols:
        return True

    return False

def process_pdf_file(uploaded_file):
    """
    使用 pdfplumber 處理上傳的 PDF 檔案，提取表格。
    此函數內部將減少 Streamlit 的直接輸出，只返回提取的數據。
    """
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
                        st.info(f"頁面 **{page_num + 1}** 未偵測到表格。這可能是由於 PDF 格式複雜或表格提取設定不適用。")
                        continue

                    for table_idx, table in enumerate(tables):
                        processed_table = []
                        for row in table:
                            normalized_row = [normalize_text(cell) for cell in row]
                            if any(cell.strip() != "" for cell in normalized_row):
                                processed_table.append(normalized_row)
                        
                        if not processed_table:
                            st.info(f"頁面 {page_num + 1} 的表格 **{table_idx + 1}** 提取後為空。")
                            continue

                        if len(processed_table) > 0 and len(processed_table[0]) >= 3: 
                            header_row = processed_table[0]
                            data_rows = processed_table[1:]
                        else:
                            st.info(f"頁面 {page_num + 1} 的表格 {table_idx + 1} 結構不完整或行數不足，已跳過。")
                            continue

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
                                    st.success(f"頁面 {page_num + 1} 的表格 {table_idx + 1} 已識別為成績單表格並已處理。")
                                else:
                                    st.info(f"頁面 {page_num + 1} 的表格 {table_idx + 1} (表頭範例: {header_row}) 未識別為成績單表格，已跳過。")
                            except Exception as e_df:
                                st.error(f"頁面 {page_num + 1} 表格 {table_idx + 1} 轉換為 DataFrame 時發生錯誤: `{e_df}`")
                                st.error(f"原始處理後數據範例: {processed_table[:2]} (前兩行)")
                                st.error(f"生成的唯一欄位名稱: {unique_columns}")
                        else:
                            st.info(f"頁面 {page_num + 1} 的表格 **{table_idx + 1}** 沒有數據行。")

                except Exception as e_table:
                    st.error(f"頁面 **{page_num + 1}** 處理表格時發生錯誤: `{e_table}`")
                    st.warning("這可能是由於 PDF 格式複雜或表格提取設定不適用。請檢查 PDF 結構。")

    except pdfplumber.PDFSyntaxError as e_pdf_syntax:
        st.error(f"處理 PDF 語法時發生錯誤: `{e_pdf_syntax}`。檔案可能已損壞或格式不正確。")
    except Exception as e:
        st.error(f"處理 PDF 檔案時發生一般錯誤: `{e}`")
        st.error("請確認您的 PDF 格式是否為清晰的表格。若問題持續，可能是 PDF 結構較為複雜，需要調整 `pdfplumber` 的表格提取設定。")

    return all_grades_data
