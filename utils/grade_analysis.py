# utils/grade_analysis.py
import pandas as pd
import re
from .pdf_processing import normalize_text # 從同層目錄的 pdf_processing.py 導入

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
    year_column_keywords = ["學年", "year", "學 年"]
    semester_column_keywords = ["學期", "semester", "學 期"]
    
    failing_grades = ["D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"] 

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
                if re.match(r'^[A-Fa-f][+\-]?' , item_str) or (item_str.isdigit() and len(item_str) <=3) or item_str.lower() in ["通過", "抵免", "pass", "exempt"]: 
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
                for row_idx, row in df.iterrows():
                    if all(normalize_text(str(cell)) == "" for cell in row):
                        continue

                    extracted_credit = 0.0
                    extracted_gpa = ""

                    if found_credit_column in row and pd.notna(row[found_credit_column]): 
                        extracted_credit, extracted_gpa_from_credit_col = parse_credit_and_gpa(row[found_credit_column])
                        if extracted_gpa_from_credit_col and not extracted_gpa:
                            extracted_gpa = extracted_gpa_from_credit_col
                    
                    if found_gpa_column and found_gpa_column in row and pd.notna(row[found_gpa_column]): 
                        gpa_from_gpa_col_raw = normalize_text(row[found_gpa_column])
                        parsed_credit_from_gpa_col, parsed_gpa_from_gpa_col = parse_credit_and_gpa(gpa_from_gpa_col_raw)
                        
                        if parsed_gpa_from_gpa_col:
                            extracted_gpa = parsed_gpa_from_gpa_col.upper()
                        
                        if parsed_credit_from_gpa_col > 0 and extracted_credit == 0.0:
                            extracted_credit = parsed_credit_from_gpa_col
                    
                    if extracted_credit is None:
                        extracted_credit = 0.0

                    is_failing_grade = False
                    if extracted_gpa:
                        gpa_clean = re.sub(r'[+\-]', '', extracted_gpa).upper() 
                        if gpa_clean in failing_grades:
                            is_failing_grade = True
                        elif gpa_clean.isdigit(): 
                            try:
                                numeric_gpa = float(gpa_clean)
                                if numeric_gpa < 60: 
                                    is_failing_grade = True
                            except ValueError:
                                pass
                    
                    is_passed_or_exempt_grade = False
                    if (found_gpa_column in row and pd.notna(row[found_gpa_column]) and normalize_text(row[found_gpa_column]).lower() in ["通過", "抵免", "pass", "exempt"]) or \
                       (found_credit_column in row and pd.notna(row[found_credit_column]) and normalize_text(row[found_credit_column]).lower() in ["通過", "抵免", "pass", "exempt"]):
                        is_passed_or_exempt_grade = True
                        
                    course_name = "未知科目" 
                    if found_subject_column in row and pd.notna(row[found_subject_column]): 
                        temp_name = normalize_text(row[found_subject_column])
                        if len(temp_name) >= 2 and re.search(r'[\u4e00-\u9fa5]', temp_name): 
                            course_name = temp_name
                        elif not temp_name: 
                            try:
                                current_col_idx = df.columns.get_loc(found_subject_column)
                                if current_col_idx > 0: 
                                    prev_col_name = df.columns[current_col_idx - 1]
                                    if prev_col_name in row and pd.notna(row[prev_col_name]):
                                        temp_name_prev_col = normalize_text(row[prev_col_name])
                                        if len(temp_name_prev_col) >= 2 and re.search(r'[\u4e00-\u9fa5]', temp_name_prev_col) and \
                                            not temp_name_prev_col.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', temp_name_prev_col):
                                            course_name = temp_name_prev_col
                                            
                                if course_name == "未知科目" and current_col_idx < len(df.columns) - 1:
                                    next_col_name = df.columns[current_col_idx + 1]
                                    if next_col_name in row and pd.notna(row[next_col_name]):
                                        temp_name_next_col = normalize_text(row[next_col_name])
                                        if len(temp_name_next_col) >= 2 and re.search(r'[\u4e00-\u9fa5]', temp_name_next_col) and \
                                            not temp_name_next_col.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', temp_name_next_col):
                                            course_name = temp_name_next_col
                            except Exception:
                                pass
                    
                    if course_name == "未知科目" and extracted_credit == 0.0 and not extracted_gpa and not is_passed_or_exempt_grade:
                        continue

                    acad_year = ""
                    semester = ""
                    if found_year_column and found_year_column in row and pd.notna(row[found_year_column]):
                        temp_year = normalize_text(row[found_year_column])
                        if temp_year.isdigit() and (len(temp_year) == 3 or len(temp_year) == 4):
                            acad_year = temp_year
                    elif found_semester_column and found_semester_column in row and pd.notna(row[found_semester_column]):
                        combined_val = normalize_text(row[found_semester_column])
                        year_match = re.search(r'(\d{3,4})', combined_val)
                        if year_match:
                            acad_year = year_match.group(1)
                    
                    if found_semester_column and found_semester_column in row and pd.notna(row[found_semester_column]):
                        temp_sem = normalize_text(row[found_semester_column])
                        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_sem, re.IGNORECASE)
                        if sem_match:
                            semester = sem_match.group(1)

                    if not acad_year and len(df.columns) > 0 and df.columns[0] in row and pd.notna(row[df.columns[0]]):
                        temp_first_col = normalize_text(row[df.columns[0]])
                        year_match = re.search(r'(\d{3,4})', temp_first_col)
                        if year_match:
                            acad_year = year_match.group(1)
                        if not semester:
                             sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
                             if sem_match:
                                 semester = sem_match.group(1)

                    if not semester and len(df.columns) > 1 and df.columns[1] in row and pd.notna(row[df.columns[1]]):
                        temp_second_col = normalize_text(row[df.columns[1]])
                        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
                        if sem_match:
                            semester = sem_match.group(1)


                    if is_failing_grade:
                        failed_courses.append({
                            "學年度": acad_year,
                            "學期": semester,
                            "科目名稱": course_name, 
                            "學分": extracted_credit, 
                            "GPA": extracted_gpa, 
                            "來源表格": df_idx + 1
                        })
                    elif extracted_credit > 0 or is_passed_or_exempt_grade: 
                        if extracted_credit > 0: 
                            total_credits += extracted_credit
                        calculated_courses.append({
                            "學年度": acad_year,
                            "學期": semester,
                            "科目名稱": course_name, 
                            "學分": extracted_credit, 
                            "GPA": extracted_gpa, 
                            "來源表格": df_idx + 1
                        })
                
            except Exception as e:
                # 注意：這裡使用 st.warning/error 在 utils 模組中不太理想，
                # 但為了保持功能不變且簡化，暫時保留。更嚴謹的做法是返回錯誤訊息給 app.py 處理。
                import streamlit as st # 確保streamlit可用
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。")
        else:
            pass 
            
    return total_credits, calculated_courses, failed_courses
