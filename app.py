# app.py
import streamlit as st
import pandas as pd
import io
import re
from utils.pdf_processing import extract_tables_from_pdf
from utils.grade_analysis import calculate_total_credits, is_passing_gpa # 確保 is_passing_gpa 也被導入

st.set_page_config(layout="wide")

st.title("📚 成績單學分計算工具")
st.markdown("---")

uploaded_file = st.file_uploader("請上傳您的 PDF 成績單", type="pdf")

if uploaded_file is not None:
    st.success("檔案上傳成功！正在處理中...")
    
    # 讀取 PDF
    try:
        # 使用我們自定義的函數提取表格
        tables_df = extract_tables_from_pdf(io.BytesIO(uploaded_file.read()))

        if not tables_df:
            st.warning("未能在 PDF 中偵測到任何表格。請確認您的 PDF 包含可選取的表格數據。")
        else:
            st.success(f"成功從 PDF 中偵測到 {len(tables_df)} 個表格。")
            
            # 顯示原始表格數據 (可選，用於調試)
            with st.expander("🔍 點擊查看偵測到的原始表格數據"):
                for i, df in enumerate(tables_df):
                    st.write(f"表格 {i+1}:")
                    st.dataframe(df, use_container_width=True)
                    st.markdown("---")

            # 計算總學分並分類課程
            # 注意這裡接收四個返回值
            total_credits, calculated_courses_gpa_passed, failed_courses_gpa, all_courses_with_credits = calculate_total_credits(tables_df)

            st.markdown("---")
            
            # --- 顯示總學分加總結果 ---
            if total_credits is not None:
                st.subheader(f"✅ 總學分加總結果 (所有非零學分垂直加總): {total_credits:.1f}")
                st.caption("此總數包含「學分」欄位中所有大於 0 的數值，不論其 GPA 狀態。")
                
                # 新增顯示所有學分被加總的課程列表
                if all_courses_with_credits:
                    st.subheader("📊 已計入總學分的課程列表")
                    all_credits_df = pd.DataFrame(all_courses_with_credits)
                    # 您可以選擇性地顯示部分欄位，例如科目名稱、學分
                    display_cols_all_credits = [col for col in ["學年度", "學期", "科目名稱", "學分", "GPA", "來源表格"] if col in all_credits_df.columns]
                    st.dataframe(all_credits_df[display_cols_all_credits], height=300, use_container_width=True)
                    st.info("這些是從「學分」欄位提取到數值並計入上方總學分的課程。")
                else:
                    st.info("沒有找到可以加總學分的課程。")
                
                st.markdown("---") # 分隔線
                
                # --- 顯示課程通過情況列表 (橫向 GPA 判斷) ---
                st.subheader("📋 課程通過情況列表 (橫向 GPA 判斷)")
                
                # 顯示通過的課程
                if calculated_courses_gpa_passed: # 更新變數名稱
                    st.write("### ✅ 已通過的課程 (C- 以上成績，或有通過/抵免字樣)")
                    passed_df = pd.DataFrame(calculated_courses_gpa_passed) # 更新變數名稱
                    final_display_passed_cols = [col for col in ["學年度", "學期", "科目名稱", "學分", "GPA", "來源表格"] if col in passed_df.columns]
                    st.dataframe(passed_df[final_display_passed_cols], height=200, use_container_width=True)
                else:
                    st.info("沒有找到通過的課程。")

                # 顯示未通過的課程
                if failed_courses_gpa: # 更新變數名稱
                    st.write("### ❌ 未通過的課程 (GPA 為 'D', 'E', 'F' 等)")
                    failed_df = pd.DataFrame(failed_courses_gpa) # 更新變數名稱
                    final_display_failed_cols = [col for col in ["學年度", "學期", "科目名稱", "學分", "GPA", "來源表格"] if col in failed_df.columns]
                    st.dataframe(failed_df[final_display_failed_cols], height=200, use_container_width=True)
                    st.info("這些科目因成績不及格 ('D', 'E', 'F' 等) 而未計入總學分。")
                else:
                    st.info("沒有找到未通過的課程。")
                
                # --- 下載選項 ---
                st.markdown("---")
                st.subheader("⬇️ 下載結果")
                
                if all_courses_with_credits:
                    csv_data_all_credits = pd.DataFrame(all_courses_with_credits).to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="下載所有計入總學分的課程列表為 CSV",
                        data=csv_data_all_credits,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_all_calculated_credits_courses.csv",
                        mime="text/csv",
                        key="download_all_credits_btn"
                    )

                if calculated_courses_gpa_passed:
                    csv_data_passed = pd.DataFrame(calculated_courses_gpa_passed).to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="下載通過的科目列表為 CSV",
                        data=csv_data_passed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_passed_courses.csv",
                        mime="text/csv",
                        key="download_passed_btn"
                    )
                if failed_courses_gpa:
                    csv_data_failed = pd.DataFrame(failed_courses_gpa).to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="下載不及格的科目列表為 CSV",
                        data=csv_data_failed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_failed_courses.csv",
                        mime="text/csv",
                        key="download_failed_btn"
                    )

            else:
                st.warning("未能成功計算學分，請檢查PDF格式或內容。")

    except Exception as e:
        st.error(f"處理 PDF 時發生錯誤：{e}")
        st.info("請確認您上傳的是有效的 PDF 檔案，且內容為清晰的表格格式。")

st.markdown("---")
st.caption("開發者資訊：此工具旨在輔助學分計算，最終結果請以學校官方成績單為準。")
