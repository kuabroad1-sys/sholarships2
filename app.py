import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# 웹 페이지 설정
st.set_page_config(page_title="장학금 관리 시스템", layout="wide")

st.title("🎓 외국인 장학금 수혜 대상자 산출 시스템")

# 1. 사이드바 설정: 예산 및 비율 입력
st.sidebar.header("⚙️ 시스템 설정")
total_budget_limit = st.sidebar.number_input("전체 예산(원)", value=500000000, step=10000000)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 선발 인원 비율 설정 (1/n)")
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

# 파일이 모두 업로드되었을 때만 로직 실행
if mapping_file is not None and student_file is not None:
    # 데이터 로드
    mapping_df = pd.read_excel(mapping_file)
    student_df = pd.read_excel(student_file)
    
    # 대학명을 키로 하는 매핑 정보 생성
    mapping_dict = mapping_df.set_index('대학').to_dict(orient='index')

    def get_info(college):
        # 매핑 정보가 없는 대학은 '기타'로 처리
        info = mapping_dict.get(college, {'계열': '기타', '수업료': 0})
        return pd.Series([info['계열'], info['수업료']])

    # 학생 데이터에 계열 및 수업료 매칭
    student_df[['계열', '수업료']] = student_df['대학'].apply(get_info)

    # 3. 필터링 로직 (제외 조건 적용)
    # 텍스트가 잘리지 않도록 변수명과 따옴표를 명확히 작성
    eligible_df = student_df[
        (student_df['등록학기수'] < 8) &
        (student_df['포기전 최종학기 취득학점'] >= 12) &
        (student_df['국적'] != '대한민국') &
        (student_df['추천기관'] != '국립국제교육원') &
        (student_df['포기전 최종학기 평점평균'] >= 3.0)
    ].copy()

    T = len(eligible_df)
    
    # 4. 등급별 총 쿼터 계산 (올림 처리)
    quotas = {
        '100%': (np.ceil(T / n_100) if n_100 > 0 else 0, 1.0),
        '60%': (np.ceil(T / n_60) if n_60 > 0 else 0, 0.6),
        '30%': (np.ceil(T / n_30) if n_30 > 0 else 0, 0.3),
        '10%': (np.ceil(T / n_10) if n_10 > 0 else 0, 0.1)
    }

    # 5. 계열별 비율 및 선발