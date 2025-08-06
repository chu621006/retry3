# utils/grade_analysis.py
import pandas as pd
import re
from .pdf_processing import normalize_text 

def is_passing_gpa(gpa_str):
    gpa_clean = normalize_text(gpa_str).upper()
    failing_grades = ["D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"] 
    if not gpa_clean: return False
    if gpa_clean in ["通過", "抵免", "PASS", "EXEMPT"]: return True
    if gpa_clean in failing_grades: return False
    if re.match(r'^[A-C][+\-]?$', gpa_clean): return True
    if gpa_clean.replace('.', '', 1).isdigit():
        try: return float(gpa_clean) >= 60.0 
        except ValueError: pass
    return False

def parse_credit_and_gpa(text):
    text_clean = normalize_text(text)
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]: return 0.0, text_clean
    match_gpa_credit = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if match_gpa_credit:
        try: return float(match_gpa_credit.group(2)), match_gpa_credit.group(1).upper()
        except ValueError: pass
    match_credit_gpa = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', text_clean)
    if match_credit_gpa:
        try: return float(match_credit_gpa.group(1)), match_credit_gpa.group(3).upper()
        except ValueError: pass
    credit_only_match = re.search(r'(\d+(\.\d+)?)', text_clean)
    if credit_only_match:
        try: return float(credit_only_match.group(1)), "" 
        except ValueError: pass
    gpa_only_match = re.search(r'([A-Fa-f][+\-]?)', text_clean)
    if gpa_only_match: return 0.0, gpa_only_match.group(1).upper()
    return 0.0, ""

def extract_year_semester(row_data, found_year_column, found_semester_column, found_course_code_column, found_subject_column, df_columns):
    acad_year = row_data.get(found_year_column, "")
    semester = row_data.get(found_semester_column, "")
    if not acad_year and found_course_code_column and found_course_code_column in row_data:
        match = re.search(r'^(\d{3,4})', row_data[found_course_code_column])
        if match: acad_year = match.group(1)
    if not acad_year and found_subject_column and found_subject_column in row_data:
        match = re.search(r'^(\d{3,4})\s*(上|下|春|夏|秋|冬|1|2|3)?', row_data[found_subject_column])
        if match:
            acad_year = match.group(1)
            if match.group(2) and not semester: semester = match.group(2)
    if not acad_year and len(df_columns) > 0 and df_columns[0] in row_data:
        temp_first_col = row_data[df_columns[0]]
        year_match = re.search(r'(\d{3,4})', temp_first_col)
        if year_match: acad_year = temp_first_col
        if not semester:
            sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
            if sem_match: semester = sem_match.group(1)
    if not semester and len(df_columns) > 1 and df_columns[1] in row_data:
        temp_second_col = row_data[df_columns[1]]
        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
        if sem_match: semester = sem_match.group(1)
    return acad_year, semester


