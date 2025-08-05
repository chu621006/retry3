# utils/grade_analysis.py
import pandas as pd
import re
from .pdf_processing import normalize_text # 從同層目錄的 pdf_processing.py 導入

def is_passing_gpa(gpa_str):
    """
    判斷給定的 GPA 字串是否為通過成績。
    """
    gpa_clean = normalize_text(gpa_str).upper()
    # 定義常見的不及格字母成績和文字
    failing_grades = ["D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"] 
    
    if not gpa_clean:
        return False
    
    # 如果是明確的通過/抵免文字
    if gpa_clean in ["通過", "抵免", "PASS", "EXEMPT"]:
        return True
    
    # 檢查是否為不及格的字母成績
    if gpa_clean in failing_grades:
        return False
        
    # 如果是 A, B, C 類的字母成績，通常視為通過
    if re.match(r'^[A-C][+\-]?$', gpa_clean):
        return True
    
    # 如果是數字成績，假設 60 分為及格線
    if gpa_clean.replace('.', '', 1).isdigit(): # 檢查是否為純數字或帶小數點的數字
        try:
            numeric_gpa = float(gpa_clean)
            return numeric_gpa >= 60.0 
        except ValueError:
            pass
            
    return False

def parse_credit_and_gpa(text):
    """
    從單元格文本中解析學分和 GPA。
    考慮 "A 2" (GPA在左，學分在右) 和 "2 A" (學分在左，GPA在右) 的情況。
    返回 (學分, GPA)。如果解析失敗，返回 (0.0, "")。
    """
    text_clean = normalize_text(text)
    
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]:
        # 對於通過或抵免的科目，學分通常為0（或依實際學分數計，但這裡我們保持為0.0，因為不直接計入總學分）
        return 0.0, text_clean

    match_gpa_credit = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if match_gpa_credit:
        gpa = match_gpa_credit.group(1).upper()
        try:
            credit = float(match_gpa_credit.group(2))
            return credit, gpa
        except ValueError:
            pass

    match_credit_gpa = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', text_clean)
    if match_credit_gpa:
        try:
            credit = float(match_credit_gpa.group(1))
            gpa = match_credit_gpa.group(3).upper()
            return credit, gpa
        except ValueError:
            pass
            
    credit_only_match = re.search(r'(\d+(\.\d+)?)', text_clean)
    if credit_only_match:
        try:
            credit = float(credit_only_match.group(1))
            return credit, "" 
        except ValueError:
            pass

    gpa_only_match = re.search(r'([A-Fa-f][+\-]?)', text_clean)
    if gpa_only_match:
        return 0.0, gpa_only_match.group(1).upper()

    return 0.0, ""

