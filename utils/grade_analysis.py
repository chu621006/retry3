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
    year_column_keywords = ["學年", "year", "學 年", "學年度"] # 增加學年度
    semester_column_keywords = ["學期", "semester", "學 期"]
    
    # 新增選課代號的關鍵字，用於更精確判斷新課程
    course_code_column_keywords = ["選課代號", "Course Code", "Code", "選課 代號"]


    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        found_credit_column = None
        found_subject_column = None 
        found_gpa_column = None 
        found_year_column = None
        found_semester_column = None
        found_course_code_column = None # 新增選課代號欄位

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
                found_gpa_column = found_gpa_column or normalized_df_columns[k] 
                break
        for k in year_column_keywords:
            if k in normalized_df_columns:
                found_year_column = normalized_df_columns[k]
                break
        for k in semester_column_keywords:
            if k in normalized_df_columns:
                found_semester_column = normalized_df_columns[k]
                break
        for k in course_code_column_keywords: # 匹配選課代號欄位
            if k in normalized_df_columns:
                found_course_code_column = normalized_df_columns[k]
                break

        # 步驟 2: 如果沒有明確匹配，則回退到根據數據內容猜測欄位
        potential_credit_cols = []
        potential_subject_cols = []
        potential_gpa_cols = []
        potential_year_cols = []
        potential_semester_cols = []
        potential_course_code_cols = [] # 潛在的選課代號欄位

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
                if re.search(r'[\u4e00-\u9fa5]', item_str) and len(item_str) >= 2 and \
                   not item_str.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', item_str) and \
                   not item_str.lower() in ["通過", "抵免", "pass", "exempt"] and \
                   not re.match(r'^\d{3,4}$', item_str) and not re.match(r'^\w{2,5}$', item_str): # 排除選課代號
                    subject_vals_found += 1
            if subject_vals_found / total_sample_count >= 0.4:
                potential_subject_cols.append(col_name)

            gpa_vals_found = 0
            for item_str in sample_data:
                if re.match(r'^[A-Fa-f][+\-]?$', item_str) or (item_str.replace('.', '', 1).isdigit() and len(item_str) <=5) or item_str.lower() in ["通過", "抵免", "pass", "exempt"]: 
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
            
            course_code_vals_found = 0
            for item_str in sample_data:
                # 簡單的數字或數字加字母組合，長度3-5之間
                if re.match(r'^\w{3,5}$', item_str) and not (item_str.isdigit() and len(item_str) in [3,4]): # 排除純學年
                    course_code_vals_found += 1
            if course_code_vals_found / total_sample_count >= 0.4:
                potential_course_code_cols.append(col_name)


        # 根據推斷結果確定欄位，考慮列的順序
        def get_best_col(potentials, reference_col_idx=None, df_cols=df.columns):
            if not potentials:
                return None
            if reference_col_idx is None:
                return sorted(potentials, key=lambda x: df_cols.get_loc(x))[0]
            
            # 優先找在參考欄位之後的欄位
            after_ref_candidates = [col for col in potentials if df_cols.get_loc(col) > reference_col_idx]
            if after_ref_candidates:
                return sorted(after_ref_candidates, key=lambda x: df_cols.get_loc(x))[0]
            # 如果參考欄位之後沒有，就找之前的
            return sorted(potentials, key=lambda x: df_cols.get_loc(x))[0]

        if not found_year_column:
            found_year_column = get_best_col(potential_year_cols)
        
        year_idx = df.columns.get_loc(found_year_column) if found_year_column else None

        if not found_semester_column:
            found_semester_column = get_best_col(potential_semester_cols, year_idx)

        sem_idx = df.columns.get_loc(found_semester_column) if found_semester_column else None

        if not found_course_code_column: # 決定選課代號
            found_course_code_column = get_best_col(potential_course_code_cols, sem_idx)

        code_idx = df.columns.get_loc(found_course_code_column) if found_course_code_column else None

        if not found_subject_column:
            found_subject_column = get_best_col(potential_subject_cols, code_idx) # 科目名稱應在選課代號之後

        subject_idx = df.columns.get_loc(found_subject_column) if found_subject_column else None

        if not found_credit_column:
            found_credit_column = get_best_col(potential_credit_cols, subject_idx)

        credit_idx = df.columns.get_loc(found_credit_column) if found_credit_column else None

        if not found_gpa_column:
            found_gpa_column = get_best_col(potential_gpa_cols, credit_idx)


        # 確保找到了至少科目名稱和學分欄位
        if found_credit_column and found_subject_column: 
            try:
                temp_subject_name_buffer = "" # 用於累積跨行的科目名稱片段

                for row_idx, row in df.iterrows():
                    row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}

                    current_row_subject_name_raw = row_data.get(found_subject_column, "")
                    credit_col_content = row_data.get(found_credit_column, "")
                    gpa_col_content = row_data.get(found_gpa_column, "")
                    year_col_content = row_data.get(found_year_column, "") # 學年度內容
                    semester_col_content = row_data.get(found_semester_column, "") # 學期內容
                    course_code_col_content = row_data.get(found_course_code_column, "") # 選課代號內容

                    extracted_credit_this_row, extracted_gpa_this_row = 0.0, ""

                    parsed_credit_from_credit_col, parsed_gpa_from_credit_col = parse_credit_and_gpa(credit_col_content)
                    if parsed_credit_from_credit_col > 0:
                        extracted_credit_this_row = parsed_credit_from_credit_col
                    if parsed_gpa_from_credit_col:
                        extracted_gpa_this_row = parsed_gpa_from_credit_col

                    parsed_credit_from_gpa_col, parsed_gpa_from_gpa_col = parse_credit_and_gpa(gpa_col_content)
                    if parsed_gpa_from_gpa_col:
                        extracted_gpa_this_row = parsed_gpa_from_gpa_col.upper()
                    if parsed_credit_from_gpa_col > 0 and extracted_credit_this_row == 0.0:
                        extracted_credit_this_row = parsed_credit_from_gpa_col
                    
                    # 判斷當前行是否為一個完整的課程記錄（即有學分或有效的GPA）
                    has_complete_course_info_this_row = (
                        extracted_credit_this_row > 0 or 
                        is_passing_gpa(extracted_gpa_this_row) or 
                        normalize_text(credit_col_content).lower() in ["通過", "抵免", "pass", "exempt"] or 
                        normalize_text(gpa_col_content).lower() in ["通過", "抵免", "pass", "exempt"]
                    )
                    
                    # 判斷當前行是否是一個潛在的科目名稱片段（有中文科目名稱，但沒有學分/GPA）
                    # 更加嚴格判斷：如果科目名稱欄位內容是數字且長度為3或4，很可能是學年，不是科目名稱片段
                    is_potential_subject_fragment_row = (
                        current_row_subject_name_raw and len(current_row_subject_name_raw) >= 2 and
                        re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw) and 
                        not has_complete_course_info_this_row and # 且不包含完整課程資訊
                        not (current_row_subject_name_raw.isdigit() and len(current_row_subject_name_raw) in [3,4]) and # 排除學年數字
                        not re.match(r'^\w{3,5}$', current_row_subject_name_raw) # 排除選課代號樣式的字符串
                    )

                    # 新增判斷：當前行是否極有可能是一個新課程的開始
                    # 條件：有學年度或學期，或有選課代號，且科目名稱欄位不為空且看起來像科目名稱
                    is_row_likely_new_course_start = (
                        (year_col_content and year_col_content.isdigit() and len(year_col_content) in [3,4]) or
                        (semester_col_content and re.search(r'(上|下|春|夏|秋|冬|1|2|3)', semester_col_content)) or
                        (course_code_col_content and re.match(r'^\w{3,5}$', course_code_col_content))
                    ) and current_row_subject_name_raw and re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw)
                    
                    # --- 核心邏輯：處理科目名稱緩衝區和課程數據組裝 ---
                    
                    # 優先判斷是否是新課程的開始，這會強制清空緩衝區
                    if is_row_likely_new_course_start and not is_potential_subject_fragment_row:
                        # 如果當前行明確是一個新課程的開始，並且它不是一個純粹的科目名稱片段（它有完整的開頭信息）
                        # 則清空之前所有的緩衝區，因為它屬於前一個可能未完成的課程
                        if temp_subject_name_buffer:
                            # 警告，表示之前的科目片段沒有被完整課程行「關閉」
                            # import streamlit as st
                            # st.warning(f"表格 {df_idx + 1} 偵測到未完成的科目名稱片段: '{temp_subject_name_buffer}'，被新課程開頭中斷，已跳過。")
                            pass
                        temp_subject_name_buffer = "" # 強制清空緩衝區
                    
                    if has_complete_course_info_this_row:
                        # 情況 1: 偵測到一個完整的課程資訊行 (包含學分/GPA)
                        
                        # 首先，將之前可能累積的科目名稱片段與當前行的科目名稱合併
                        final_subject_name = current_row_subject_name_raw
                        if temp_subject_name_buffer:
                            final_subject_name = temp_subject_name_buffer + " " + current_row_subject_name_raw
                            
                        # 重要：在處理完一個課程後，立即清空緩衝區，避免污染下一個課程
                        temp_subject_name_buffer = "" 

                        # 提取學年學期等信息
                        acad_year = year_col_content
                        semester = semester_col_content
                        
                        # 如果學年學期欄位是空的，但科目名稱或選課代號欄位含有這些信息，嘗試從那裡提取
                        if not acad_year and found_course_code_column and found_course_code_column in row_data:
                            match = re.search(r'^(\d{3,4})', row_data[found_course_code_column])
                            if match:
                                acad_year = match.group(1)

                        if not acad_year and found_subject_column and found_subject_column in row_data:
                            match = re.search(r'^(\d{3,4})\s*(上|下|春|夏|秋|冬|1|2|3)?', row_data[found_subject_column])
                            if match:
                                acad_year = match.group(1)
                                if match.group(2) and not semester:
                                    semester = match.group(2)

                        # 進一步從其他列或第一列/第二列尋找學年學期
                        if not acad_year and len(df.columns) > 0 and df.columns[0] in row_data:
                            temp_first_col = row_data[df.columns[0]]
                            year_match = re.search(r'(\d{3,4})', temp_first_col)
                            if year_match:
                                acad_year = temp_first_col
                            if not semester:
                                 sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
                                 if sem_match:
                                     semester = sem_match.group(1)

                        if not semester and len(df.columns) > 1 and df.columns[1] in row_data:
                            temp_second_col = row_data[df.columns[1]]
                            sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
                            if sem_match:
                                semester = sem_second_col # 直接使用匹配到的值

                        # 組裝課程數據並添加到列表
                        course_info = {
                            "學年度": acad_year,
                            "學期": semester,
                            "科目名稱": final_subject_name, 
                            "學分": extracted_credit_this_row, 
                            "GPA": extracted_gpa_this_row, 
                            "來源表格": df_idx + 1
                        }

                        if extracted_gpa_this_row:
                            if not is_passing_gpa(extracted_gpa_this_row): 
                                failed_courses.append(course_info)
                            else:
                                if extracted_credit_this_row > 0: 
                                    total_credits += extracted_credit_this_row
                                calculated_courses.append(course_info)
                        elif extracted_credit_this_row > 0: # 只有學分，沒有 GPA，也視為通過
                            total_credits += extracted_credit_this_row
                            calculated_courses.append(course_info)

                    elif is_potential_subject_fragment_row:
                        # 情況 2: 當前行是科目名稱的片段 (有科目名稱，但沒有學分/GPA)
                        temp_subject_name_buffer += (" " if temp_subject_name_buffer else "") + current_row_subject_name_raw
                        
                    else:
                        # 情況 3: 既不是完整的課程資訊行，也不是科目名稱片段行。
                        # 這通常是空行、表格合計行、或不相關的文字行。
                        # 在這種情況下，必須清空任何殘餘的科目名稱緩衝區，因為它不屬於任何待處理的課程。
                        if temp_subject_name_buffer:
                            # 由於 Streamlit 在這個環境中可能無法直接訪問，暫時註釋掉 st.warning
                            # import streamlit as st
                            # st.warning(f"表格 {df_idx + 1} 偵測到未完成的科目名稱片段: '{temp_subject_name_buffer}'，被非課程行中斷，已跳過。")
                            pass 
                        temp_subject_name_buffer = "" # 強制清空緩衝區
                        

                # 循環結束後，檢查緩衝區是否有任何未處理的科目名稱片段
                if temp_subject_name_buffer:
                    # import streamlit as st
                    # st.warning(f"表格 {df_idx + 1} 偵測到文件末尾未完成的科目名稱片段: '{temp_subject_name_buffer}'，已跳過。")
                    pass 

            except Exception as e:
                import streamlit as st # 確保 streamlit 可用
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。錯誤訊息: `{e}`")
        else:
            # 如果沒有找到學分欄位或科目欄位，這張表格可能不是成績單，直接跳過
            pass 
            
    return total_credits, calculated_courses, failed_courses
