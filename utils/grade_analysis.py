# utils/grade_analysis.py

# ... (檔案中其他的函數 is_passing_gpa, parse_credit_and_gpa 維持不變) ...

def calculate_total_credits(df_list):
    """
    從提取的 DataFrames 列表中計算總學分。
    (優化版本：強化對跨行科目名稱的處理)
    """
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    # --- 欄位關鍵字定義 (維持不變) ---
    credit_column_keywords = ["學分", "學分數", "學分(GPA)", "學 分", "Credits", "Credit", "學分數(學分)"]
    subject_column_keywords = ["科目名稱", "課程名稱", "Course Name", "Subject Name", "科目", "課程"]
    gpa_column_keywords = ["GPA", "成績", "Grade", "gpa(數值)"]
    year_column_keywords = ["學年", "year", "學 年"]
    semester_column_keywords = ["學期", "semester", "學 期"]

    for df_idx, df in enumerate(df_list):
        if df.empty or len(df.columns) < 3:
            continue

        # --- 欄位識別邏輯 (維持不變，您的版本已經很完善) ---
        found_credit_column = None
        found_subject_column = None
        found_gpa_column = None
        found_year_column = None
        found_semester_column = None
        
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
        
        # ... (此處省略了從內容推斷欄位的邏輯，您的版本已經存在，直接沿用即可) ...
        # 假設您的欄位推斷邏輯能正確找到 found_subject_column 和 found_credit_column
        # 如果推斷邏輯有問題，也需要一併檢查

        if found_credit_column and found_subject_column:
            try:
                # 將緩衝區移至迴圈外部，確保在整個表格處理過程中持續存在
                temp_subject_name_buffer = "" 

                for row_idx, row in df.iterrows():
                    row_data = {col: normalize_text(row[col]) if pd.notna(row[col]) else "" for col in df.columns}

                    current_row_subject_name_raw = row_data.get(found_subject_column, "")
                    credit_col_content = row_data.get(found_credit_column, "")
                    gpa_col_content = row_data.get(found_gpa_column, "")

                    # --- 解析學分與GPA (與您的版本相同) ---
                    extracted_credit_this_row, extracted_gpa_this_row = 0.0, ""
                    extracted_credit_from_credit_col, extracted_gpa_from_credit_col = parse_credit_and_gpa(credit_col_content)
                    if extracted_credit_from_credit_col > 0:
                        extracted_credit_this_row = extracted_credit_from_credit_col
                    if extracted_gpa_from_credit_col:
                        extracted_gpa_this_row = extracted_gpa_from_credit_col

                    parsed_credit_from_gpa_col, parsed_gpa_from_gpa_col = parse_credit_and_gpa(gpa_col_content)
                    if parsed_gpa_from_gpa_col:
                        extracted_gpa_this_row = parsed_gpa_from_gpa_col.upper()
                    if parsed_credit_from_gpa_col > 0 and extracted_credit_this_row == 0.0:
                        extracted_credit_this_row = parsed_credit_from_gpa_col
                    
                    # --- 判斷是否為有效課程資訊行 (與您的版本相同) ---
                    has_complete_course_info_this_row = (
                        extracted_credit_this_row > 0 or
                        is_passing_gpa(extracted_gpa_this_row) or
                        normalize_text(credit_col_content).lower() in ["通過", "抵免", "pass", "exempt"] or
                        normalize_text(gpa_col_content).lower() in ["通過", "抵免", "pass", "exempt"]
                    )
                    
                    # --- 判斷是否為空行 (與您的版本相同) ---
                    is_effectively_empty_row = all(not row_data.get(col) for col in [found_subject_column, found_credit_column, found_gpa_column])


                    # --- **核心邏輯強化**：處理科目名稱緩衝區 ---
                    if has_complete_course_info_this_row:
                        # 情況1: 當前行包含學分/GPA，是課程的結束行
                        
                        # 組合緩衝區中的名稱和當前行的名稱
                        final_course_name = (temp_subject_name_buffer + " " + current_row_subject_name_raw).strip()
                        if not final_course_name or (len(final_course_name) < 2 and not re.search(r'[\u4e00-\u9fa5]', final_course_name)):
                             final_course_name = "未知科目"

                        # 處理學年學期... (此處邏輯與您的版本相同)
                        acad_year = ""
                        semester = ""
                        # (省略學年學期提取程式碼，沿用您版本中的即可)
                        if found_year_column and row_data.get(found_year_column): acad_year = row_data.get(found_year_column)
                        if found_semester_column and row_data.get(found_semester_column): semester = row_data.get(found_semester_column)
                        
                        # 將課程分類
                        is_failing_grade = not is_passing_gpa(extracted_gpa_this_row) if extracted_gpa_this_row else False
                        
                        if is_failing_grade:
                            failed_courses.append({ "學年度": acad_year, "學期": semester, "科目名稱": final_course_name, "學分": extracted_credit_this_row, "GPA": extracted_gpa_this_row, "來源表格": df_idx + 1 })
                        else:
                            if extracted_credit_this_row > 0:
                                total_credits += extracted_credit_this_row
                            calculated_courses.append({ "學年度": acad_year, "學期": semester, "科目名稱": final_course_name, "學分": extracted_credit_this_row, "GPA": extracted_gpa_this_row, "來源表格": df_idx + 1 })
                        
                        # **重要**: 處理完畢後，清空緩衝區
                        temp_subject_name_buffer = ""

                    elif current_row_subject_name_raw:
                        # 情況2: 當前行沒有學分/GPA，但有科目名稱 -> 視為跨行名稱的一部分
                        # 驗證這確實是個名稱片段，而不是其他雜訊
                        if len(current_row_subject_name_raw) >= 2 and re.search(r'[\u4e00-\u9fa5a-zA-Z]', current_row_subject_name_raw):
                           temp_subject_name_buffer += (" " if temp_subject_name_buffer else "") + current_row_subject_name_raw

                    elif is_effectively_empty_row:
                        # 情況3: 遇到空行
                        # 如果緩衝區有內容，表示一個跨行科目被中斷了，發出警告並清空
                        if temp_subject_name_buffer:
                            import streamlit as st
                            st.warning(f"表格 {df_idx + 1} 偵測到未完成的科目名稱: '{temp_subject_name_buffer}'，因被空行中斷而跳過。")
                            temp_subject_name_buffer = ""
                
                # ... (檔案結尾的其他程式碼)

            except Exception as e:
                import streamlit as st
                st.warning(f"表格 {df_idx + 1} 的學分計算時發生錯誤: `{e}`。")

        else:
            pass
            
    return total_credits, calculated_courses, failed_courses
