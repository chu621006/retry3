# utils/grade_analysis.py
import pandas as pd
import re
from .pdf_processing import normalize_text 

def is_passing_gpa(gpa_str):
    """
    判斷給定的 GPA 字串是否為通過成績。
    """
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
    """
    從單元格文本中解析學分和 GPA。
    返回 (學分, GPA)。如果解析失敗，返回 (0.0, "")。
    """
    text_clean = normalize_text(text)
    
    if text_clean.lower() in ["通過", "抵免", "pass", "exempt"]: return 0.0, text_clean

    match_gpa_credit = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', text_clean)
    if match_gpa_credit:
        gpa = match_gpa_credit.group(1).upper()
        try: return float(match_gpa_credit.group(2)), gpa
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
    """Helper to extract year and semester from row data, with fallback logic."""
    acad_year = row_data.get(found_year_column, "")
    semester = row_data.get(found_semester_column, "")

    # Fallback for year if not directly in its column, try course code
    if not acad_year and found_course_code_column and found_course_code_column in row_data:
        match = re.search(r'^(\d{3,4})', row_data[found_course_code_column])
        if match: acad_year = match.group(1)

    # Fallback for year/semester if not directly in their columns, try subject name
    if not acad_year and found_subject_column and found_subject_column in row_data:
        match = re.search(r'^(\d{3,4})\s*(上|下|春|夏|秋|冬|1|2|3)?', row_data[found_subject_column])
        if match:
            acad_year = match.group(1)
            if match.group(2) and not semester: semester = match.group(2)

    # General fallback to first/second column if year/semester still not found
    if not acad_year and len(df_columns) > 0 and df_columns[0] in row_data:
        temp_first_col = row_data[df_columns[0]]
        year_match = re.search(r'(\d{3,4})', temp_first_col)
        if year_match and len(temp_first_col) <= 5: # Limit length to avoid picking up random numbers
            acad_year = temp_first_col
        if not semester:
            sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_first_col, re.IGNORECASE)
            if sem_match: semester = sem_match.group(1)

    if not semester and len(df_columns) > 1 and df_columns[1] in row_data:
        temp_second_col = row_data[df_columns[1]]
        sem_match = re.search(r'(上|下|春|夏|秋|冬|1|2|3|春季|夏季|秋季|冬季|spring|summer|fall|winter)', temp_second_col, re.IGNORECASE)
        if sem_match: semester = sem_match.group(1)
    
    return acad_year, semester


