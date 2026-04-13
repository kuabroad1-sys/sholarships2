import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="장학금 관리 시스템", layout="wide")

st.title("🎓 외국인 장학금 수혜 대상자 산출 시스템")

# 1. 사이드바 - 예산 및 선발 비율 설정
st.sidebar.header("⚙️ 시스템 설정")

# 예산 입력
total_budget_limit = st.sidebar.number_input("전체 예산(원)", value=500000000, step=10000000)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 선발 인원 비율 설정 (1/n)")
# 사용자가 직접 분모(n) 값을 입력
n_100 = st.sidebar.number_input("100% 장학 기준 (1/n)", value=65)
n_60 = st.sidebar.number_input("60% 장학 기준 (1/n)", value=24)
n_30 = st.sidebar.number_input("30% 장학 기준 (1/n)", value=20)
n_10 = st.sidebar.number_input("10% 장학 기준 (1/n)", value=12)

# 2. 파일 업로드 섹션
st.subheader("1. 데이터 업로드")
col1, col2 = st.columns(2)
with col1:
    mapping_file = st.file_uploader("계열확인(수업료 포함) 파일 업로드", type=['xlsx'])
with col2:
    student_file = st.file_uploader("학생 기초 데이터(2.xlsx) 업로드", type=['xlsx'])

if mapping_file and student_file:
    mapping_df = pd.read_excel(mapping_file)
    student_df = pd.read_excel(student_file)
    mapping_dict = mapping_df.set_index('대학').to_dict(orient='index')

    def get_info(college):
        info = mapping_dict.get(college, {'계열': '기타', '수업료': 0})
        return pd.Series([info['계열'], info['수업료']])

    student_df[['계열', '수업료']] = student_df['대학'].apply(get_info)

    # 3. 필터링 (조건 적용)
    eligible_df = student_df[
        (student_df['등록학기수'] < 8) &
        (student_df['포기전 최종학기 취득학점'] >= 12) &
        (student_df['국적'] != '대한민국') &
        (student_df['추천기관'] != '국립국제교육원') &
        (student_df['포기전 최종학기 평점평균'] >= 3.0)
    ].copy()

    T = len(eligible_df)
    
    # 4. 사용자가 설정한 비율(n) 적용하여 쿼터 산출 (올림)
    quotas = {
        '100%': (np.ceil(T / n_100) if n_100 > 0 else 0, 1.0),
        '60%': (np.ceil(T / n_60) if n_60 > 0 else 0, 0.6),
        '30%': (np.ceil(T / n_30) if n_30 > 0 else 0, 0.3),
        '10%': (np.ceil(T / n_10) if n_10 > 0 else 0, 0.1)
    }

    # 5. 계열 비율 및 선발 로직
    group_ratios = eligible_df['계열'].value_counts() / T
    final_list = []

    for group in group_ratios.index:
        group_df = eligible_df[eligible_df['계열'] == group].sort_values(by='포기전 최종학기 평점평균', ascending=False)
        ratio = group_ratios[group]
        
        for grade, (total_q, rate) in quotas.items():
            g_quota = int(round(total_q * ratio))
            if g_quota == 0: continue
            
            temp_top = group_df.head(g_quota)
            if not temp_top.empty:
                cut_off_gpa = temp_top.iloc[-1]['포기전 최종학기 평점평균']
                selected = group_df[group_df['포기전 최종학기 평점평균'] >= cut_off_gpa].copy()
                selected = selected[~selected['학번'].isin([s['학번'] for s in final_list])]
                
                for _, row in selected.iterrows():
                    student_data = row.to_dict()
                    student_data['장학등급'] = grade
                    student_data['수혜금액'] = int(row['수업료'] * rate)
                    final_list.append(student_data)
                
                group_df = group_df[~group_df['학번'].isin(selected['학번'])]

    # 6. 결과 시각화
    final_df = pd.DataFrame(final_list)
    total_spent = final_df['수혜금액'].sum()

    st.subheader("2. 산출 결과 요약")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 대상 인원", f"{T}명")
    m2.metric("실제 집행액", f"{total_spent:,}원")
    m3.metric("예산 대비", f"{(total_spent/total_budget_limit)*100:.1f}%")
    
    # 7. 예산 상태 알림
    if total_spent > total_budget_limit:
        st.error(f"⚠️ 예산 초과: {total_spent - total_budget_limit:,}원이 부족합니다. 비율(n)을 높여 인원을 줄이세요.")
    else:
        st.success(f"✅ 예산 안정권: {total_budget_limit - total_spent:,}원의 여유가 있습니다.")

    st.dataframe(final_df[['계열', '대학', '학과', '학번', '성명', '포기전 최종학기 평점평균', '장학등급', '수혜금액']])

    # 8. 엑셀 다운로드
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Result')
    
    st.download_button(
        label="📥 결과 엑셀 다운로드",
        data=output.getvalue(),
        file_name="scholarship_result.xlsx",
        mime="application/vnd.ms-excel"
    )