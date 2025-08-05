# utils/pdf_processing.py
import pdfplumber
import pandas as pd
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
        if not col or col.isspace(): # 處理空字串或只包含空白的字串
            col = f"Column_{seen['']}"
            seen[''] += 1
        
        # 標準化欄位名稱，避免因為空白、大小寫等導致重複
        normalized_col = normalize_text(col).replace(" ", "_").lower()
        
        if normalized_col in seen:
            seen[normalized_col] += 1
            unique_columns.append(f"{col}_{seen[normalized_col]}")
        else:
            seen[normalized_col] = 0 # 將第一次出現的計數設為0，後續重複從1開始
            unique_columns.append(col)
    return unique_columns

def extract_tables_from_pdf(pdf_file):
    """
    從 PDF 文件中提取所有表格，並返回 DataFrame 列表。
    嘗試使用不同的 table_settings 來提高提取準確性。
    """
    dfs = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # 嘗試使用更精細的表格設定
                # 這裡增加了一些參數，特別是 snap_vertical 和 snap_horizontal
                # 讓 pdfplumber 更傾向於依賴偵測到的線條。
                # 'intersection_tolerance' 調整交集容忍度，有助於更準確地識別單元格
                # 'vertical_strategy': 'lines' 強制使用垂直線條來分割列
                # 'horizontal_strategy': 'lines' 強制使用水平線條來分割行
                table_settings = {
                    "vertical_strategy": "lines",  # 強制根據垂直線條來識別列
                    "horizontal_strategy": "lines", # 強制根據水平線條來識別行
                    "snap_tolerance": 5,           # 靠近線條的容忍度 (像素)
                    "snap_vertical": [l.x for l in page.lines if l.width == 0],  # 使用頁面中所有垂直線的x座標
                    "snap_horizontal": [l.y for l in page.lines if l.height == 0], # 使用頁面中所有水平線的y座標
                    "join_tolerance": 3,           # 合併相鄰單元格的容忍度
                    "edge_min_length": 3,          # 偵測到的線段最小長度
                    "min_words_vertical": 0,       # 垂直方向最少有多少個詞才算是一個獨立列
                    "min_words_horizontal": 0,     # 水平方向最少有多少個詞才算是一個獨立行
                    "intersection_tolerance": 6    # 交集點的容忍度，用於連接線段形成單元格
                }
                
                tables = page.extract_tables(table_settings=table_settings)
                
                for table in tables:
                    # 第一行通常是表頭
                    if not table or not table[0]:
                        continue
                    
                    header_row = [normalize_text(h) for h in table[0]]
                    data_rows = table[1:]
                    
                    # 檢查 header_row 是否全是空字串
                    if all(not h for h in header_row):
                        # 如果表頭為空，嘗試使用第一行數據作為表頭，或者生成默認表頭
                        if data_rows and any(normalize_text(cell) for cell in data_rows[0]):
                            header_row = [normalize_text(cell) for cell in data_rows[0]]
                            data_rows = data_rows[1:]
                        else:
                            # 仍然沒有有效表頭，生成默認欄位名
                            header_row = [f"Column_{i}" for i in range(len(table[0]))]

                    unique_headers = make_unique_columns(header_row)
                    
                    # 確保數據行的列數與表頭一致
                    processed_data = []
                    for row in data_rows:
                        if len(row) == len(unique_headers):
                            processed_data.append([normalize_text(cell) for cell in row])
                        elif len(row) > len(unique_headers):
                            # 如果數據行比表頭多列，截斷多餘的列
                            processed_data.append([normalize_text(cell) for cell in row[:len(unique_headers)]])
                        else:
                            # 如果數據行比表頭少列，用空字串填充
                            padded_row = [normalize_text(cell) for cell in row] + [''] * (len(unique_headers) - len(row))
                            processed_data.append(padded_row)

                    if processed_data:
                        df = pd.DataFrame(processed_data, columns=unique_headers)
                        dfs.append(df)
    except Exception as e:
        import streamlit as st
        st.error(f"提取 PDF 表格時發生錯誤: {e}")
    return dfs