def calculate_total_credits(df_list):
    """
    從提取的 DataFrames 列表中計算總學分。
    尋找包含 '學分' 或 '學分(GPA)' 類似字樣的欄位進行加總。
    返回總學分和計算學分的科目列表，以及不及格科目列表。
    """
    total_credits = 0.0
    calculated_courses = [] 
    failed_courses = [] 

    credit_column_keywords = ["學分", "學分數", "學分(GPA)", "學 分", "Credits", "Credit", "學分數(學分)"] 
    subject_column_keywords = ["科目名稱", "課程名稱", "Course Name", "Subject Name", "科目", "課程"] 
    gpa_column_keywords = ["GPA", "成績", "Grade", "gpa(數值)"] 
    year_column_keywords = ["學年", "year", "學 年"]
    semester_column_keywords = ["學期", "semester", "學 期"]
    
    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        found_credit_column = None
        found_subject_column = None 
        found_gpa_column = None 
        found_year_column = None
        found_semester_column = None
        
        # 步驟 1: 優先匹配明確的表頭關鍵字
        normalized_df_columns = {re.sub(r'\s+', '', col_name).lower(): col_name for col_name in df.columns}
        
        for k in credit_column_keywords:
            if k in normalized_df_columns:
                found_credit_column = normalized_df_columns[k]
                break
        for k in subject_column_keywords:
            if k in normalized_df_columns:
                found_subject_column = normalized_df_columns[k]
                break
        for k in gpa_column_keywords:
            if k in normalized_df_columns:
                found_gpa_column = normalized_df_columns[k]
                break
        for k in year_column_keywords:
            if k in normalized_df_columns:
                found_year_column = normalized_df_columns[k]
                break
        for k in semester_column_keywords:
            if k in normalized_df_columns:
                found_semester_column = normalized_df_columns[k]
                break

        # 步驟 2: 如果沒有明確匹配，則回退到根據數據內容猜測欄位
        potential_credit_cols = []
        potential_subject_cols = []
        potential_gpa_cols = []
        potential_year_cols = []
        potential_semester_cols = []

        sample_rows_df = df.head(min(len(df), 20)) 

        for col_name in df.columns: 
            sample_data = sample_rows_df[col_name].apply(normalize_text).tolist()
            total_sample_count = len(sample_data)
            if total_sample_count == 0:
                continue

            credit_vals_found = 0
            for item_str in sample_data:
                credit_val, _ = parse_credit_and_gpa(item_str)
                if 0.0 < credit_val <= 10.0: 
                    credit_vals_found += 1
            if credit_vals_found / total_sample_count >= 0.4:
                potential_credit_cols.append(col_name)

            subject_vals_found = 0
            for item_str in sample_data:
                if re.search(r'[\u4e00-\u9fa5]', item_str) and len(item_str) >= 2 and not item_str.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', item_str) and not item_str.lower() in ["通過", "抵免", "pass", "exempt"]: 
                    subject_vals_found += 1
            if subject_vals_found / total_sample_count >= 0.4:
                potential_subject_cols.append(col_name)

            gpa_vals_found = 0
            for item_str in sample_data:
                # 檢查是否為字母GPA、數字或通過/抵免字樣
                if re.match(r'^[A-Fa-f][+\-]?$', item_str) or (item_str.isdigit() and len(item_str) <=3) or item_str.lower() in ["通過", "抵免", "pass", "exempt"]: 
                    gpa_vals_found += 1
            if gpa_vals_found / total_sample_count >= 0.4:
                potential_gpa_cols.append(col_name)

            year_vals_found = 0
            for item_str in sample_data:
                if (item_str.isdigit() and (len(item_str) == 3 or len(item_str) == 4)):
                    year_vals_found += 1
            if year_vals_found / total_sample_count >= 0.6: 
                potential_year_cols.append(col_name)

            semester_vals_found = 0
            for item_str in sample_data:
                if item_str.lower() in ["上", "下", "春", "夏", "秋", "冬", "1", "2", "3", "春季", "夏季", "秋季", "冬季", "spring", "summer", "fall", "winter"]:
                    semester_vals_found += 1
            if semester_vals_found / total_sample_count >= 0.6: 
                potential_semester_cols.append(col_name)

        # 根據推斷結果確定學分、科目、GPA、學年、學期欄位
        if not found_year_column and potential_year_cols:
            found_year_column = sorted(potential_year_cols, key=lambda x: df.columns.get_loc(x))[0]
        if not found_semester_column and potential_semester_cols:
            if found_year_column:
                year_col_idx = df.columns.get_loc(found_year_column)
                candidates = [col for col in potential_semester_cols if df.columns.get_loc(col) > year_col_idx]
                if candidates:
                    found_semester_column = sorted(candidates, key=lambda x: df.columns.get_loc(x))[0]
                elif potential_semester_cols:
                    found_semester_column = potential_semester_cols[0]
            else:
                found_semester_column = sorted(potential_semester_cols, key=lambda x: df.columns.get_loc(x))[0]

        if not found_subject_column and potential_subject_cols:
            if found_semester_column:
                sem_col_idx = df.columns.get_loc(found_semester_column)
                candidates = [col for col in potential_subject_cols if df.columns.get_loc(col) > sem_col_idx]
                if candidates:
                    found_subject_column = sorted(candidates, key=lambda x: df.columns.get_loc(x))[0]
                elif potential_subject_cols:
                    found_subject_column = potential_subject_cols[0]
            else:
                found_subject_column = sorted(potential_subject_cols, key=lambda x: df.columns.get_loc(x))[0]

        if not found_credit_column and potential_credit_cols:
            if found_subject_column:
                subject_col_idx = df.columns.get_loc(found_subject_column)
                candidates = [col for col in potential_credit_cols if df.columns.get_loc(col) > subject_col_idx]
                if candidates:
                    found_credit_column = sorted(candidates, key=lambda x: df.columns.get_loc(x))[0]
                elif potential_credit_cols:
                    found_credit_column = potential_credit_cols[0]
            else:
                found_credit_column = sorted(potential_credit_cols, key=lambda x: df.columns.get_loc(x))[0]

        if not found_gpa_column and potential_gpa_cols:
            if found_credit_column:
                credit_col_idx = df.columns.get_loc(found_credit_column)
                candidates = [col for col in potential_gpa_cols if df.columns.get_loc(col) > credit_col_idx]
                if candidates:
                    found_gpa_column = sorted(candidates, key=lambda x: df.columns.get_loc(x))[0]
                elif potential_gpa_cols:
                    found_gpa_column = potential_gpa_cols[0]
            else:
                found_gpa_column = sorted(potential_gpa_cols, key=lambda x: df.columns.get_loc(x))[0]

        if found_credit_column and found_subject_column: 
            try:
                # 使用迭代器來處理行，以便於合併
                row_iter = df.iterrows()
                current_row_idx, current_row = next(row_iter, (None, None))

                while current_row_idx is not None:
                    # 如果整行為空行，則跳過
                    if all(normalize_text(str(cell)) == "" for cell in current_row):
                        current_row_idx, current_row = next(row_iter, (None, None))
                        continue

                    extracted_credit = 0.0
                    extracted_gpa = ""
                    course_name = "未知科目"

                    # 嘗試從科目名稱欄位獲取
                    if found_subject_column in current_row and pd.notna(current_row[found_subject_column]):
                        course_name = normalize_text(current_row[found_subject_column])
                    
                    # 嘗試從學分欄位提取學分和潛在的 GPA
                    if found_credit_column in current_row and pd.notna(current_row[found_credit_column]): 
                        extracted_credit, extracted_gpa_from_credit_col = parse_credit_and_gpa(current_row[found_credit_column])
                        if extracted_gpa_from_credit_col and not extracted_gpa:
                            extracted_gpa = extracted_gpa_from_credit_col
                    
                    # 從 GPA 欄位提取 GPA（優先使用）
                    if found_gpa_column and found_gpa_column in current_row and pd.notna(current_row[found_gpa_column]): 
                        gpa_from_gpa_col_raw = normalize_text(current_row[found_gpa_column])
                        parsed_credit_from_gpa_col, parsed_gpa_from_gpa_col = parse_credit_and_gpa(gpa_from_gpa_col_raw)
                        
                        if parsed_gpa_from_gpa_col:
                            extracted_gpa = parsed_gpa_from_gpa_col.upper()
                        
                        # 如果 GPA 欄位也包含學分信息且主學分欄位沒有提取到學分，則補充
                        if parsed_credit_from_gpa_col > 0 and extracted_credit == 0.0:
                            extracted_credit = parsed_credit_from_gpa_col
                    
                    if extracted_credit is None:
                        extracted_credit = 0.0

                    # --- **新增：處理科目名稱跨行的邏輯** ---
                    # 判斷當前行是否為潛在的科目名稱前半部分 (例如，沒有完整學分/GPA數據但有部分名稱)
                    is_incomplete_course_row = (
                        len(course_name) > 2 and # 有一定長度的科目名稱
                        extracted_credit == 0.0 and # 當前行沒有明確學分
                        not extracted_gpa and # 當前行沒有明確GPA
                        not is_passing_gpa(extracted_gpa) # 也不是通過或不及格
                    )
                    
                    # 預讀下一行，檢查是否是科目名稱的延續
                    peek_row_idx, peek_row = next(row_iter, (None, None))
                    
                    can_merge_subject = False
                    if peek_row_idx is not None and found_subject_column in peek_row:
                        next_subject_part = normalize_text(peek_row[found_subject_column])
                        next_credit, next_gpa = 0.0, ""
                        if found_credit_column in peek_row and pd.notna(peek_row[found_credit_column]):
                            next_credit, next_gpa_from_credit_col = parse_credit_and_gpa(peek_row[found_credit_column])
                            if next_gpa_from_credit_col and not next_gpa:
                                next_gpa = next_gpa_from_credit_col

                        if found_gpa_column and found_gpa_column in peek_row and pd.notna(peek_row[found_gpa_column]):
                            _, parsed_gpa_from_gpa_col = parse_credit_and_gpa(normalize_text(peek_row[found_gpa_column]))
                            if parsed_gpa_from_gpa_col:
                                next_gpa = parsed_gpa_from_gpa_col.upper()
                        
                        if next_credit == 0.0 and not next_gpa and next_subject_part and len(next_subject_part) >= 2:
                             # 如果下一行科目名稱不為空，且下一行沒有學分/GPA信息，則認為可以合併
                             can_merge_subject = True
                             
                    # 如果當前行是部分科目名稱，且下一行看起來是其延續，則進行合併
                    if is_incomplete_course_row and can_merge_subject:
                        course_name += " " + next_subject_part
                        # 從被合併的下一行中提取完整的學分和 GPA
                        if found_credit_column in peek_row and pd.notna(peek_row[found_credit_column]):
                            extracted_credit, extracted_gpa_from_merged = parse_credit_and_gpa(peek_row[found_credit_column])
                            if extracted_gpa_from_merged and not extracted_gpa: # 使用合併行的GPA
                                extracted_gpa = extracted_gpa_from_merged
                        
                        if found_gpa_column and found_gpa_column in peek_row and pd.notna(peek_row[found_gpa_column]):
                            _, gpa_from_merged_gpa_col = parse_credit_and_gpa(normalize_text(peek_row[found_gpa_column]))
                            if gpa_from_merged_gpa_col:
                                extracted_gpa = gpa_from_merged_gpa_col.upper()

                        # 繼續處理合併後的行
                        current_row_idx, current_row = peek_row_idx, peek_row # 讓下一次循環從合併的下一行開始
                        # 學年學期信息也從合併的行獲取，如果當前行沒有
                        if not acad_year: # 僅在當前行學年為空時，嘗試從被合併的行獲取
                             acad_year = normalize_text(current_row[found_year_column]) if found_year_column and found_year_column in current_row and pd.notna(current_row[found_year_column]) else ""
                        if not semester: # 僅在當前行學期為空時，嘗試從被合併的行獲取
                             semester = normalize_text(current_row[found_semester_column]) if found_semester_column and found_semester_column in current_row and pd.notna(current_row[found_semester_column]) else ""
                    else:
                        # 如果不合併，則回退到下一行
                        row_iter = iter([(peek_row_idx, peek_row)] + list(row_iter)) # 將預讀的行放回迭代器開頭
                    # --- **結束：處理科目名稱跨行的邏輯** ---

                    # 判斷是否為不及格成績
                    is_failing_grade = False
                    if extracted_gpa:
                        if not is_passing_gpa(extracted_gpa): # 使用 is_passing_gpa 函數
                            is_failing_grade = True
                    
                    # 判斷是否為文字上的"通過"或"抵免" (即使沒有學分)
                    is_passed_or_exempt_grade_text = False
                    if (found_gpa_column and found_gpa_column in current_row and pd.notna(current_row[found_gpa_column]) and normalize_text(current_row[found_gpa_column]).lower() in ["通過", "抵免", "pass", "exempt"]) or \
                       (found_credit_column and found_credit_column in current_row and pd.notna(current_row[found_credit_column]) and normalize_text(current_row[found_credit_column]).lower() in ["通過", "抵免", "pass", "exempt"]):
                        is_passed_or_exempt_grade_text = True
                    
                    # 提取學年學期信息，即使它們可能出現在非預期的位置
                    acad_year = ""
                    semester = ""
                    if found_year_column and found_year_column in current_row and pd.notna(current_row[found_year_column]):
                        temp_year = normalize_text(current_row[found_year_column])
                        if temp_year.isdigit() and (len(temp_year) == 3 or len(temp_year) == 4):
                            acad_year = temp_year
                    elif found_semester_column and found_semester_column in current_row and pd.notna(current_row[found_semester_column]):
                        combined_val = normalize_text(current_row[found_semester_column])
                        year_match = re.search(r'(\d{3,4})', combined_val)
                        if year_match:
                            acad_year = year_match.group(1)
                    
                    if found_semester_column and found_semester_column in current_row and pd.notna(current_row[found_semester_column]):
                        temp_sem = normalize_text(current_row[found_semester_column])
                        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_sem, re.IGNORECASE)
                        if sem_match:
                            semester = sem_match.group(1)

                    # 嘗試從前兩個欄位中獲取學年學期，如果前面未找到
                    if not acad_year and len(df.columns) > 0 and df.columns[0] in current_row and pd.notna(current_row[df.columns[0]]):
                        temp_first_col = normalize_text(current_row[df.columns[0]])
                        year_match = re.search(r'(\d{3,4})', temp_first_col)
                        if year_match:
                            acad_year = year_match.group(1)
                        if not semester:
                             sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
                             if sem_match:
                                 semester = sem_match.group(1)

                    if not semester and len(df.columns) > 1 and df.columns[1] in current_row and pd.notna(current_row[df.columns[1]]):
                        temp_second_col = normalize_text(current_row[df.columns[1]])
                        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
                        if sem_match:
                            semester = sem_match.group(1)


                    # 將課程分類為不及格或通過（計入列表，但不一定計入總學分）
                    if is_failing_grade:
                        failed_courses.append({
                            "學年度": acad_year,
                            "學期": semester,
                            "科目名稱": course_name, 
                            "學分": extracted_credit, 
                            "GPA": extracted_gpa, 
                            "來源表格": df_idx + 1
                        })
                    # 如果有學分 (大於0) 或者 GPA 是通過等級，則計入通過課程列表
                    elif extracted_credit > 0 or is_passing_gpa(extracted_gpa) or is_passed_or_exempt_grade_text: # 額外判斷文本通過
                        if extracted_credit > 0: 
                            total_credits += extracted_credit # 只有學分大於0才計入總學分
                        calculated_courses.append({
                            "學年度": acad_year,
                            "學期": semester,
                            "科目名稱": course_name, 
                            "學分": extracted_credit, 
                            "GPA": extracted_gpa, 
                            "來源表格": df_idx + 1
                        })
                    
                    # 準備處理下一行
                    current_row_idx, current_row = next(row_iter, (None, None))
                
            except Exception as e:
                import streamlit as st # 確保 streamlit 可用
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。")
        else:
            pass 
            
    return total_credits, calculated_courses, failed_courses