def calculate_total_credits(df_list):
    total_credits = 0.0
    calculated_courses = [] 
    failed_courses = [] 

    credit_column_keywords = ["學分", "學分數", "學分(GPA)", "學 分", "Credits", "Credit", "學分數(學分)"] 
    subject_column_keywords = ["科目名稱", "課程名稱", "Course Name", "Subject Name", "科目", "課程"] 
    gpa_column_keywords = ["GPA", "成績", "Grade", "gpa(數值)"] 
    year_column_keywords = ["學年", "year", "學 年", "學年度"] 
    semester_column_keywords = ["學期", "semester", "學 期"]
    course_code_column_keywords = ["選課代號", "Course Code", "Code", "選課 代號"]


    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3: continue

        found_credit_column, found_subject_column, found_gpa_column, found_year_column, found_semester_column, found_course_code_column = None, None, None, None, None, None

        normalized_df_columns = {re.sub(r'\s+', '', col_name).lower(): col_name for col_name in df.columns}
        
        for k in credit_column_keywords:
            if k in normalized_df_columns: found_credit_column = normalized_df_columns[k]; break
        for k in subject_column_keywords:
            if k in normalized_df_columns: found_subject_column = normalized_df_columns[k]; break
        for k in gpa_column_keywords:
            if k in normalized_df_columns: found_gpa_column = normalized_df_columns[k]; break
        for k in year_column_keywords:
            if k in normalized_df_columns: found_year_column = normalized_df_columns[k]; break
        for k in semester_column_keywords:
            if k in normalized_df_columns: found_semester_column = normalized_df_columns[k]; break
        for k in course_code_column_keywords: 
            if k in normalized_df_columns: found_course_code_column = normalized_df_columns[k]; break

        potential_credit_cols, potential_subject_cols, potential_gpa_cols, potential_year_cols, potential_semester_cols, potential_course_code_cols = [], [], [], [], [], []

        sample_rows_df = df.head(min(len(df), 20)) 

        for col_name in df.columns: 
            sample_data = sample_rows_df[col_name].apply(normalize_text).tolist()
            total_sample_count = len(sample_data)
            if total_sample_count == 0: continue

            credit_vals_found = 0
            for item_str in sample_data:
                credit_val, _ = parse_credit_and_gpa(item_str)
                if 0.0 < credit_val <= 10.0: credit_vals_found += 1
            if credit_vals_found / total_sample_count >= 0.4: potential_credit_cols.append(col_name)

            subject_vals_found = 0
            for item_str in sample_data:
                if re.search(r'[\u4e00-\u9fa5]', item_str) and len(item_str) >= 2 and \
                   not item_str.isdigit() and not re.match(r'^[A-Fa-f][+\-]?$', item_str) and \
                   not item_str.lower() in ["通過", "抵免", "pass", "exempt"] and \
                   not re.match(r'^\d{3,4}$', item_str) and not re.match(r'^\w{2,5}$', item_str): 
                    subject_vals_found += 1
            if subject_vals_found / total_sample_count >= 0.4: potential_subject_cols.append(col_name)

            gpa_vals_found = 0
            for item_str in sample_data:
                if re.match(r'^[A-Fa-f][+\-]?$', item_str) or (item_str.replace('.', '', 1).isdigit() and len(item_str) <=5) or item_str.lower() in ["通過", "抵免", "pass", "exempt"]: 
                    gpa_vals_found += 1
            if gpa_vals_found / total_sample_count >= 0.4: potential_gpa_cols.append(col_name)

            year_vals_found = 0
            for item_str in sample_data:
                if (item_str.isdigit() and (len(item_str) == 3 or len(item_str) == 4)): year_vals_found += 1
            if year_vals_found / total_sample_count >= 0.6: potential_year_cols.append(col_name)

            semester_vals_found = 0
            for item_str in sample_data:
                if item_str.lower() in ["上", "下", "春", "夏", "秋", "冬", "1", "2", "3", "春季", "夏季", "秋季", "冬季", "spring", "summer", "fall", "winter"]: semester_vals_found += 1
            if semester_vals_found / total_sample_count >= 0.6: potential_semester_cols.append(col_name)
            
            course_code_vals_found = 0
            for item_str in sample_data:
                if re.match(r'^\w{3,5}$', item_str) and not (item_str.isdigit() and len(item_str) in [3,4]): 
                    course_code_vals_found += 1
            if course_code_vals_found / total_sample_count >= 0.4: potential_course_code_cols.append(col_name)

        def get_best_col(potentials, reference_col_idx=None, df_cols=df.columns):
            if not potentials: return None
            if reference_col_idx is None: return sorted(potentials, key=lambda x: df_cols.get_loc(x))[0]
            after_ref_candidates = [col for col in potentials if df_cols.get_loc(col) > reference_col_idx]
            if after_ref_candidates: return sorted(after_ref_candidates, key=lambda x: df_cols.get_loc(x))[0]
            return sorted(potentials, key=lambda x: df_cols.get_loc(x))[0]

        if not found_year_column: found_year_column = get_best_col(potential_year_cols)
        year_idx = df.columns.get_loc(found_year_column) if found_year_column else -1
        if not found_semester_column: found_semester_column = get_best_col(potential_semester_cols, year_idx)
        sem_idx = df.columns.get_loc(found_semester_column) if found_semester_column else -1
        if not found_course_code_column: found_course_code_column = get_best_col(potential_course_code_cols, sem_idx)
        code_idx = df.columns.get_loc(found_course_code_column) if found_course_code_column else -1
        if not found_subject_column: found_subject_column = get_best_col(potential_subject_cols, code_idx) 
        subject_idx = df.columns.get_loc(found_subject_column) if found_subject_column else -1
        if not found_credit_column: found_credit_column = get_best_col(potential_credit_cols, subject_idx)
        credit_idx = df.columns.get_loc(found_credit_column) if found_credit_column else -1
        if not found_gpa_column: found_gpa_column = get_best_col(potential_gpa_cols, credit_idx)


        if found_credit_column and found_subject_column: 
            try:
                temp_subject_name_buffer = "" 

                for row_idx, row in df.iterrows():
                    row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}

                    current_row_subject_name_raw = row_data.get(found_subject_column, "")
                    credit_col_content = row_data.get(found_credit_column, "")
                    gpa_col_content = row_data.get(found_gpa_column, "")
                    year_col_content = row_data.get(found_year_column, "") 
                    semester_col_content = row_data.get(found_semester_column, "") 
                    course_code_col_content = row_data.get(found_course_code_column, "") 

                    extracted_credit_this_row, extracted_gpa_this_row = parse_credit_and_gpa(credit_col_content)
                    _, gpa_from_gpa_col = parse_credit_and_gpa(gpa_col_content) 
                    if gpa_from_gpa_col: extracted_gpa_this_row = gpa_from_gpa_col.upper()
                    
                    has_complete_course_info_this_row = (
                        extracted_credit_this_row > 0 or 
                        is_passing_gpa(extracted_gpa_this_row) or 
                        normalize_text(credit_col_content).lower() in ["通過", "抵免", "pass", "exempt"] or 
                        normalize_text(gpa_col_content).lower() in ["通過", "抵免", "pass", "exempt"]
                    )
                    
                    is_strong_new_course_signal = (
                        (year_col_content and year_col_content.isdigit() and len(year_col_content) in [3,4]) or 
                        (semester_col_content and re.search(r'(上|下|春|夏|秋|冬|1|2|3)', semester_col_content)) or
                        (course_code_col_content and re.match(r'^\w{3,5}$', course_code_col_content)) 
                    )

                    is_valid_subject_fragment_text = (
                        current_row_subject_name_raw and len(current_row_subject_name_raw) >= 2 and
                        re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw) and 
                        not (current_row_subject_name_raw.isdigit() and len(current_row_subject_name_raw) in [3,4]) and 
                        not re.match(r'^\w{3,5}$', current_row_subject_name_raw) 
                    )

                    # State machine logic
                    if has_complete_course_info_this_row:
                        # Case 1: This row completes a course. Finalize subject name.
                        final_subject_name = current_row_subject_name_raw
                        if temp_subject_name_buffer:
                            final_subject_name = temp_subject_name_buffer + " " + current_row_subject_name_raw
                        
                        acad_year, semester = extract_year_semester(row_data, found_year_column, found_semester_column, found_course_code_column, found_subject_column, df.columns)
                        course_info = {
                            "學年度": acad_year, "學期": semester, "科目名稱": final_subject_name, 
                            "學分": extracted_credit_this_row, "GPA": extracted_gpa_this_row, "來源表格": df_idx + 1
                        }

                        if extracted_gpa_this_row and not is_passing_gpa(extracted_gpa_this_row): failed_courses.append(course_info)
                        else:
                            if extracted_credit_this_row > 0: total_credits += extracted_credit_this_row
                            calculated_courses.append(course_info)
                        
                        temp_subject_name_buffer = "" # Clear buffer after a course is finalized.

                    elif is_strong_new_course_signal: # 新課程訊號，並且不是完成當前課程的行
                        if temp_subject_name_buffer: # 如果有緩衝區，說明之前的科目沒完成，清空它
                            temp_subject_name_buffer = "" 
                        
                        if is_valid_subject_fragment_text: # 如果當前行的科目名稱有效，作為新課程的第一部分
                             temp_subject_name_buffer = current_row_subject_name_raw

                    elif is_valid_subject_fragment_text:
                        # Case 3: Current row is a subject fragment. Append to buffer.
                        temp_subject_name_buffer += (" " if temp_subject_name_buffer else "") + current_row_subject_name_raw
                        
                    else:
                        # Case 4: Irrelevant row. Clear buffer if any.
                        if temp_subject_name_buffer:
                            temp_subject_name_buffer = "" 
                        
                if temp_subject_name_buffer:
                    # st.warning(f"表格 {df_idx + 1} 偵測到文件末尾未完成的科目名稱片段: '{temp_subject_name_buffer}'，已跳過。")
                    pass 

            except Exception as e:
                import streamlit as st 
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。錯誤訊息: `{e}`")
        else:
            pass 
            
    return total_credits, calculated_courses, failed_courses