def calculate_total_credits(df_list):
    """
    從提取的 DataFrames 列表中計算總學分。
    尋找包含 '學分' 或 '學分(GPA)' 類似字樣的欄位進行加總。
    返回總學分和計算學分的科目列表，以及不及格科目列表。
    """
    total_credits = 0.0
    calculated_courses = [] 
    failed_courses = [] 

    # Keywords for column detection (kept for robustness in column finding)
    credit_column_keywords = ["學分", "學分數", "學分(GPA)", "學 分", "Credits", "Credit", "學分數(學分)"] 
    subject_column_keywords = ["科目名稱", "課程名稱", "Course Name", "Subject Name", "科目", "課程"] 
    gpa_column_keywords = ["GPA", "成績", "Grade", "gpa(數值)"] 
    year_column_keywords = ["學年", "year", "學 年", "學年度"] 
    semester_column_keywords = ["學期", "semester", "學 期"]
    course_code_column_keywords = ["選課代號", "Course Code", "Code", "選課 代號"]


    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3: continue

        # Initialize found columns for this DataFrame
        found_credit_column, found_subject_column, found_gpa_column, found_year_column, found_semester_column, found_course_code_column = None, None, None, None, None, None

        # Normalize column names for easier keyword matching
        normalized_df_columns = {re.sub(r'\s+', '', col_name).lower(): col_name for col_name in df.columns}
        
        # Detect actual column names based on keywords
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

        # Also identify potential columns based on data patterns in sample rows (robustness)
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

        # Helper to get the "best" column from potentials, preferring columns after a reference index
        def get_best_col(potentials, reference_col_idx=None, df_cols=df.columns):
            if not potentials: return None
            if reference_col_idx is not None:
                after_ref_candidates = [col for col in potentials if df_cols.get_loc(col) > reference_col_idx]
                if after_ref_candidates: return sorted(after_ref_candidates, key=lambda x: df_cols.get_loc(x))[0]
            return sorted(potentials, key=lambda x: df_cols.get_loc(x))[0]

        # Final assignment of columns (prioritizing keyword matches first, then potential data)
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


        # Main parsing loop for rows
        if found_credit_column and found_subject_column: # Essential columns must be found to proceed
            try:
                temp_subject_name_buffer = "" # Buffer to collect multi-line subject names

                for row_idx, row in df.iterrows():
                    row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}

                    current_row_subject_name_raw = row_data.get(found_subject_column, "")
                    credit_col_content = row_data.get(found_credit_column, "")
                    gpa_col_content = row_data.get(found_gpa_column, "")
                    year_col_content = row_data.get(found_year_column, "") # Get year content for new signal

                    # Extract credit and GPA from their respective columns
                    extracted_credit_this_row, extracted_gpa_this_row = parse_credit_and_gpa(credit_col_content)
                    _, gpa_from_gpa_col = parse_credit_and_gpa(gpa_col_content) 
                    if gpa_from_gpa_col: extracted_gpa_this_row = gpa_from_gpa_col.upper()
                    
                    # Define if this row contains enough info to be considered a complete course entry
                    has_complete_course_info_this_row = (
                        extracted_credit_this_row > 0 or 
                        is_passing_gpa(extracted_gpa_this_row) or 
                        normalize_text(credit_col_content).lower() in ["通過", "抵免", "pass", "exempt"] or 
                        normalize_text(gpa_col_content).lower() in ["通過", "抵免", "pass", "exempt"]
                    )
                    
                    # Define if the text in the subject column looks like a valid part of a subject name
                    is_valid_subject_fragment_text = (
                        current_row_subject_name_raw and len(current_row_subject_name_raw) >= 2 and
                        re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw) and 
                        not (current_row_subject_name_raw.isdigit() and len(current_row_subject_name_raw) in [3,4]) and 
                        not re.match(r'^\w{3,5}$', current_row_subject_name_raw) and
                        not (len(current_row_subject_name_raw) <=3 and not re.search(r'[\u4e00-\u9fa5]', current_row_subject_name_raw)) # Avoid very short non-Chinese fragments
                    )

                    # --- State machine logic (New Year signal is highest priority) ---
                    # New: If a 3 or 4 digit number is found in the '學年度' column, it's a strong new course signal.
                    is_new_year_signal = (
                        year_col_content and re.match(r'^\d{3,4}$', year_col_content)
                    )

                    if is_new_year_signal:
                        # Case 1: New academic year detected. Force clear buffer to prevent pollution.
                        if temp_subject_name_buffer:
                            # If there was a buffered subject, it implies a previous multi-line course wasn't finalized.
                            # We discard it to prevent pollution of the new academic year's courses.
                            temp_subject_name_buffer = ""
                        
                        # Now, if the current row also has complete course info, process it.
                        # This covers cases where the first row of a new year also contains course details.
                        if has_complete_course_info_this_row:
                            final_subject_name = current_row_subject_name_raw # No buffer for new year's first course unless it's itself multi-line
                            
                            acad_year, semester = extract_year_semester(row_data, found_year_column, found_semester_column, found_course_code_column, found_subject_column, df.columns)
                            course_info = {
                                "學年度": acad_year, "學期": semester, "科目名稱": final_subject_name, 
                                "學分": extracted_credit_this_row, "GPA": extracted_gpa_this_row, "來源表格": df_idx + 1
                            }
                            if extracted_gpa_this_row and not is_passing_gpa(extracted_gpa_this_row): failed_courses.append(course_info)
                            else:
                                if extracted_credit_this_row > 0: total_credits += extracted_credit_this_row
                                calculated_courses.append(course_info)
                            # Buffer is already clear from is_new_year_signal check.
                            
                        # If the new year signal is present, and it's not a complete course row,
                        # but it's a valid subject fragment, start buffering for this new year.
                        elif is_valid_subject_fragment_text:
                            temp_subject_name_buffer = current_row_subject_name_raw


                    elif has_complete_course_info_this_row:
                        # Case 2: This row completes a course (no new year signal, or new year signal handled above).
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
                        
                        temp_subject_name_buffer = "" # CRITICAL: Clear buffer immediately after finalizing a course.

                    elif is_valid_subject_fragment_text:
                        # Case 3: This row is a valid subject fragment, but doesn't complete a course,
                        # and no new year signal was detected. Append to buffer.
                        temp_subject_name_buffer += (" " if temp_subject_name_buffer else "") + current_row_subject_name_raw
                        
                    else:
                        # Case 4: Irrelevant row (not a course completion, not a valid subject fragment, no new year signal).
                        # Clear buffer to prevent contamination from unrelated text.
                        if temp_subject_name_buffer:
                            temp_subject_name_buffer = "" 
                        
                # After iterating through all rows in a DataFrame, check if there's any lingering subject fragment
                if temp_subject_name_buffer:
                    # Log or discard incomplete buffered subject at the end of a table.
                    pass 

            except Exception as e:
                import streamlit as st 
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。該表格的學分可能無法計入總數。請檢查學分和GPA欄位數據是否正確。錯誤訊息: `{e}`")
        else:
            pass # Skip if essential columns are not found
            
    return total_credits, calculated_courses, failed_courses
