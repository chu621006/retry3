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
                found_gpa_column = found_gpa_column or normalized_df_columns[k] # 確保即使後面的關鍵字也能更新
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
                # 判斷是否為看起來像中文科目名稱的字符串
                if re.search(r'[\u4e00-\u9fa5]', item_str) and len(item_str) >= 2 and \
                   not item_str.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', item_str) and \
                   not item_str.lower() in ["通過", "抵免", "pass", "exempt"] and \
                   not re.match(r'^\d{3,4}$', item_str): # 排除單純的學年數字
                    subject_vals_found += 1
            if subject_vals_found / total_sample_count >= 0.4:
                potential_subject_cols.append(col_name)

            gpa_vals_found = 0
            for item_str in sample_data:
                # 檢查是否為字母GPA、數字或通過/抵免字樣
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
                temp_subject_name_buffer = "" # 用於累積跨行的科目名稱片段
                current_course_data = {} # 用於暫存一個完整課程的數據

                for row_idx, row in df.iterrows():
                    row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}

                    current_row_subject_name_raw = row_data.get(found_subject_column, "")
                    credit_col_content = row_data.get(found_credit_column, "")
                    gpa_col_content = row_data.get(found_gpa_column, "")

                    extracted_credit_this_row, extracted_gpa_this_row = 0.0, ""

                    # 從學分欄位提取學分和潛在的 GPA (當前行的數據)
                    parsed_credit_from_credit_col, parsed_gpa_from_credit_col = parse_credit_and_gpa(credit_col_content)
                    if parsed_credit_from_credit_col > 0:
                        extracted_credit_this_row = parsed_credit_from_credit_col
                    if parsed_gpa_from_credit_col:
                        extracted_gpa_this_row = parsed_gpa_from_credit_col

                    # 從 GPA 欄位提取 GPA（優先使用，因為可能更準確）
                    parsed_credit_from_gpa_col, parsed_gpa_from_gpa_col = parse_credit_and_gpa(gpa_col_content)
                    if parsed_gpa_from_gpa_col:
                        extracted_gpa_this_row = parsed_gpa_from_gpa_col.upper()
                    # 如果 GPA 欄位也包含學分信息且主學分欄位沒有提取到學分，則補充
                    if parsed_credit_from_gpa_col > 0 and extracted_credit_this_row == 0.0:
                        extracted_credit_this_row = parsed_credit_from_gpa_col
                    
                    # 判斷當前行是否為一個完整的課程記錄（即有學分或有效的GPA）
                    has_complete_course_info_this_row = (
                        extracted_credit_this_row > 0 or 
                        is_passing_gpa(extracted_gpa_this_row) or # 檢查解析後的GPA是否及格
                        normalize_text(credit_col_content).lower() in ["通過", "抵免", "pass", "exempt"] or # 也考慮原始文本是「通過」或「抵免」的情況
                        normalize_text(gpa_col_content).lower() in ["通過", "抵免", "pass", "exempt"]
                    )
                    
                    # 判斷當前行是否是一個潛在的科目名稱片段（有中文科目名稱，但沒有學分/GPA）
                    is_potential_subject_fragment_row = (
                        current_row_subject_name_raw and len(current_row_subject_name_raw) >= 2 and
                        re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw) and
                        not current_row_subject_name_raw.isdigit() and # 不是純數字
                        not re.match(r'^[A-Fa-f][+\-]?$', current_row_subject_name_raw) and # 不是字母GPA
                        not normalize_text(current_row_subject_name_raw).lower() in ["通過", "抵免", "pass", "exempt"] # 不是通過/抵免字樣
                    )

                    # --- 核心邏輯：處理科目名稱緩衝區和課程數據組裝 ---
                    if has_complete_course_info_this_row:
                        # 如果當前行是完整的課程信息，這代表一個新課程的開始或上一個課程的延續
                        
                        # 在處理新課程之前，先處理並儲存上一個可能已經組裝好的課程
                        if current_course_data:
                            is_failing_prev = False
                            if current_course_data.get("GPA"):
                                if not is_passing_gpa(current_course_data["GPA"]):
                                    is_failing_prev = True
                            
                            if is_failing_prev:
                                failed_courses.append(current_course_data)
                            elif current_course_data.get("學分", 0) > 0 or is_passing_gpa(current_course_data.get("GPA", "")):
                                if current_course_data.get("學分", 0) > 0:
                                    total_credits += current_course_data["學分"]
                                calculated_courses.append(current_course_data)
                            
                            current_course_data = {} # 清空，準備組裝新課程

                        # 合併科目名稱：將緩衝區內容與當前行的科目名稱合併
                        final_course_name = current_row_subject_name_raw
                        if temp_subject_name_buffer:
                            final_course_name = temp_subject_name_buffer + " " + current_row_subject_name_raw
                            temp_subject_name_buffer = "" # 清空緩衝區，因為已使用

                        # 開始組裝當前行代表的新課程數據
                        current_course_data = {
                            "學年度": "",
                            "學期": "",
                            "科目名稱": final_course_name, 
                            "學分": extracted_credit_this_row, 
                            "GPA": extracted_gpa_this_row, 
                            "來源表格": df_idx + 1
                        }

                        # 提取學年學期 (從當前行提取)
                        # 這部分邏輯保持與之前相同，確保學年學期能被正確獲取
                        if found_year_column and found_year_column in row_data:
                            temp_year = row_data[found_year_column]
                            if temp_year.isdigit() and (len(temp_year) == 3 or len(temp_year) == 4):
                                current_course_data["學年度"] = temp_year
                        elif found_semester_column and found_semester_column in row_data: 
                            combined_val = row_data[found_semester_column]
                            year_match = re.search(r'(\d{3,4})', combined_val)
                            if year_match:
                                current_course_data["學年度"] = year_match.group(1)
                        
                        if found_semester_column and found_semester_column in row_data:
                            temp_sem = row_data[found_semester_column]
                            sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_sem, re.IGNORECASE)
                            if sem_match:
                                current_course_data["學期"] = sem_match.group(1)

                        if not current_course_data["學年度"] and len(df.columns) > 0 and df.columns[0] in row_data:
                            temp_first_col = row_data[df.columns[0]]
                            year_match = re.search(r'(\d{3,4})', temp_first_col)
                            if year_match:
                                current_course_data["學年度"] = temp_first_col
                            if not current_course_data["學期"]:
                                 sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
                                 if sem_match:
                                     current_course_data["學期"] = sem_match.group(1)

                        if not current_course_data["學期"] and len(df.columns) > 1 and df.columns[1] in row_data:
                            temp_second_col = row_data[df.columns[1]]
                            sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
                            if sem_match:
                                current_course_data["學期"] = sem_match.group(1)

                    elif is_potential_subject_fragment_row:
                        # 如果當前行不是完整的課程信息，但僅是科目名稱的片段，則將其添加到緩衝區
                        temp_subject_name_buffer += (" " if temp_subject_name_buffer else "") + current_row_subject_name_raw
                        
                    else:
                        # 如果該行既不是完整的課程信息，也不是潛在的科目名稱片段 (例如，它是一個真正的空行，或者不相關的數據行)
                        # 在這種情況下，我們僅僅跳過該行，**不影響緩衝區 `temp_subject_name_buffer` 的內容**。
                        # 這確保了即使科目名稱片段之間有空行，緩衝區也不會被錯誤清空。
                        continue
                
                # 處理循環結束後可能存在的最後一個課程或剩餘的緩衝區內容
                # 這部分邏輯保持不變，因為它處理的是在文件末尾可能未被添加到列表的課程
                if current_course_data:
                    is_failing_last = False
                    if current_course_data.get("GPA"):
                        if not is_passing_gpa(current_course_data["GPA"]):
                            is_failing_last = True
                    
                    if is_failing_last:
                        failed_courses.append(current_course_data)
                    elif current_course_data.get("學分", 0) > 0 or is_passing_gpa(current_course_data.get("GPA", "")):
                        if current_course_data.get("學分", 0) > 0:
                            total_credits += current_course_data["學分"]
                        calculated_courses.append(current_course_data)
                
                if temp_subject_name_buffer:
                    import streamlit as st
                    st.warning(f"表格 {df_idx + 1} 偵測到未完成的科目名稱: '{temp_subject_name_buffer}'，由於缺乏學分/GPA信息，已跳過。")

            except Exception as e:
                import streamlit as st # 確保 streamlit 可用
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。錯誤訊息: `{e}`")
        else:
            # 如果沒有找到學分欄位或科目欄位，這張表格可能不是成績單，直接跳過
            pass 
            
    return total_credits, calculated_courses, failed_courses
